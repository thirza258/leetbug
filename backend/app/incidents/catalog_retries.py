"""Incident: nested retries turn a 4-minute database failover into a 50-minute outage (retry amplification, level 3)."""
from app.catalog import case, code
from app.incidents.catalog_common import artifact, event, log, series, span, text_artifact

STARTER = code('''
    GATEWAY_ATTEMPTS = 3
    CHECKOUT_ATTEMPTS = 3


    class ServiceError(Exception):
        status = 500


    class RetryableError(ServiceError):
        """Transient failure: the same call may succeed if it is repeated."""


    class DependencyTimeout(RetryableError):
        status = 504


    class DependencyUnavailable(RetryableError):
        status = 503


    class Conflict(ServiceError):
        status = 409


    class BadRequest(ServiceError):
        status = 400


    class RetriesExhausted(ServiceError):
        """Terminal failure: the caller already retried, so outer layers must not retry again."""

        def __init__(self, cause):
            super().__init__(str(cause))
            self.status = cause.status


    def with_retries(operation, attempts):
        """Shared helper from the resilience library, used by every service."""
        last_error = None
        for _ in range(attempts):
            try:
                return operation()
            except ServiceError as error:
                last_error = error
        # Re-raise the original error so callers can map it to the right HTTP status.
        raise last_error


    class InventoryService:
        def __init__(self, outcomes, after_script):
            self.outcomes = list(outcomes)
            self.after_script = after_script
            self.calls = 0

        def reserve(self, request):
            self.calls += 1
            outcome = self.outcomes.pop(0) if self.outcomes else self.after_script
            if outcome == "timeout":
                raise DependencyTimeout("inventory did not answer within 300 ms")
            if outcome == "unavailable":
                raise DependencyUnavailable("inventory is unavailable")
            if outcome == "conflict":
                raise Conflict(f"insufficient stock for {request['sku']}")
            return {"sku": request["sku"], "quantity": request["quantity"]}


    class CheckoutService:
        def __init__(self, inventory):
            self.inventory = inventory
            self.calls = 0

        def place_order(self, request):
            self.calls += 1
            if request["quantity"] <= 0:
                raise BadRequest("quantity must be positive")
            return with_retries(lambda: self.inventory.reserve(request), CHECKOUT_ATTEMPTS)


    class EdgeGateway:
        def __init__(self, checkout):
            self.checkout = checkout

        def handle(self, request):
            try:
                with_retries(lambda: self.checkout.place_order(request), GATEWAY_ATTEMPTS)
                return 200
            except ServiceError as error:
                return error.status


    def solve(data):
        inventory = InventoryService(data.get("inventory", []), data.get("after_script", "ok"))
        checkout = CheckoutService(inventory)
        gateway = EdgeGateway(checkout)
        statuses = [gateway.handle(request) for request in data["requests"]]
        return {"statuses": statuses, "calls": {"checkout": checkout.calls, "inventory": inventory.calls}}
''')

SOLUTION = STARTER.replace('''    """Shared helper from the resilience library, used by every service."""
    last_error = None
    for _ in range(attempts):
        try:
            return operation()
        except ServiceError as error:
            last_error = error
    # Re-raise the original error so callers can map it to the right HTTP status.
    raise last_error
''', '''    """Shared helper from the resilience library, used by every service.

    Only transient failures are retried. When the attempts run out, a terminal RetriesExhausted
    (carrying the last status) tells callers further out not to multiply the retries.
    """
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except RetryableError as error:
            if attempt == attempts:
                raise RetriesExhausted(error) from error
''')
assert SOLUTION != STARTER


def _request(number, quantity=1, sku="SKU-100"):
    return {"id": f"r{number}", "sku": sku, "quantity": quantity}


def _result(statuses, checkout, inventory):
    return {"statuses": statuses, "calls": {"checkout": checkout, "inventory": inventory}}


