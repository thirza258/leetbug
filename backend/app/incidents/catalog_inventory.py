"""Incident: a flash sale oversells a limited allocation (race condition, level 3)."""
from app.catalog import case, code
from app.incidents.catalog_common import (
    artifact,
    event,
    log,
    series,
    span,
    text_artifact,
    ts,
)

SKU = "SKU-CONSOLE-LE"
SALE = "2026-04-18T10:00:00Z"

STARTER = code('''
    LOW_STOCK_THRESHOLD = 5


    class InventoryDatabase:
        """In-memory stand-in for the inventory tables.

        Each statement runs atomically inside the database, then yields once while its response
        travels back, so other requests can run before the caller resumes. Call statements with
        ``yield from``.
        """

        def __init__(self, stock):
            self.available = dict(stock)
            self.reservations = []

        def select_available(self, sku):
            # SELECT available FROM inventory WHERE sku = :sku
            value = self.available.get(sku, 0)
            yield "select"
            return value

        def update_available(self, sku, value):
            # UPDATE inventory SET available = :value WHERE sku = :sku
            self.available[sku] = value
            yield "update"

        def decrement_if_available(self, sku, quantity):
            # UPDATE inventory SET available = available - :quantity
            #  WHERE sku = :sku AND available >= :quantity RETURNING available
            remaining = None
            if self.available.get(sku, 0) >= quantity:
                self.available[sku] -= quantity
                remaining = self.available[sku]
            yield "conditional-update"
            return remaining

        def insert_reservation(self, order_id, sku, quantity):
            # INSERT INTO reservations (order_id, sku, quantity) VALUES (...)
            self.reservations.append({"order_id": order_id, "sku": sku, "quantity": quantity})
            yield "insert"


    def reserve(db, alerts, request):
        """Reserve stock for one order and return "reserved" or "rejected"."""
        sku, quantity = request["sku"], request["quantity"]
        if quantity <= 0:
            return "rejected"
        # Read first so the low-stock event can report the remaining quantity.
        available = yield from db.select_available(sku)
        if available < quantity:
            return "rejected"
        remaining = available - quantity
        yield from db.update_available(sku, remaining)
        yield from db.insert_reservation(request["order_id"], sku, quantity)
        if remaining <= LOW_STOCK_THRESHOLD:
            alerts.setdefault(sku, []).append(remaining)
        return "reserved"


    def run(db, alerts, requests, schedule):
        """Interleave concurrent requests the way the launch traffic did.

        Each schedule entry resumes that request until its next database round trip. Requests
        that are still running afterwards finish one at a time, in arrival order.
        """
        workers = {request["id"]: reserve(db, alerts, request) for request in requests}
        outcomes = {}

        def step(request_id):
            if request_id in outcomes or request_id not in workers:
                return
            try:
                next(workers[request_id])
            except StopIteration as finished:
                outcomes[request_id] = finished.value

        for request_id in schedule:
            step(request_id)
        for request in requests:
            while request["id"] not in outcomes:
                step(request["id"])
        return outcomes


    def solve(data):
        db = InventoryDatabase(data["stock"])
        alerts = {}
        outcomes = run(db, alerts, data["requests"], data.get("schedule", []))
        reserved_units = {}
        for row in db.reservations:
            reserved_units[row["sku"]] = reserved_units.get(row["sku"], 0) + row["quantity"]
        return {
            "state": {
                "available": dict(sorted(db.available.items())),
                "reserved_units": dict(sorted(reserved_units.items())),
                "reservations": len(db.reservations),
                "rejected": sum(1 for outcome in outcomes.values() if outcome == "rejected"),
            },
            "low_stock_alerts": {sku: sorted(values, reverse=True) for sku, values in sorted(alerts.items())},
        }
''')

SOLUTION = STARTER.replace('''    # Read first so the low-stock event can report the remaining quantity.
    available = yield from db.select_available(sku)
    if available < quantity:
        return "rejected"
    remaining = available - quantity
    yield from db.update_available(sku, remaining)
''', '''    # One conditional statement checks and decrements together, so no other request can change
    # the row between the check and the write. Its RETURNING value feeds the low-stock event.
    remaining = yield from db.decrement_if_available(sku, quantity)
    if remaining is None:
        return "rejected"
''')
assert SOLUTION != STARTER


