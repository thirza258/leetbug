"""Incident: invalid partner orders leak database connections until the API stalls (resource leak, level 2)."""
from app.catalog import case, code
from app.incidents.catalog_common import artifact, at, event, log, series, span, text_artifact

STARTER = code('''
    from contextlib import contextmanager


    class PoolExhausted(Exception):
        """No idle connection: the pool limit was reached (QueuePool timeout)."""


    class ValidationError(Exception):
        pass


    class Database:
        def __init__(self):
            self.orders = []
            self.order_lines = 0

        def apply(self, statement):
            if statement[0] == "insert_order":
                self.orders.append(statement[1])
            else:
                self.order_lines += 1


    class Connection:
        def __init__(self, number, database):
            self.number = number
            self.database = database
            self.pending = None   # statements of the open transaction; None when idle

        def begin(self):
            # Like PostgreSQL, BEGIN inside an open transaction only warns: earlier statements stay pending.
            if self.pending is None:
                self.pending = []

        def execute(self, statement):
            if self.pending is None:
                self.pending = []
            self.pending.append(statement)

        def commit(self):
            for statement in self.pending or []:
                self.database.apply(statement)
            self.pending = None

        def rollback(self):
            self.pending = None


    class ConnectionPool:
        def __init__(self, size, database):
            self.size = size
            self.connections = [Connection(number, database) for number in range(1, size + 1)]
            self.idle = list(reversed(self.connections))   # pop() hands out connection 1 first
            self.checked_out = set()

        def acquire(self):
            if not self.idle:
                raise PoolExhausted()
            connection = self.idle.pop()
            self.checked_out.add(connection.number)
            return connection

        def release(self, connection):
            self.checked_out.discard(connection.number)
            self.idle.append(connection)

        @contextmanager
        def transaction(self):
            """One transaction: commit on success, roll back on error, always return the connection."""
            connection = self.acquire()
            connection.begin()
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                self.release(connection)


    class OrderService:
        def __init__(self, pool, catalog):
            self.pool = pool
            self.catalog = set(catalog)

        def create_order(self, request):
            connection = self.pool.acquire()
            connection.begin()
            connection.execute(("insert_order", request["order_id"]))
            for line in request["lines"]:
                if line["sku"] not in self.catalog or line["quantity"] <= 0:
                    raise ValidationError(f"invalid line {line['sku']} x {line['quantity']}")
                connection.execute(("insert_line", request["order_id"], line["sku"], line["quantity"]))
            connection.commit()
            self.pool.release(connection)
            return request["order_id"]

        def handle(self, request):
            """HTTP handler: 201 created, 422 invalid order, 503 when no connection is free."""
            try:
                self.create_order(request)
                return 201
            except ValidationError:
                return 422
            except PoolExhausted:
                return 503


    def solve(data):
        database = Database()
        pool = ConnectionPool(data["pool_size"], database)
        service = OrderService(pool, data["catalog"])
        statuses = [service.handle(request) for request in data["requests"]]
        return {
            "statuses": statuses,
            "state": {
                "orders": database.orders,
                "order_lines": database.order_lines,
                "pool": {
                    "size": pool.size,
                    "in_use": len(pool.checked_out),
                    "open_transactions": sum(1 for connection in pool.connections if connection.pending is not None),
                },
            },
        }
''')

SOLUTION = STARTER.replace('''    def create_order(self, request):
        connection = self.pool.acquire()
        connection.begin()
        connection.execute(("insert_order", request["order_id"]))
        for line in request["lines"]:
            if line["sku"] not in self.catalog or line["quantity"] <= 0:
                raise ValidationError(f"invalid line {line['sku']} x {line['quantity']}")
            connection.execute(("insert_line", request["order_id"], line["sku"], line["quantity"]))
        connection.commit()
        self.pool.release(connection)
        return request["order_id"]
''', '''    def create_order(self, request):
        # The transaction context rolls back on every error path and always releases the connection,
        # so a rejected order can neither leak a connection nor leave half a transaction behind.
        with self.pool.transaction() as connection:
            connection.execute(("insert_order", request["order_id"]))
            for line in request["lines"]:
                if line["sku"] not in self.catalog or line["quantity"] <= 0:
                    raise ValidationError(f"invalid line {line['sku']} x {line['quantity']}")
                connection.execute(("insert_line", request["order_id"], line["sku"], line["quantity"]))
        return request["order_id"]
''')
assert SOLUTION != STARTER