TESTS = [
    case("Transient timeout recovers",
         {"requests": [_request(1)], "inventory": ["timeout", "ok"], "after_script": "ok"},
         _result([200], 1, 2)),
    case("Inventory outage",
         {"requests": [_request(1)], "inventory": [], "after_script": "timeout"},
         _result([504], 1, 3), assertions=[{"path": "calls.inventory", "equals": 3}]),
    case("Out of stock is not retried",
         {"requests": [_request(1, sku="SKU-SOLDOUT-7")], "inventory": [], "after_script": "conflict"},
         _result([409], 1, 1)),
    case("Invalid quantity is rejected once",
         {"requests": [_request(1, 0)], "inventory": [], "after_script": "ok"}, _result([400], 1, 0), True),
    case("Two blips, then success",
         {"requests": [_request(1)], "inventory": ["unavailable", "unavailable", "ok"], "after_script": "ok"},
         _result([200], 1, 3), True),
    case("Mixed traffic during an outage",
         {"requests": [_request(1), _request(2, 2), _request(3, 0), _request(4)],
          "inventory": ["timeout", "timeout", "timeout", "ok"], "after_script": "ok"},
         _result([504, 200, 400, 200], 4, 5), True),
    case("Unavailable outage",
         {"requests": [_request(1)], "inventory": [], "after_script": "unavailable"}, _result([503], 1, 3), True),
    case("Conflict after a timeout",
         {"requests": [_request(1)], "inventory": ["timeout", "conflict"], "after_script": "ok"},
         _result([409], 1, 2), True),
    case("No traffic", {"requests": [], "inventory": [], "after_script": "timeout"}, _result([], 0, 0), True),
    case("Recovery after the outage",
         {"requests": [_request(1), _request(2), _request(3)], "inventory": ["unavailable"] * 3, "after_script": "ok"},
         _result([503, 200, 200], 3, 5), True),
]

LOGS = sorted([
    log("2026-08-20T08:55:41.002Z", "INFO", "edge-gateway", "library upgraded", None, library="resilience",
        version="4.2.0"),
    log("2026-08-20T08:56:02.517Z", "INFO", "checkout-service", "library upgraded", None, library="resilience",
        version="4.2.0"),
    log("2026-08-20T09:40:12.110Z", "WARN", "checkout-service", "retrying inventory.reserve", "t-r010", attempt=2,
        error="Conflict", status=409, sku="SKU-SOLDOUT-7"),
    log("2026-08-20T09:40:12.121Z", "WARN", "checkout-service", "retrying inventory.reserve", "t-r010", attempt=3,
        error="Conflict", status=409, sku="SKU-SOLDOUT-7"),
    log("2026-08-20T09:40:12.130Z", "WARN", "edge-gateway", "retrying POST /checkout", "t-r010", attempt=2,
        error="Conflict", status=409),
    log("2026-08-20T09:40:12.162Z", "INFO", "edge-gateway", "request completed", "t-r010", status=409,
        inventory_calls=9),
    log("2026-08-20T11:03:00.000Z", "INFO", "inventory-db", "planned failover started", None,
        old_primary="inventory-db-1.internal", new_primary="inventory-db-2.internal"),
    log("2026-08-20T11:03:20.114Z", "WARN", "inventory-service", "database unavailable: failover in progress", None,
        pod="inventory-6c4f-2"),
    log("2026-08-20T11:03:24.402Z", "WARN", "checkout-service", "retrying inventory.reserve", "t-r100", attempt=2,
        error="DependencyTimeout", status=504),
    log("2026-08-20T11:03:24.705Z", "WARN", "checkout-service", "retrying inventory.reserve", "t-r100", attempt=3,
        error="DependencyTimeout", status=504),
    log("2026-08-20T11:03:25.008Z", "WARN", "edge-gateway", "retrying POST /checkout", "t-r100", attempt=2,
        error="DependencyTimeout", status=504),
    log("2026-08-20T11:03:25.912Z", "WARN", "edge-gateway", "retrying POST /checkout", "t-r100", attempt=3,
        error="DependencyTimeout", status=504),
    log("2026-08-20T11:03:26.816Z", "ERROR", "edge-gateway", "request failed", "t-r100", status=504,
        inventory_calls=9, duration_ms=2714),
    log("2026-08-20T11:05:00.000Z", "WARN", "inventory-service", "request queue full", None, queue_depth=2048,
        cpu_percent=100, pod="inventory-6c4f-4"),
    log("2026-08-20T11:07:10.250Z", "INFO", "inventory-db", "failover complete", None,
        primary="inventory-db-2.internal", replication_lag_ms=0),
    log("2026-08-20T11:08:30.000Z", "INFO", "autoscaler", "scaled inventory-service", None, replicas_from=6,
        replicas_to=12),
    log("2026-08-20T11:12:30.000Z", "INFO", "autoscaler", "scaled inventory-service", None, replicas_from=12,
        replicas_to=24),
    log("2026-08-20T11:13:02.771Z", "ERROR", "inventory-db",
        "FATAL: remaining connection slots are reserved for superuser connections", None, connections=500),
    log("2026-08-20T11:20:00.000Z", "INFO", "inventory-db", "parameter changed", None, max_connections="500 -> 800"),
    log("2026-08-20T11:33:41.090Z", "WARN", "inventory-service", "request queue full", None, queue_depth=2048,
        cpu_percent=100, pod="inventory-6c4f-19"),
    log("2026-08-20T11:41:00.000Z", "INFO", "support", "ticket summary", None,
        note="sold-out items answer 'please try again' instead of 'sold out'"),
    log("2026-08-20T11:54:00.000Z", "INFO", "edge-gateway", "configuration reloaded", None, retry_max_attempts=1),
    log("2026-08-20T11:58:30.500Z", "INFO", "inventory-service", "queue drained", None, queue_depth=0,
        cpu_percent=38),
    log("2026-08-20T12:10:00.000Z", "INFO", "statuspage", "incident resolved", None),
], key=lambda entry: entry["ts"])