def _request(number, order, quantity, sku="SKU-CONSOLE"):
    return {"id": f"r{number}", "order_id": order, "sku": sku, "quantity": quantity}


def _state(available, reserved_units, reservations, rejected, alerts):
    return {"state": {"available": available, "reserved_units": reserved_units, "reservations": reservations,
                      "rejected": rejected}, "low_stock_alerts": alerts}


TESTS = [
    case("Sequential checkout",
         {"stock": {"SKU-CONSOLE": 10}, "requests": [_request(1, "o-1001", 4), _request(2, "o-1002", 4)],
          "schedule": []},
         _state({"SKU-CONSOLE": 2}, {"SKU-CONSOLE": 8}, 2, 0, {"SKU-CONSOLE": [2]})),
    case("Two buyers race for the last units",
         {"stock": {"SKU-CONSOLE": 10}, "requests": [_request(1, "o-2001", 6), _request(2, "o-2002", 6)],
          "schedule": ["r1", "r2"]},
         _state({"SKU-CONSOLE": 4}, {"SKU-CONSOLE": 6}, 1, 1, {"SKU-CONSOLE": [4]}),
         assertions=[{"path": "state.reserved_units.SKU-CONSOLE", "equals": 6},
                     {"path": "state.available.SKU-CONSOLE", "equals": 4}]),
    case("Flash-sale burst",
         {"stock": {"SKU-CONSOLE": 10}, "requests": [_request(n, f"o-30{n:02d}", 3) for n in range(1, 11)],
          "schedule": [f"r{n}" for n in range(1, 11)]},
         _state({"SKU-CONSOLE": 1}, {"SKU-CONSOLE": 9}, 3, 7, {"SKU-CONSOLE": [4, 1]}),
         assertions=[{"path": "state.reservations", "equals": 3}]),
    case("Two SKUs interleaved",
         {"stock": {"SKU-A": 5, "SKU-B": 2},
          "requests": [_request(1, "o-4001", 2, "SKU-A"), _request(2, "o-4002", 2, "SKU-B"),
                       _request(3, "o-4003", 2, "SKU-A"), _request(4, "o-4004", 2, "SKU-B"),
                       _request(5, "o-4005", 2, "SKU-A")],
          "schedule": ["r1", "r2", "r3", "r4", "r5"]},
         _state({"SKU-A": 1, "SKU-B": 0}, {"SKU-A": 4, "SKU-B": 2}, 3, 2, {"SKU-A": [3, 1], "SKU-B": [0]}),
         True),
    case("Invalid quantities and unknown SKU",
         {"stock": {"SKU-CONSOLE": 3},
          "requests": [_request(1, "o-5001", 0), _request(2, "o-5002", -2), _request(3, "o-5003", 1, "SKU-GHOST"),
                       _request(4, "o-5004", 1)],
          "schedule": ["r1", "r2", "r3", "r4"]},
         _state({"SKU-CONSOLE": 2}, {"SKU-CONSOLE": 1}, 1, 3, {"SKU-CONSOLE": [2]}), True),
    case("Exactly enough for both racers",
         {"stock": {"SKU-CONSOLE": 6}, "requests": [_request(1, "o-6001", 3), _request(2, "o-6002", 3)],
          "schedule": ["r1", "r2"]},
         _state({"SKU-CONSOLE": 0}, {"SKU-CONSOLE": 6}, 2, 0, {"SKU-CONSOLE": [3, 0]}), True,
         [{"path": "state.available.SKU-CONSOLE", "equals": 0}]),
    case("Late writer overwrites a newer value",
         {"stock": {"SKU-CONSOLE": 10}, "requests": [_request(1, "o-7001", 2), _request(2, "o-7002", 5)],
          "schedule": ["r1", "r2", "r2", "r2"]},
         _state({"SKU-CONSOLE": 3}, {"SKU-CONSOLE": 7}, 2, 0, {"SKU-CONSOLE": [3]}), True),
    case("Oversized order is rejected",
         {"stock": {"SKU-CONSOLE": 4}, "requests": [_request(1, "o-8001", 5), _request(2, "o-8002", 4)],
          "schedule": ["r1", "r2"]},
         _state({"SKU-CONSOLE": 0}, {"SKU-CONSOLE": 4}, 1, 1, {"SKU-CONSOLE": [0]}), True),
    case("No requests", {"stock": {"SKU-CONSOLE": 4}, "requests": [], "schedule": []},
         _state({"SKU-CONSOLE": 4}, {}, 0, 0, {}), True),
]