CATALOG = ["SKU-1", "SKU-2", "SKU-3"]


def _order(order_id, *lines):
    return {"order_id": order_id, "lines": [{"sku": sku, "quantity": quantity} for sku, quantity in lines]}


def _result(statuses, orders, lines, size):
    return {"statuses": statuses, "state": {"orders": orders, "order_lines": lines,
                                            "pool": {"size": size, "in_use": 0, "open_transactions": 0}}}


TESTS = [
    case("Healthy traffic",
         {"pool_size": 2, "catalog": CATALOG,
          "requests": [_order("o-1", ("SKU-1", 1)), _order("o-2", ("SKU-2", 2), ("SKU-3", 1)), _order("o-3", ("SKU-1", 1))]},
         _result([201, 201, 201], ["o-1", "o-2", "o-3"], 4, 2)),
    case("Validation errors exhaust the pool",
         {"pool_size": 2, "catalog": CATALOG,
          "requests": [_order("o-10", ("SKU-9", 1)), _order("o-11", ("SKU-1", 0)), _order("o-12", ("SKU-1", 1)),
                       _order("o-13", ("SKU-2", 1))]},
         _result([422, 422, 201, 201], ["o-12", "o-13"], 2, 2),
         assertions=[{"path": "state.pool.in_use", "equals": 0}]),
    case("One bad order with a pool of one",
         {"pool_size": 1, "catalog": CATALOG, "requests": [_order("o-20", ("SKU-2", -1)), _order("o-21", ("SKU-2", 1))]},
         _result([422, 201], ["o-21"], 1, 1)),
    case("Rejected order leaves no partial rows",
         {"pool_size": 1, "catalog": CATALOG,
          "requests": [_order("o-30", ("SKU-1", 1), ("SKU-9", 1)), _order("o-31", ("SKU-3", 2))]},
         _result([422, 201], ["o-31"], 1, 1), True, [{"path": "state.orders", "equals": ["o-31"]}]),
    case("Burst larger than the pool",
         {"pool_size": 3, "catalog": CATALOG,
          "requests": [_order("o-40", ("SKU-9", 1)), _order("o-41", ("SKU-1", 0)), _order("o-42", ("SKU-8", 2)),
                       _order("o-43", ("SKU-2", -5)), _order("o-44", ("SKU-1", 1)), _order("o-45", ("SKU-2", 3))]},
         _result([422, 422, 422, 422, 201, 201], ["o-44", "o-45"], 2, 3), True),
    case("Mixed traffic",
         {"pool_size": 2, "catalog": CATALOG,
          "requests": [_order("o-50", ("SKU-1", 1)), _order("o-51", ("SKU-9", 1)), _order("o-52", ("SKU-2", 1)),
                       _order("o-53", ("SKU-3", 0)), _order("o-54", ("SKU-3", 1))]},
         _result([201, 422, 201, 422, 201], ["o-50", "o-52", "o-54"], 3, 2), True),
    case("Order without lines", {"pool_size": 1, "catalog": CATALOG, "requests": [_order("o-60")]},
         _result([201], ["o-60"], 0, 1), True),
    case("No requests", {"pool_size": 2, "catalog": CATALOG, "requests": []}, _result([], [], 0, 2), True),
    case("Invalid last line after valid lines",
         {"pool_size": 2, "catalog": CATALOG,
          "requests": [_order("o-70", ("SKU-1", 1), ("SKU-2", 2), ("SKU-3", 0)), _order("o-71", ("SKU-3", 1)),
                       _order("o-72", ("SKU-1", 1))]},
         _result([422, 201, 201], ["o-71", "o-72"], 2, 2), True),
]