def _attempt_spans(trace_id, gateway_attempt, start, inventory_duration, status, error):
    """One gateway attempt: a checkout call with three inventory calls under it."""
    checkout_id = f"{trace_id}-c{gateway_attempt}"
    spans = [span(checkout_id, f"{trace_id}-g", "checkout-service", "place_order", start,
                  3 * (inventory_duration + 1) + 1, "error", attempt=gateway_attempt)]
    for call in range(3):
        spans.append(span(f"{trace_id}-c{gateway_attempt}-i{call + 1}", checkout_id, "inventory-service", "reserve",
                          start + 1 + call * (inventory_duration + 1), inventory_duration, "error",
                          attempt=call + 1, error=error, **{"http.status_code": status}))
    return spans


def _nested_trace(trace_id, inventory_duration, status, error):
    attempt_duration = 3 * (inventory_duration + 1) + 1
    spans = [span(f"{trace_id}-g", None, "edge-gateway", "POST /checkout", 0, 3 * attempt_duration + 2, "error",
                  **{"http.status_code": status})]
    for attempt in range(3):
        spans += _attempt_spans(trace_id, attempt + 1, 1 + attempt * attempt_duration, inventory_duration, status,
                                error)
    return {"trace_id": trace_id, "spans": spans}


START = "2026-08-20T08:30:00Z"
ARTIFACTS = [
    artifact("retry-logs", "logs", "Gateway, checkout, inventory and database logs",
             "Logs from 08:55 to 12:10 UTC.", {"entries": LOGS}),
    artifact("retry-metrics", "metrics", "Checkout path dashboard", "Ten-minute averages.", {
        "series": [
            series("edge_requests_per_second", "requests/s", START, 10,
                   [380, 385, 390, 396, 401, 399, 402, 405, 398, 400, 403, 401, 402, 398, 405, 401, 392, 395, 400,
                    398, 401, 404, 400, 399]),
            series("inventory_requests_per_second", "requests/s", START, 10,
                   [381, 386, 392, 430, 437, 433, 438, 441, 432, 436, 440, 435, 437, 433, 440, 2310, 3590, 3580,
                    3600, 3575, 2180, 452, 441, 438]),
            series("inventory_cpu", "percent", START, 10,
                   [33, 33, 34, 35, 36, 35, 35, 36, 35, 35, 36, 35, 35, 35, 36, 79, 100, 100, 100, 100, 92, 39, 36,
                    35]),
            series("edge_504_ratio", "percent", START, 10,
                   [0.1, 0.1, 0.2, 0.2, 0.2, 0.1, 0.2, 0.2, 0.1, 0.2, 0.2, 0.2, 0.1, 0.2, 0.2, 41.0, 60.2, 59.4, 60.8,
                    59.9, 31.5, 0.4, 0.2, 0.2]),
        ],
        "annotations": [
            {"at": "2026-08-20T08:55:00Z", "label": "resilience 4.2.0 rolled out"},
            {"at": "2026-08-20T11:03:00Z", "label": "inventory-db failover starts"},
            {"at": "2026-08-20T11:07:00Z", "label": "Failover complete"},
            {"at": "2026-08-20T11:54:00Z", "label": "Gateway retries disabled"},
        ]}),
    artifact("retry-traces", "traces", "One request during the outage and one sold-out request",
             "t-r100 is a checkout during the failover; t-r010 is a sold-out item at 09:40.", {"traces": [
                 _nested_trace("t-r100", 300, 504, "DependencyTimeout"),
                 _nested_trace("t-r010", 3, 409, "Conflict"),
             ]}),
    artifact("retry-counters", "database", "Request counters and database connections",
             "Per-minute counters from the request-accounting table, and inventory-db connection counts.",
             {"tables": [
                 {"name": "request_counts (per minute)",
                  "columns": ["minute", "edge_requests", "checkout_calls", "inventory_calls"],
                  "rows": [["2026-08-20T08:50:00Z", 23890, 23890, 23940],
                           ["2026-08-20T11:02:00Z", 24030, 24100, 26210],
                           ["2026-08-20T11:04:00Z", 23950, 71580, 214900],
                           ["2026-08-20T11:10:00Z", 23880, 71400, 214100],
                           ["2026-08-20T11:56:00Z", 24060, 24300, 72500],
                           ["2026-08-20T12:00:00Z", 24010, 24050, 26900]]},
                 {"name": "inventory-db connections", "columns": ["time", "connections", "max_connections"],
                  "rows": [["2026-08-20T11:02:00Z", 120, 500], ["2026-08-20T11:08:00Z", 310, 500],
                           ["2026-08-20T11:13:00Z", 500, 500], ["2026-08-20T11:20:00Z", 640, 800],
                           ["2026-08-20T12:05:00Z", 130, 800]]},
             ]}),
    text_artifact("retry-config", "config", "Retry and autoscaling settings", "Deployed configuration.",
                  "deploy/checkout-path.yaml", "yaml", '''
edge-gateway:
  resilience: 4.2.0
  retry:
    max_attempts: 3          # set to 1 at 11:54 UTC
    backoff_ms: 50
checkout-service:
  resilience: 4.2.0
  retry:
    max_attempts: 3
    backoff_ms: 50
  inventory_timeout_ms: 300
inventory-service:
  autoscaling:
    min_replicas: 6
    max_replicas: 24
    target_cpu_percent: 70
'''),
    artifact("resilience-4-2-0", "diff", "resilience 4.2.0: preserve the original error type",
             "Shared library release picked up by edge-gateway and checkout-service at 08:55 UTC.", {
                 "title": "Preserve the original error type when retries are exhausted", "author": "platform-team",
                 "content": '''
--- a/resilience/retry.py
+++ b/resilience/retry.py
@@ -12,10 +12,11 @@
 def with_retries(operation, attempts):
     """Shared helper from the resilience library, used by every service."""
-    for attempt in range(1, attempts + 1):
-        try:
-            return operation()
-        except RetryableError as error:
-            if attempt == attempts:
-                raise RetriesExhausted(error) from error
+    last_error = None
+    for _ in range(attempts):
+        try:
+            return operation()
+        except ServiceError as error:
+            last_error = error
+    # Re-raise the original error so callers can map it to the right HTTP status.
+    raise last_error
'''.strip("\n") + "\n"}),
    text_artifact("retry-guidelines", "runbook", "Engineering standard: retries",
                  "Internal guideline referenced by the resilience library.", "docs/standards/retries.md", "markdown", '''
# Retries

1. Retry only transient failures (timeouts, 503). Never retry 4xx responses such as 409.
2. Retry at one layer. A caller that receives "retries exhausted" must not retry again.
3. Every layer multiplies the attempts below it: 3 retries at two layers is 9 calls.
4. Bound total retry load with a budget and give up before the caller's deadline.
'''),
    artifact("checkout-architecture", "architecture", "Checkout path", "Synchronous call chain for checkout.", {
        "nodes": [
            {"id": "clients", "label": "web and mobile clients", "kind": "external"},
            {"id": "gateway", "label": "edge-gateway (retries x3)", "kind": "service"},
            {"id": "checkout", "label": "checkout-service (retries x3)", "kind": "service"},
            {"id": "inventory", "label": "inventory-service (6–24 pods)", "kind": "service"},
            {"id": "db", "label": "inventory-db (PostgreSQL primary + standby)", "kind": "database"},
            {"id": "autoscaler", "label": "autoscaler", "kind": "service"},
        ],
        "edges": [
            {"from": "clients", "to": "gateway", "label": "POST /checkout"},
            {"from": "gateway", "to": "checkout", "label": "place_order"},
            {"from": "checkout", "to": "inventory", "label": "reserve (300 ms timeout)"},
            {"from": "inventory", "to": "db", "label": "connections per pod"},
            {"from": "autoscaler", "to": "inventory", "label": "scale on CPU"},
        ]}),
]