def _reservation_logs():
    """Launch logs: 47 accepted reservations against 40 units, with lost decrements."""
    # (seconds after launch, order suffix, available read, trace id) for a representative sample.
    accepted = [
        (0.104, 101, 40, "t-7c01"), (0.106, 102, 40, "t-7c02"), (0.109, 103, 40, "t-7c03"),
        (0.231, 104, 39, "t-7c04"), (0.698, 105, 38, None), (0.702, 106, 38, None),
        (31.442, 121, 27, None), (58.910, 133, 17, "t-7c33"), (58.913, 134, 17, "t-7c34"),
        (117.201, 141, 6, None), (117.640, 142, 5, None), (117.644, 143, 5, None),
        (117.880, 145, 4, None), (117.983, 146, 3, None), (118.002, 147, 1, "t-7c47"),
    ]
    entries = [
        log("2026-04-18T09:41:07.552Z", "INFO", "inventory-service", "service started",
            version="2026.04.18-1", low_stock_events=True, pool_size=20),
        log("2026-04-18T09:58:00.019Z", "INFO", "storefront-api", "availability cache warmed",
            sku=SKU, availability="in_stock", ttl_seconds=30),
    ]
    for seconds, suffix, available, trace_id in accepted:
        remaining = available - 1
        entries.append(log(ts(SALE, seconds), "INFO", "inventory-service", "reservation accepted", trace_id,
                           order_id=f"o-77{suffix}", sku=SKU, quantity=1, read_available=available,
                           remaining=remaining))
        if remaining <= 5:
            entries.append(log(ts(SALE, seconds + 0.004), "INFO", "inventory-service", "low-stock event published",
                               trace_id, sku=SKU, remaining=remaining))
    entries += [
        log(ts(SALE, 0.233), "WARN", "inventory-db", "slow statement", None, duration_ms=41,
            statement="SELECT available FROM inventory WHERE sku = $1"),
        log(ts(SALE, 45.1), "WARN", "inventory-db", "slow statement", None, duration_ms=38,
            statement="UPDATE inventory SET available = $1 WHERE sku = $2"),
        log(ts(SALE, 118.4), "INFO", "inventory-service", "reservation rejected: insufficient stock", "t-7c51",
            order_id="o-77151", sku=SKU, quantity=1, read_available=0),
        log(ts(SALE, 121.0), "INFO", "storefront-api", "availability served from cache", None, sku=SKU,
            availability="in_stock", cache_age_seconds=24),
        log("2026-04-18T10:06:00.311Z", "WARN", "reconciliation-job", "reserved units exceed allocation", None,
            sku=SKU, allocation=40, reserved_units=47, available=0),
        log("2026-04-18T10:12:04.870Z", "ERROR", "fulfillment-worker", "pick failed: INSUFFICIENT_STOCK", "t-9f31",
            order_id="o-77141", warehouse="FRA-2"),
        log("2026-04-18T10:12:05.102Z", "ERROR", "fulfillment-worker", "pick failed: INSUFFICIENT_STOCK", None,
            order_id="o-77145", warehouse="FRA-2"),
        log("2026-04-18T10:15:00.000Z", "INFO", "storefront-api", "feature flag changed", None,
            flag="sale.console_le.enabled", value=False),
    ]
    return sorted(entries, key=lambda entry: entry["ts"])