POD_1, POD_2, POD_3 = "orders-api-7d9f-1", "orders-api-7d9f-2", "orders-api-7d9f-3"
LOGS = sorted([
    log("2026-07-09T09:31:05.201Z", "INFO", "orders-api", "service started", None, version="2026.07.09-1",
        pool_size=20, pod=POD_1),
    log("2026-07-09T10:05:12.330Z", "INFO", "orders-api", "order created", "t-o050", order_id="web-87961",
        status=201, pod=POD_2),
    log("2026-07-09T10:12:40.118Z", "WARN", "orders-api", "order rejected: invalid line", "t-o100",
        order_id="po-5531", sku="SKU-77-OLD", quantity=2, status=422, pod=POD_1),
    log("2026-07-09T10:12:41.503Z", "WARN", "orders-api", "order rejected: invalid line", None,
        order_id="po-5532", sku="SKU-77-OLD", quantity=1, status=422, pod=POD_2),
    log("2026-07-09T10:12:44.017Z", "WARN", "orders-api", "order rejected: invalid line", None,
        order_id="po-5533", sku="SKU-81-OLD", quantity=4, status=422, pod=POD_3),
    log("2026-07-09T10:15:20.950Z", "INFO", "orders-api", "order created", None, order_id="web-88042",
        status=201, pod=POD_1),
    log("2026-07-09T10:18:02.441Z", "WARN", "orders-api", "order rejected: invalid line", None,
        order_id="po-5570", sku="SKU-77-OLD", quantity=3, status=422, pod=POD_1),
    log("2026-07-09T10:20:58.770Z", "ERROR", "orders-api",
        "QueuePool limit of size 20 overflow 0 reached, connection timed out, timeout 30.00", "t-o200",
        order_id="web-88120", status=503, pod=POD_1),
    log("2026-07-09T10:21:00.913Z", "ERROR", "orders-api",
        "QueuePool limit of size 20 overflow 0 reached, connection timed out, timeout 30.00", None,
        order_id="web-88121", status=503, pod=POD_2),
    log("2026-07-09T10:21:30.000Z", "WARN", "kubelet", "Readiness probe failed: GET /ready returned 503", None,
        pod=POD_1),
    log("2026-07-09T10:24:00.000Z", "WARN", "orders-db", "sessions idle in transaction", None, count=58,
        oldest_seconds=680, cpu_percent=12, connections=74, max_connections=300),
    log("2026-07-09T10:31:00.000Z", "INFO", "deployer", "rollout restart deployment/orders-api", None,
        actor="oncall-sre"),
    log("2026-07-09T10:31:40.884Z", "INFO", "orders-api", "service started", None, version="2026.07.09-1",
        pool_size=20, pod="orders-api-7d9f-4"),
    log("2026-07-09T10:31:52.106Z", "INFO", "orders-api", "order created", None, order_id="web-88301",
        status=201, pod="orders-api-7d9f-4"),
    log("2026-07-09T10:33:10.640Z", "WARN", "orders-api", "order rejected: invalid line", None,
        order_id="po-5602", sku="SKU-81-OLD", quantity=1, status=422, pod="orders-api-7d9f-4"),
    log("2026-07-09T10:47:12.392Z", "ERROR", "orders-api",
        "QueuePool limit of size 20 overflow 0 reached, connection timed out, timeout 30.00", None,
        order_id="web-88570", status=503, pod="orders-api-7d9f-4"),
    log("2026-07-09T10:52:00.000Z", "INFO", "api-gateway", "client blocked", None, client="partner-b2b",
        actor="oncall-sre"),
    log("2026-07-09T10:55:00.000Z", "INFO", "deployer", "rollout restart deployment/orders-api", None,
        actor="oncall-sre"),
    log("2026-07-09T11:20:00.000Z", "INFO", "orders-db", "parameter changed", None,
        idle_in_transaction_session_timeout="60s"),
    log("2026-07-09T11:22:05.311Z", "WARN", "orders-db",
        "terminating connection due to idle-in-transaction timeout", None, pid=48211),
], key=lambda entry: entry["ts"])