INCIDENT = {
    "slug": "retry-amplification-storm",
    "title": "A four-minute failover becomes a fifty-minute outage",
    "summary": "A planned database failover caused a few minutes of timeouts, but checkout stayed down for nearly an "
               "hour while inventory received nine times its normal traffic.",
    "severity": "SEV-1",
    "level": 3,
    "category": "retry_idempotency",
    "taxonomy": {"bug_categories": ["retry_idempotency", "configuration", "distributed_consistency"],
                 "skills": ["dependency_analysis", "log_investigation", "performance_profiling", "reproduction"]},
    "affected_services": ["edge-gateway", "checkout-service", "inventory-service", "inventory-db"],
    "impact": [
        "About 60% of checkout requests failed with 504 for 51 minutes.",
        "Sold-out items answered 'please try again' instead of 'sold out' since the morning release.",
        "Autoscaling to 24 pods exhausted inventory-db connections and prolonged recovery.",
    ],
    "expected_behavior": "A transient inventory failure costs at most three inventory calls per checkout request, "
                         "and permanent errors such as 'out of stock' fail immediately.",
    "observed_symptoms": [
        "Inventory receives about nine calls per checkout request during the outage.",
        "inventory-service CPU stays at 100% long after the failover completed at 11:07.",
        "inventory-db rejects connections after the autoscaler adds pods.",
        "Even before the outage, inventory receives about 9% more calls than the gateway sends.",
    ],
    "objective": "Find why load stayed amplified after the database recovered, fix the shared retry helper, and "
                 "explain the safeguards that keep retries bounded.",
    "timeline": [
        event("2026-08-20T08:55:00Z", "deploy", "resilience 4.2.0",
              "Shared retry library upgraded in edge-gateway and checkout-service."),
        event("2026-08-20T09:40:00Z", "note", "Sold-out requests take longer",
              "A sold-out checkout makes 9 inventory calls before returning 409."),
        event("2026-08-20T11:03:00Z", "action", "Planned inventory-db failover", "Expected impact: under 5 minutes."),
        event("2026-08-20T11:04:00Z", "alert", "Edge 504 ratio above 40%", "Checkout requests time out."),
        event("2026-08-20T11:07:00Z", "note", "Failover complete", "The new primary is healthy; errors continue."),
        event("2026-08-20T11:08:00Z", "symptom", "Autoscaler adds inventory pods",
              "6 → 12 → 24 replicas; CPU stays at 100%."),
        event("2026-08-20T11:13:00Z", "alert", "inventory-db connection slots exhausted",
              "500 of 500 connections in use."),
        event("2026-08-20T11:20:00Z", "action", "max_connections raised to 800", "Connection errors stop; 504s continue."),
        event("2026-08-20T11:41:00Z", "note", "Support reports confusing errors",
              "Sold-out items show 'please try again' instead of 'sold out'."),
        event("2026-08-20T11:54:00Z", "action", "Gateway retries disabled",
              "edge-gateway retry.max_attempts set to 1; inventory traffic drops by two thirds."),
        event("2026-08-20T11:58:00Z", "symptom", "Inventory queue drains", "504 ratio returns to normal."),
    ],
    "artifacts": ARTIFACTS,
    "scenarios": [
        {"id": "transient-blip", "name": "Transient timeout recovers",
         "description": "One timeout, then success: retries must still help.", "tests": ["Transient timeout recovers"]},
        {"id": "dependency-down", "name": "Inventory outage",
         "description": "Every inventory call times out. Count the calls behind one request.",
         "tests": ["Inventory outage"]},
        {"id": "sold-out", "name": "Out of stock is not retried",
         "description": "A 409 is permanent.", "tests": ["Out of stock is not retried"]},
    ],
    "rubric": {
        "version": 1, "source": "authored",
        "defect_categories": ["retry_idempotency", "configuration"],
        "related_categories": ["distributed_consistency", "resource_leak"],
        "root_cause": [
            ["retry", "retries", "retrying", "with_retries"],
            ["every layer", "each layer", "nested", "multiple layers", "gateway and checkout", "both layers",
             "multiplied", "multiplies", "3 x 3", "3x3", "nine", "amplification", "amplify", "amplifies"],
            ["non-retryable", "not retryable", "conflict", "409", "bad request", "400", "client error",
             "all errors", "every error", "serviceerror"],
            ["exhausted", "exhaustion", "terminal", "gives up", "original error", "last error", "re-raise",
             "reraise", "retriesexhausted"],
        ],
        "component": ["with_retries", "RetriesExhausted", "RetryableError", "EdgeGateway", "CheckoutService"],
        "invariant": [
            ["at most", "bounded", "no more than", "limit", "cap"],
            ["attempts", "calls", "retries", "load"],
            ["per request", "each request", "user request", "per checkout"],
        ],
        "correction": [
            ["only retry", "retryableerror", "transient", "timeout and unavailable", "retryable errors"],
            ["terminal", "non-retryable", "retriesexhausted", "do not retry", "stop retrying", "don't retry"],
            ["one layer", "single layer", "innermost", "outer layer", "gateway"],
        ],
        "reproduction": [
            ["dependency down", "outage", "always times out", "timeout", "inventory down", "every call fails"],
            ["count calls", "call count", "number of calls", "inventory calls", "calls to inventory"],
            ["conflict", "409", "out of stock", "sold out", "bad request"],
        ],
    },
    "evaluation": {
        "remediation_concepts": [
            ["disable retries", "turn off retries", "reduce retries", "max_attempts"],
            ["rollback", "revert", "downgrade", "hotfix"],
            ["shed load", "rate limit", "circuit breaker", "throttle"],
            ["scale", "capacity", "connections", "drain"],
        ],
        "prevention_concepts": [
            ["retry budget", "budget"],
            ["backoff", "jitter"],
            ["circuit breaker"],
            ["test", "load test", "chaos", "fault injection", "game day"],
            ["one layer", "single layer", "deadline", "timeout budget"],
            ["alert", "monitor", "retry rate", "amplification"],
        ],
        "impact_concepts": [
            ["outage", "unavailable", "504", "timeouts", "failed"],
            ["checkout", "orders", "customers"],
            ["amplified", "nine times", "9x", "load", "storm"],
            ["duration", "minutes", "prolonged", "recovery", "51"],
        ],
    },
    "problem": {
        "title": "Incident: retries on top of retries",
        "summary": "Two layers retry the same failing call through a shared helper, multiplying load during an "
                   "outage and retrying permanent errors. Bound the retries without losing transient recovery.",
        "category": "system_design",
        "difficulty": "hard",
        "tags": ["retries", "resilience", "backoff", "configuration"],
        "requirements": [
            "Input has requests [{id, sku, quantity}] handled in order, and inventory: the scripted outcome of each "
            "call that reaches inventory-service (ok, timeout, unavailable, conflict). after_script is used once the "
            "script runs out.",
            "Only timeouts (504) and unavailable responses (503) are transient. Make at most 3 inventory attempts per "
            "user request in total; a request whose attempts run out fails with the last error's status.",
            "Conflicts (409) and invalid quantities (400) are never retried. A request is validated before inventory "
            "is called.",
            "Return {statuses, calls: {checkout, inventory}}: the HTTP status of every request and how many times "
            "each service was called.",
        ],
        "starters": {"python": STARTER},
        "solutions": {"python": SOLUTION},
        "tests": TESTS,
        "explanation": "with_retries() caught every ServiceError and, when its attempts ran out, re-raised the "
                       "original transient error. The gateway wraps checkout in the same helper, so it retried "
                       "requests that checkout had already retried three times: each request became nine inventory "
                       "calls, and conflicts and bad requests were retried as if they were transient. Retrying only "
                       "RetryableError and raising the terminal RetriesExhausted when attempts run out keeps retries "
                       "at one layer and caps the load at three calls per request, while a transient blip still "
                       "recovers. Time O(a) per request.",
        "hints": [
            "During the outage, inventory received far more calls than users sent requests. Count the calls behind "
            "one user request.",
            "Two layers use the same retry helper. What does the gateway see when checkout gives up, and which errors "
            "does the helper treat as retryable?",
            "with_retries retries every ServiceError and re-raises the transient error when attempts run out, so the "
            "outer layer retries again. Retry only RetryableError and raise a terminal RetriesExhausted at the end.",
        ],
        "minutes": 35,
    },
}