def _reservation_trace(trace_id, offset, order_suffix):
    return {"trace_id": trace_id, "spans": [
        span(f"{trace_id}-1", None, "storefront-api", "POST /checkout/reserve", offset, 24.0,
             order_id=f"o-77{order_suffix}"),
        span(f"{trace_id}-2", f"{trace_id}-1", "inventory-service", "reserve", offset + 1, 21.0, sku=SKU),
        span(f"{trace_id}-3", f"{trace_id}-2", "inventory-db", "SELECT available FROM inventory", offset + 2, 3.1,
             **{"db.rows": 1, "inventory.available": 40}),
        span(f"{trace_id}-4", f"{trace_id}-2", "inventory-db", "UPDATE inventory SET available = $1", offset + 9, 4.2,
             **{"db.params.available": 39, "db.rows_affected": 1}),
        span(f"{trace_id}-5", f"{trace_id}-2", "inventory-db", "INSERT INTO reservations", offset + 15, 2.8,
             **{"db.rows_affected": 1}),
        span(f"{trace_id}-6", f"{trace_id}-2", "inventory-service", "publish reservation event", offset + 19, 1.6),
    ]}


ARTIFACTS = [
    artifact("inventory-logs", "logs", "Launch logs (inventory, storefront, fulfillment)",
             "Structured logs from 09:40 to 10:15 UTC. Sampled reservation logs; every accepted reservation is "
             "logged with the stock it read and the remaining stock it wrote.",
             {"entries": _reservation_logs()}),
    artifact("launch-metrics", "metrics", "Launch dashboard",
             "Five-minute buckets. Reservations are counted when inserted; inventory is the stored row value.",
             {"series": [
                 series("inventory_available{sku=SKU-CONSOLE-LE}", "units", "2026-04-18T09:30:00Z", 5,
                        [40, 40, 40, 40, 40, 40, 40, 0, 0, 0, 0, 0]),
                 series("reservations_accepted{sku=SKU-CONSOLE-LE}", "count per 5 min", "2026-04-18T09:30:00Z", 5,
                        [0, 0, 0, 0, 0, 0, 47, 0, 0, 0, 0, 0]),
                 series("fulfillment_pick_failures", "count per 5 min", "2026-04-18T09:30:00Z", 5,
                        [0, 0, 0, 0, 0, 0, 0, 0, 7, 0, 0, 0]),
                 series("inventory_db_statement_latency_p95", "ms", "2026-04-18T09:30:00Z", 5,
                        [4, 4, 4, 5, 4, 4, 38, 6, 5, 4, 4, 4]),
             ],
              "annotations": [{"at": "2026-04-18T09:40:00Z", "label": "Deploy inventory-service 2026.04.18-1"},
                              {"at": SALE, "label": "Launch opens"},
                              {"at": "2026-04-18T10:15:00Z", "label": "Launch paused"}]}),
    artifact("reservation-traces", "traces", "Two reservations 2 ms apart",
             "Traces t-7c01 and t-7c02 started 2 ms apart for the same SKU. Both completed with status ok. "
             "Trace t-9f31 is a later fulfillment pick.",
             {"traces": [
                 _reservation_trace("t-7c01", 0.0, 101),
                 _reservation_trace("t-7c02", 2.0, 102),
                 {"trace_id": "t-9f31", "spans": [
                     span("t-9f31-1", None, "fulfillment-worker", "pick order o-77141", 0.0, 412.0, "error",
                          order_id="o-77141"),
                     span("t-9f31-2", "t-9f31-1", "warehouse-api", "POST /picks", 3.0, 405.0, "error",
                          warehouse="FRA-2", error="INSUFFICIENT_STOCK", **{"http.status_code": 409}),
                 ]},
             ]}),
    artifact("inventory-db-snapshot", "database", "inventory-db after the launch",
             "Read-only snapshot taken at 10:20 UTC.",
             {"tables": [
                 {"name": "inventory", "columns": ["sku", "available", "updated_at"],
                  "rows": [[SKU, 0, "2026-04-18T10:01:58Z"], ["SKU-CTRL-PRO", 212, "2026-04-18T09:12:40Z"]]},
                 {"name": "reservations (grouped)",
                  "columns": ["sku", "reservations", "reserved_units", "first_reserved_at", "last_reserved_at"],
                  "rows": [[SKU, 47, 47, "2026-04-18T10:00:00Z", "2026-04-18T10:01:58Z"],
                           ["SKU-CTRL-PRO", 3, 4, "2026-04-18T08:51:10Z", "2026-04-18T10:04:31Z"]]},
                 {"name": "sale_allocations", "columns": ["sale", "sku", "allocated_units", "opens_at"],
                  "rows": [["console-le-launch", SKU, 40, SALE]]},
             ]}),
    text_artifact("inventory-config", "config", "inventory-service configuration",
                  "Deployed configuration at the time of the launch.", "deploy/inventory-service.yaml", "yaml", '''
service: inventory-service
version: 2026.04.18-1
database:
  host: inventory-db.internal
  port: 5432
  name: inventory
  isolation_level: read_committed
  pool_size: 20
low_stock:
  threshold: 5
  events_enabled: true        # new in 2026.04.18-1
storefront_cache:
  availability_ttl_seconds: 30
'''),
    artifact("deploy-2026-04-18-1", "diff", "Deploy 2026.04.18-1: low-stock events with remaining quantity",
             "Merged on 2026-04-17, deployed 2026-04-18 09:40 UTC.",
             {"title": "Emit low-stock events with the remaining quantity",
              "author": "dev-inventory-team", "content": '''
--- a/inventory/reservations.py
+++ b/inventory/reservations.py
@@ -41,12 +41,16 @@ def reserve(db, alerts, request):
     sku, quantity = request["sku"], request["quantity"]
     if quantity <= 0:
         return "rejected"
-    if (yield from db.decrement_if_available(sku, quantity)) is None:
-        return "rejected"
+    # Read first so the low-stock event can report the remaining quantity.
+    available = yield from db.select_available(sku)
+    if available < quantity:
+        return "rejected"
+    remaining = available - quantity
+    yield from db.update_available(sku, remaining)
     yield from db.insert_reservation(request["order_id"], sku, quantity)
+    if remaining <= LOW_STOCK_THRESHOLD:
+        alerts.setdefault(sku, []).append(remaining)
     return "reserved"
--- a/deploy/inventory-service.yaml
+++ b/deploy/inventory-service.yaml
@@ -9,3 +9,4 @@ database:
 low_stock:
   threshold: 5
+  events_enabled: true        # new in 2026.04.18-1
'''.strip("\n") + "\n"}),
    artifact("inventory-architecture", "architecture", "Reservation path",
             "Services involved in a launch reservation.",
             {"nodes": [
                 {"id": "storefront", "label": "storefront-api", "kind": "service"},
                 {"id": "availability-cache", "label": "availability cache (Redis)", "kind": "cache"},
                 {"id": "inventory", "label": "inventory-service", "kind": "service"},
                 {"id": "inventory-db", "label": "inventory-db (PostgreSQL)", "kind": "database"},
                 {"id": "order-events", "label": "order-events topic", "kind": "queue"},
                 {"id": "fulfillment", "label": "fulfillment-worker", "kind": "service"},
                 {"id": "warehouse", "label": "warehouse-api (FRA-2)", "kind": "external"},
             ], "edges": [
                 {"from": "storefront", "to": "availability-cache", "label": "availability reads, 30 s TTL"},
                 {"from": "storefront", "to": "inventory", "label": "POST /reservations"},
                 {"from": "inventory", "to": "inventory-db", "label": "SELECT / UPDATE / INSERT"},
                 {"from": "inventory", "to": "order-events", "label": "reservation and low-stock events"},
                 {"from": "order-events", "to": "fulfillment", "label": "consume"},
                 {"from": "fulfillment", "to": "warehouse", "label": "pick requests"},
             ]}),
    text_artifact("oversell-runbook", "runbook", "Oversell runbook",
                  "Operations runbook used by the on-call engineer.", "runbooks/oversell.md", "markdown", '''
# Oversell runbook

1. Pause the sale: set `sale.<name>.enabled=false`.
2. Compare `reservations` with `sale_allocations` and the warehouse count.
3. Cancel and refund reservations beyond the physical stock, newest first.
4. Notify support with the affected order IDs.
5. Open an incident review: every oversell must have a root cause, not only a reconciliation.
'''),
]