START = "2026-07-09T09:00:00Z"
ARTIFACTS = [
    artifact("orders-logs", "logs", "orders-api, gateway and database logs",
             "Logs from three orders-api pods, Kubernetes and orders-db, 09:31–11:22 UTC.", {"entries": LOGS}),
    artifact("orders-metrics", "metrics", "Orders API dashboard", "Five-minute values summed across pods "
             "(3 pods × 20 connections).", {
                 "series": [
                     series("db_pool_connections_in_use", "connections", START, 5,
                            [7, 6, 8, 7, 9, 8, 7, 6, 7, 8, 7, 8, 9, 8, 10, 21, 60, 60, 60, 8, 33, 58, 60, 7, 8, 7, 6,
                             7, 8, 7, 7]),
                     series("http_5xx", "count per 5 min", START, 5,
                            [0] * 16 + [340, 1210, 1180, 40, 0, 610, 1150, 90, 0, 0, 0, 0, 0, 0, 0]),
                     series("http_422", "count per 5 min", START, 5,
                            [1, 0, 2, 1, 0, 1, 0, 1, 2, 0, 1, 1, 0, 1, 4, 22, 25, 3, 2, 24, 23, 9, 1, 0, 0, 1, 0, 0,
                             1, 0, 0]),
                     series("postgres_idle_in_transaction_sessions", "sessions", START, 5,
                            [0] * 15 + [21, 58, 60, 60, 0, 25, 56, 60, 0, 0, 0, 0, 0, 0, 0, 0]),
                 ],
                 "annotations": [
                     {"at": "2026-07-09T09:30:00Z", "label": "Deploy orders-api 2026.07.09-1"},
                     {"at": "2026-07-09T10:12:00Z", "label": "Partner sends retired SKUs"},
                     {"at": "2026-07-09T10:31:00Z", "label": "Pods restarted"},
                     {"at": "2026-07-09T10:52:00Z", "label": "Partner blocked"},
                     {"at": "2026-07-09T10:55:00Z", "label": "Pods restarted"},
                 ]}),
    artifact("orders-traces", "traces", "A rejected order, a failed order and a healthy order",
             "t-o100 is a partner order with a retired SKU; t-o200 is a valid order eight minutes later; t-o050 is "
             "a valid order before the incident.", {"traces": [
                 {"trace_id": "t-o100", "spans": [
                     span("t-o100-1", None, "api-gateway", "POST /orders", 0, 9.8, **{"http.status_code": 422}),
                     span("t-o100-2", "t-o100-1", "orders-api", "create_order", 1.0, 8.1, "error",
                          error="ValidationError: invalid line SKU-77-OLD x 2"),
                     span("t-o100-3", "t-o100-2", "orders-api", "pool.acquire", 1.2, 0.3, **{"pool.checked_out": 4}),
                     span("t-o100-4", "t-o100-2", "orders-db", "BEGIN", 1.6, 0.4),
                     span("t-o100-5", "t-o100-2", "orders-db", "INSERT INTO orders", 2.1, 1.9,
                          **{"db.rows_affected": 1}),
                     span("t-o100-6", "t-o100-2", "orders-api", "validate lines", 4.2, 0.2, "error"),
                 ]},
                 {"trace_id": "t-o200", "spans": [
                     span("t-o200-1", None, "api-gateway", "POST /orders", 0, 30012, "error",
                          **{"http.status_code": 503}),
                     span("t-o200-2", "t-o200-1", "orders-api", "create_order", 1.0, 30009, "error"),
                     span("t-o200-3", "t-o200-2", "orders-api", "pool.acquire", 1.5, 30000, "error",
                          **{"pool.size": 20, "pool.checked_out": 20,
                             "error": "QueuePool limit of size 20 overflow 0 reached"}),
                 ]},
                 {"trace_id": "t-o050", "spans": [
                     span("t-o050-1", None, "api-gateway", "POST /orders", 0, 14.6, **{"http.status_code": 201}),
                     span("t-o050-2", "t-o050-1", "orders-api", "create_order", 1.0, 12.9),
                     span("t-o050-3", "t-o050-2", "orders-api", "pool.acquire", 1.1, 0.2, **{"pool.checked_out": 3}),
                     span("t-o050-4", "t-o050-2", "orders-db", "BEGIN", 1.4, 0.3),
                     span("t-o050-5", "t-o050-2", "orders-db", "INSERT INTO orders", 1.9, 1.7),
                     span("t-o050-6", "t-o050-2", "orders-db", "INSERT INTO order_lines", 3.8, 1.5),
                     span("t-o050-7", "t-o050-2", "orders-db", "COMMIT", 11.0, 1.4),
                     span("t-o050-8", "t-o050-2", "orders-api", "pool.release", 12.6, 0.1),
                 ]},
             ]}),
    artifact("orders-db-activity", "database", "orders-db session activity", "pg_stat_activity at 10:24 UTC "
             "(5 of 58 idle-in-transaction sessions shown) and order counts per 15 minutes.", {"tables": [
                 {"name": "pg_stat_activity", "columns": ["pid", "application_name", "state", "xact_start", "query"],
                  "rows": [
                      [48211, POD_1, "idle in transaction", "2026-07-09T10:12:40Z",
                       "INSERT INTO orders (order_id, customer_id) VALUES ($1, $2)"],
                      [48219, POD_2, "idle in transaction", "2026-07-09T10:12:41Z",
                       "INSERT INTO orders (order_id, customer_id) VALUES ($1, $2)"],
                      [48230, POD_3, "idle in transaction", "2026-07-09T10:12:44Z",
                       "INSERT INTO orders (order_id, customer_id) VALUES ($1, $2)"],
                      [48302, POD_1, "idle in transaction", "2026-07-09T10:18:02Z",
                       "INSERT INTO order_lines (order_id, sku, quantity) VALUES ($1, $2, $3)"],
                      [48377, POD_2, "idle in transaction", "2026-07-09T10:19:15Z",
                       "INSERT INTO orders (order_id, customer_id) VALUES ($1, $2)"],
                      [48410, "monitoring", "active", "2026-07-09T10:24:00Z", "SELECT * FROM pg_stat_activity"],
                  ]},
                 {"name": "orders created (15-minute buckets)", "columns": ["bucket_start", "created", "rejected"],
                  "rows": [[at(START, minutes=15 * i), created, rejected] for i, (created, rejected) in enumerate(
                      [(212, 2), (205, 1), (220, 2), (231, 1), (198, 31), (12, 30), (171, 47), (15, 10),
                       (240, 0), (236, 1)])]},
             ]}),
    text_artifact("orders-config", "config", "orders-api and orders-db settings", "Deployed configuration.",
                  "deploy/orders.yaml", "yaml", '''
orders-api:
  replicas: 3
  database:
    host: orders-db.internal
    pool_size: 20             # per pod
    max_overflow: 0
    pool_timeout_seconds: 30
  readiness_probe: /ready     # fails when no connection is available
orders-db:
  max_connections: 300
  idle_in_transaction_session_timeout: 0   # disabled; set to 60s at 11:20 UTC
'''),
    artifact("deploy-2026-07-09-1", "diff", "Deploy 2026.07.09-1: validate lines inside the transaction",
             "Deployed 2026-07-09 09:30 UTC.", {
                 "title": "Validate order lines inside the order transaction (one pass over the lines)",
                 "author": "dev-orders-team", "content": '''
--- a/orders/service.py
+++ b/orders/service.py
@@ -88,12 +88,15 @@ class OrderService:
     def create_order(self, request):
-        for line in request["lines"]:
-            if line["sku"] not in self.catalog or line["quantity"] <= 0:
-                raise ValidationError(f"invalid line {line['sku']} x {line['quantity']}")
-        with self.pool.transaction() as connection:
-            connection.execute(("insert_order", request["order_id"]))
-            for line in request["lines"]:
-                connection.execute(("insert_line", request["order_id"], line["sku"], line["quantity"]))
+        connection = self.pool.acquire()
+        connection.begin()
+        connection.execute(("insert_order", request["order_id"]))
+        for line in request["lines"]:
+            if line["sku"] not in self.catalog or line["quantity"] <= 0:
+                raise ValidationError(f"invalid line {line['sku']} x {line['quantity']}")
+            connection.execute(("insert_line", request["order_id"], line["sku"], line["quantity"]))
+        connection.commit()
+        self.pool.release(connection)
         return request["order_id"]
'''.strip("\n") + "\n"}),
    artifact("orders-architecture", "architecture", "Order intake", "Order traffic from the web shop and the "
             "B2B partner.", {
                 "nodes": [
                     {"id": "web", "label": "web storefront", "kind": "service"},
                     {"id": "partner", "label": "partner-b2b", "kind": "external"},
                     {"id": "gateway", "label": "api-gateway", "kind": "service"},
                     {"id": "orders", "label": "orders-api (3 pods, pool 20 each)", "kind": "service"},
                     {"id": "db", "label": "orders-db (PostgreSQL)", "kind": "database"},
                     {"id": "catalog-sync", "label": "catalog-sync (nightly)", "kind": "service"},
                 ],
                 "edges": [
                     {"from": "web", "to": "gateway", "label": "POST /orders"},
                     {"from": "partner", "to": "gateway", "label": "POST /orders (batch import)"},
                     {"from": "gateway", "to": "orders", "label": "route"},
                     {"from": "orders", "to": "db", "label": "pooled connections"},
                     {"from": "catalog-sync", "to": "db", "label": "catalog table"},
                 ]}),
]