INCIDENT = {
    "slug": "inventory-reservation-race",
    "title": "Launch oversells a limited console allocation",
    "summary": "During a product launch, 47 orders were accepted for 40 units even though the inventory row "
               "never went negative. Seven customers paid for consoles that cannot ship.",
    "severity": "SEV-2",
    "level": 3,
    "category": "race_condition",
    "taxonomy": {"bug_categories": ["race_condition", "database_transactions", "state_corruption"],
                 "skills": ["concurrency_reasoning", "log_investigation", "state_inspection", "reproduction"]},
    "affected_services": ["inventory-service", "inventory-db", "fulfillment-worker", "storefront-api"],
    "impact": [
        "47 reservations were accepted against a 40-unit allocation; 7 orders cannot ship.",
        "Fulfillment failed 7 picks and support must cancel and refund those orders.",
        "The inventory row looked healthy throughout the launch, which delayed detection.",
    ],
    "expected_behavior": "Each reservation decrements stock exactly once, and the service never accepts more "
                         "units than the allocation, however requests interleave.",
    "observed_symptoms": [
        "The reconciliation job reports 47 reserved units for a 40-unit allocation.",
        "Several 'reservation accepted' logs report the same remaining stock.",
        "inventory-db p95 statement latency rose from 4 ms to 38 ms at launch.",
        "The storefront kept showing 'in stock' for up to 30 seconds after the SKU sold out.",
    ],
    "objective": "Find why reservations exceeded the allocation, fix reserve() so its check and decrement "
                 "cannot interleave, and keep the low-stock events accurate.",
    "timeline": [
        event("2026-04-18T09:40:00Z", "deploy", "inventory-service 2026.04.18-1",
              "Adds low-stock events that report the remaining quantity, for the launch dashboard."),
        event("2026-04-18T09:58:00Z", "note", "Availability cache pre-warmed",
              "SKU-CONSOLE-LE marked in stock; 40 units allocated to the launch."),
        event(SALE, "symptom", "Launch opens", "Reservation traffic peaks at about 1,900 requests per minute."),
        event("2026-04-18T10:00:45Z", "alert", "inventory-db p95 latency 38 ms",
              "Latency alert during the launch peak. CPU 41%; no lock waits or errors reported."),
        event("2026-04-18T10:01:58Z", "symptom", "Inventory reaches zero",
              "The storefront switches the SKU to sold out after its 30-second availability cache expires."),
        event("2026-04-18T10:06:00Z", "alert", "Reconciliation: reserved units exceed allocation",
              "47 units reserved against a 40-unit allocation."),
        event("2026-04-18T10:12:00Z", "symptom", "Seven picks fail",
              "fulfillment-worker reports INSUFFICIENT_STOCK for 7 orders at warehouse FRA-2."),
        event("2026-04-18T10:15:00Z", "action", "Launch paused", "Feature flag sale.console_le.enabled set to false."),
        event("2026-04-18T10:25:00Z", "action", "Availability cache TTL lowered to 5 s",
              "No effect on the oversell: all 47 reservations were accepted by inventory-service itself."),
        event("2026-04-18T10:40:00Z", "note", "Customer impact",
              "Support begins contacting the seven customers whose orders cannot ship."),
    ],
    "artifacts": ARTIFACTS,
    "scenarios": [
        {"id": "sequential-baseline", "name": "Sequential checkout",
         "description": "Two orders that never overlap. The service behaves correctly here.",
         "tests": ["Sequential checkout"]},
        {"id": "concurrent-last-units", "name": "Two buyers race for the last units",
         "description": "Both requests read the stock before either one writes.",
         "tests": ["Two buyers race for the last units"]},
        {"id": "launch-burst", "name": "Flash-sale burst",
         "description": "Ten buyers read the stock at once, like the launch peak.", "tests": ["Flash-sale burst"]},
    ],
    "rubric": {
        "version": 1, "source": "authored",
        "defect_categories": ["race_condition"],
        "related_categories": ["database_transactions", "state_corruption"],
        "root_cause": [
            ["read-modify-write", "read then write", "select then update", "check-then-act", "check then act",
             "stale read", "stale value", "read the stock"],
            ["lost update", "lost updates", "overwrite", "overwrites", "overwrote", "overwritten"],
            ["concurrent", "concurrently", "interleave", "interleaving", "simultaneous", "parallel", "race"],
            ["not atomic", "non-atomic", "atomic", "separate statements", "two statements", "round trip",
             "between the read and the write"],
        ],
        "component": ["reserve", "select_available", "update_available", "InventoryDatabase"],
        "invariant": [
            ["never exceed", "cannot exceed", "not exceed", "at most", "no more than", "never negative"],
            ["stock", "inventory", "available units", "allocation"],
            ["reserved", "reservations", "sold"],
        ],
        "correction": [
            ["atomic", "atomically", "single statement", "conditional update", "decrement_if_available",
             "compare-and-set", "compare and set", "select for update", "row lock", "lock"],
            ["where available >=", "guard", "condition", "check and decrement", "check and update together"],
            ["returning", "returned remaining", "remaining from the update", "returned value"],
        ],
        "reproduction": [
            ["concurrent", "simultaneous", "two requests", "parallel", "interleave", "schedule", "at once"],
            ["same sku", "same item", "last units", "limited stock", "low stock", "few units"],
            ["reserved units", "oversold", "more than stock", "exceeds stock", "exceed the stock", "count"],
        ],
    },
    "evaluation": {
        "remediation_concepts": [
            ["pause", "disable", "feature flag", "stop the sale"],
            ["reconcile", "compare reservations", "audit", "count reservations"],
            ["cancel", "refund", "notify customers", "contact customers", "backorder"],
            ["hotfix", "deploy the fix", "rollback", "revert"],
        ],
        "prevention_concepts": [
            ["concurrency test", "race test", "concurrent test", "load test", "stress test"],
            ["constraint", "check constraint", "available >= 0", "database constraint"],
            ["atomic", "conditional update", "single statement"],
            ["review", "checklist"],
            ["reconciliation", "monitor", "alert"],
        ],
        "impact_concepts": [
            ["oversold", "oversell", "more orders than stock", "47", "seven"],
            ["customers", "orders"],
            ["fulfillment", "pick", "cannot ship", "cancellation"],
            ["refund", "revenue", "support", "trust"],
        ],
    },
    "problem": {
        "title": "Incident: the launch that sold 47 of 40 consoles",
        "summary": "Concurrent reservations both pass the stock check and the later write overwrites the earlier "
                   "one. Reproduce the interleaving and make reservations safe for every schedule.",
        "category": "business",
        "difficulty": "hard",
        "tags": ["concurrency", "atomicity", "inventory", "transactions"],
        "requirements": [
            "Input has stock per SKU, requests {id, order_id, sku, quantity} in arrival order, and a schedule of "
            "request ids.",
            "Each schedule entry resumes that request until its next database round trip; requests still running "
            "afterwards finish one at a time in arrival order. Every statement is a round trip — keep the yields.",
            "Reserve a positive quantity only if that many units are still available; otherwise reject the request "
            "and leave inventory unchanged.",
            "For every interleaving, reserved plus available units equal the starting stock, and available units "
            "never go below zero.",
            "Return {state: {available, reserved_units, reservations, rejected}, low_stock_alerts}. A low-stock "
            "alert records the units left (5 or fewer) after a reservation, listed per SKU from highest to lowest.",
        ],
        "starters": {"python": STARTER},
        "solutions": {"python": SOLUTION},
        "tests": TESTS,
        "explanation": "reserve() read the available units and wrote back available - quantity in a separate "
                       "statement. Requests that read before either write both pass the check, and the later "
                       "write overwrites the earlier one, so a decrement is lost and reservations exceed the "
                       "stock while the inventory row still looks healthy. One conditional statement (UPDATE ... "
                       "WHERE available >= :quantity RETURNING available) checks and decrements together, and its "
                       "returned value keeps the low-stock event accurate. Time O(n) per schedule, space O(n).",
        "hints": [
            "Two buyers can both see enough stock before either one writes. What does each request assume between "
            "its read and its write?",
            "Compare the reservations with the inventory row after the race. Which statement makes one buyer's "
            "decrement disappear?",
            "The check and the decrement are separate round trips, so a stale read overwrites a newer value. Use one "
            "conditional decrement that returns the remaining units, and alert from that value.",
        ],
        "minutes": 40,
    },
}