INCIDENT = {
    "slug": "connection-pool-exhaustion",
    "title": "Orders API stalls after a burst of invalid partner orders",
    "summary": "A partner started sending retired SKUs. Each rejected order quietly kept a database connection, "
               "and within minutes every order — valid or not — failed with 503.",
    "severity": "SEV-2",
    "level": 2,
    "category": "resource_leak",
    "taxonomy": {"bug_categories": ["resource_leak", "database_transactions", "runtime_exception"],
                 "skills": ["log_investigation", "stack_trace_analysis", "performance_profiling", "reproduction"]},
    "affected_services": ["orders-api", "orders-db", "api-gateway"],
    "impact": [
        "Order intake failed for about 25 minutes in two waves; roughly 4,500 requests returned 503.",
        "Web shop customers could not place orders while partner orders were being rejected.",
        "Pod restarts restored service for only about 15 minutes each.",
    ],
    "expected_behavior": "Invalid orders are rejected with 422 without affecting capacity; every request returns "
                         "its connection to the pool with no open transaction.",
    "observed_symptoms": [
        "QueuePool timeouts and 503 responses on all three pods.",
        "orders-db reports dozens of sessions 'idle in transaction'.",
        "Database CPU is 12% and far below max_connections.",
        "Restarting the pods fixes the errors for a while; blocking the partner stops new errors.",
    ],
    "objective": "Explain why rejected orders exhaust the pool, fix OrderService.create_order() so every path "
                 "returns its connection clean, and propose operational safeguards.",
    "timeline": [
        event("2026-07-09T09:30:00Z", "deploy", "orders-api 2026.07.09-1",
              "Validates order lines inside the order transaction to avoid a second pass over the lines."),
        event("2026-07-09T10:12:00Z", "note", "Partner sends retired SKUs",
              "partner-b2b's catalog sync lags; its batch import contains SKUs retired the day before."),
        event("2026-07-09T10:14:00Z", "symptom", "422 responses rise", "Rejected partner orders, expected for bad data."),
        event("2026-07-09T10:21:00Z", "alert", "orders-api 5xx above 20%",
              "QueuePool timeouts on all pods; readiness probes start failing."),
        event("2026-07-09T10:24:00Z", "alert", "orders-db idle-in-transaction sessions",
              "58 sessions idle in transaction; CPU 12%, 74 of 300 connections."),
        event("2026-07-09T10:31:00Z", "action", "Pods restarted", "503s stop for about 15 minutes."),
        event("2026-07-09T10:47:00Z", "symptom", "503s return", "Pool exhaustion repeats as partner orders continue."),
        event("2026-07-09T10:52:00Z", "action", "Partner blocked at the gateway",
              "Stops new rejections; the exhausted pools need another restart."),
        event("2026-07-09T10:55:00Z", "action", "Pods restarted", "Service recovers."),
        event("2026-07-09T11:20:00Z", "action", "Idle-transaction timeout enabled",
              "orders-db terminates sessions idle in a transaction for 60 seconds."),
    ],
    "artifacts": ARTIFACTS,
    "scenarios": [
        {"id": "healthy-traffic", "name": "Healthy traffic", "description": "Valid orders only.",
         "tests": ["Healthy traffic"]},
        {"id": "invalid-burst", "name": "Validation errors exhaust the pool",
         "description": "Two invalid orders, then two valid ones, with a pool of two.",
         "tests": ["Validation errors exhaust the pool"]},
        {"id": "single-connection", "name": "One bad order with a pool of one",
         "description": "The smallest reproduction.", "tests": ["One bad order with a pool of one"]},
    ],
    "rubric": {
        "version": 1, "source": "authored",
        "defect_categories": ["resource_leak"],
        "related_categories": ["database_transactions", "runtime_exception", "configuration"],
        "root_cause": [
            ["connection", "connections", "pool"],
            ["not released", "never released", "never returned", "not returned", "leak", "leaked", "leaks",
             "release"],
            ["error path", "exception", "validation error", "validationerror", "raise", "raised", "early exit"],
            ["rollback", "rolled back", "open transaction", "idle in transaction", "uncommitted"],
        ],
        "component": ["create_order", "release", "ConnectionPool", "OrderService"],
        "invariant": [
            ["every connection", "each connection", "acquired connection", "connection acquired", "every request"],
            ["returned", "released", "given back", "back to the pool"],
            ["every path", "all paths", "error path", "success or failure", "even on error", "always"],
        ],
        "correction": [
            ["finally", "try/finally", "context manager", "with statement", "transaction()", "with block"],
            ["release", "return the connection"],
            ["rollback", "roll back"],
        ],
        "reproduction": [
            ["invalid order", "validation error", "bad order", "invalid line", "unknown sku", "retired sku"],
            ["pool size", "pool of", "small pool", "pool_size", "pool of one", "pool of two"],
            ["503", "pool exhausted", "exhaust", "valid order fails", "next request fails", "subsequent"],
        ],
    },
    "evaluation": {
        "remediation_concepts": [
            ["restart", "recycle", "rollout"],
            ["terminate idle", "idle in transaction", "pg_terminate_backend", "idle_in_transaction_session_timeout"],
            ["hotfix", "rollback", "revert", "deploy the fix"],
            ["block the partner", "reject earlier", "rate limit", "contact the partner"],
        ],
        "prevention_concepts": [
            ["context manager", "finally", "lint", "static analysis"],
            ["test", "error path test", "fault injection", "regression test"],
            ["idle_in_transaction_session_timeout", "timeout", "statement timeout"],
            ["monitor", "alert", "pool usage", "in use", "idle in transaction"],
            ["validate before", "validate early", "validate first"],
        ],
        "impact_concepts": [
            ["503", "unavailable", "outage", "errors", "failed"],
            ["orders", "customers", "web shop", "checkout"],
            ["minutes", "duration", "25", "two waves"],
            ["valid orders", "all requests", "every order"],
        ],
    },
    "problem": {
        "title": "Incident: rejected orders drain the connection pool",
        "summary": "Every rejected order keeps its database connection and an open transaction, so valid orders soon "
                   "fail with 503. Make every request return its connection clean.",
        "category": "runtime",
        "difficulty": "medium",
        "tags": ["resource-lifecycle", "error-handling", "transactions", "cleanup"],
        "requirements": [
            "Input has pool_size, the catalog of valid SKUs, and requests [{order_id, lines: [{sku, quantity}]}] "
            "handled one after another.",
            "An order is valid when every line has a catalog SKU and a positive quantity; an order without lines is "
            "valid. Valid orders return 201 and commit the order and its lines.",
            "Invalid orders return 422 and leave no rows behind. Return 503 only when every connection is "
            "genuinely in use.",
            "After each request the pool must be as before: connection released and no open transaction. Return "
            "{statuses, state: {orders (committed ids in commit order), order_lines, pool: {size, in_use, "
            "open_transactions}}}.",
        ],
        "starters": {"python": STARTER},
        "solutions": {"python": SOLUTION},
        "tests": TESTS,
        "explanation": "create_order() released its connection only after a successful commit. A validation error "
                       "raised mid-transaction skipped both the rollback and the release, so each rejected order "
                       "left one connection idle in a transaction until the pool was empty and every request "
                       "returned 503; restarts only reset the leak. Using the pool's transaction() context (or "
                       "try/except/finally) rolls back on error and always releases. The rollback matters too: a "
                       "connection returned with pending statements would commit the rejected order with the next "
                       "request. Time O(lines) per request.",
        "hints": [
            "The pool loses one connection for every rejected order. Where does a request give its connection back?",
            "Follow an invalid order: acquire, BEGIN, INSERT, then the validation error. Which statements never run? "
            "Compare the healthy trace.",
            "The error path skips both commit and release. Roll back on failure and release in a finally block or the "
            "pool's transaction() context, so every path returns the connection clean.",
        ],
        "minutes": 25,
    },
}
