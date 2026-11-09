"""Incident: provider timeouts plus client retries charge customers twice (idempotency, level 2)."""
from app.catalog import case, code
from app.incidents.catalog_common import artifact, event, log, series, span, text_artifact

STARTER = code('''
    class ProviderTimeout(Exception):
        """No response in time. The charge may or may not have been created."""


    class ProviderUnavailable(Exception):
        """CardFlow refused the request before creating a charge (HTTP 503)."""


    class PaymentProvider:
        """Stand-in for the CardFlow charges API.

        Charges are deduplicated by idempotency key: repeating a key returns the original charge
        instead of charging again. ``outcomes`` scripts how CardFlow handles each new charge
        request: "ok", "declined", "unavailable" (no charge), or "timeout_after_charge" (charged,
        but the response is lost).
        """

        def __init__(self, outcomes):
            self.outcomes = list(outcomes)
            self.charges = []
            self.by_key = {}

        def charge(self, idempotency_key, amount, reference):
            if idempotency_key in self.by_key:
                return {"status": "succeeded", "charge_id": self.by_key[idempotency_key]["charge_id"]}
            outcome = self.outcomes.pop(0) if self.outcomes else "ok"
            if outcome == "unavailable":
                raise ProviderUnavailable()
            if outcome == "declined":
                return {"status": "declined", "charge_id": None}
            charge = {"charge_id": f"ch_{len(self.charges) + 1:04d}", "reference": reference, "amount": amount}
            self.charges.append(charge)
            self.by_key[idempotency_key] = charge
            if outcome == "timeout_after_charge":
                raise ProviderTimeout()
            return {"status": "succeeded", "charge_id": charge["charge_id"]}


    class PaymentService:
        def __init__(self, provider):
            self.provider = provider
            self.payments = {}

        def process(self, payment, attempt):
            """Charge one order. payment["key"] is the order's idempotency key; attempt counts from 1."""
            key = payment["key"]
            record = self.payments.get(key)
            if record and record["status"] in ("succeeded", "declined"):
                return {"status": record["status"], "charge_id": record["charge_id"]}
            # Unique per attempt so support can tell retries apart in the provider dashboard.
            provider_key = f"{key}:{attempt}"
            try:
                result = self.provider.charge(provider_key, payment["amount"], reference=key)
            except ProviderTimeout:
                self.payments[key] = {"status": "unknown", "charge_id": None}
                return {"status": "timeout", "charge_id": None}
            except ProviderUnavailable:
                self.payments[key] = {"status": "failed", "charge_id": None}
                return {"status": "error", "charge_id": None}
            self.payments[key] = {"status": result["status"], "charge_id": result["charge_id"]}
            return {"status": result["status"], "charge_id": result["charge_id"]}


    def checkout(service, payment, max_attempts):
        """Storefront client: retries timeouts and provider errors with the same order key."""
        for attempt in range(1, max_attempts + 1):
            response = service.process(payment, attempt)
            if response["status"] not in ("timeout", "error"):
                return {**response, "attempts": attempt}
        return {**response, "attempts": max_attempts}


    def solve(data):
        provider = PaymentProvider(data.get("provider", []))
        service = PaymentService(provider)
        responses = [{"key": payment["key"], **checkout(service, payment, data.get("max_attempts", 3))}
                     for payment in data["payments"]]
        charged = {}
        for charge in provider.charges:
            charged[charge["reference"]] = charged.get(charge["reference"], 0) + charge["amount"]
        return {
            "responses": responses,
            "state": {
                "charges": provider.charges,
                "charged_by_order": dict(sorted(charged.items())),
                "payments": {key: record["status"] for key, record in sorted(service.payments.items())},
            },
        }
''')

SOLUTION = STARTER.replace('''        # Unique per attempt so support can tell retries apart in the provider dashboard.
        provider_key = f"{key}:{attempt}"
''', '''        # CardFlow deduplicates by this key, so it must be identical on every retry of the same
        # order. A per-attempt key turns a captured-but-timed-out charge into a second charge.
        provider_key = key
''')
assert SOLUTION != STARTER


def _payment(key, amount, customer="cus-0042"):
    return {"key": key, "customer": customer, "amount": amount}


def _charge(number, reference, amount):
    return {"charge_id": f"ch_{number:04d}", "reference": reference, "amount": amount}


def _response(key, status, charge_id, attempts):
    return {"key": key, "status": status, "charge_id": charge_id, "attempts": attempts}


TESTS = [
    case("Clean checkout",
         {"max_attempts": 3, "payments": [_payment("ord-1001", 4999)], "provider": ["ok"]},
         {"responses": [_response("ord-1001", "succeeded", "ch_0001", 1)],
          "state": {"charges": [_charge(1, "ord-1001", 4999)], "charged_by_order": {"ord-1001": 4999},
                    "payments": {"ord-1001": "succeeded"}}}),
    case("Timeout after the card was charged",
         {"max_attempts": 3, "payments": [_payment("ord-2001", 7500)], "provider": ["timeout_after_charge", "ok"]},
         {"responses": [_response("ord-2001", "succeeded", "ch_0001", 2)],
          "state": {"charges": [_charge(1, "ord-2001", 7500)], "charged_by_order": {"ord-2001": 7500},
                    "payments": {"ord-2001": "succeeded"}}},
         assertions=[{"path": "state.charged_by_order.ord-2001", "equals": 7500}]),
    case("Provider outage before charging",
         {"max_attempts": 3, "payments": [_payment("ord-3001", 2500)], "provider": ["unavailable", "ok"]},
         {"responses": [_response("ord-3001", "succeeded", "ch_0001", 2)],
          "state": {"charges": [_charge(1, "ord-3001", 2500)], "charged_by_order": {"ord-3001": 2500},
                    "payments": {"ord-3001": "succeeded"}}}),
    case("Repeated timeouts charge once",
         {"max_attempts": 3, "payments": [_payment("ord-4001", 1200)],
          "provider": ["timeout_after_charge", "timeout_after_charge", "timeout_after_charge"]},
         {"responses": [_response("ord-4001", "succeeded", "ch_0001", 2)],
          "state": {"charges": [_charge(1, "ord-4001", 1200)], "charged_by_order": {"ord-4001": 1200},
                    "payments": {"ord-4001": "succeeded"}}}, True),
    case("Same customer buys twice",
         {"max_attempts": 3, "payments": [_payment("ord-5001", 1999, "cus-0007"), _payment("ord-5002", 1999, "cus-0007")],
          "provider": ["ok", "ok"]},
         {"responses": [_response("ord-5001", "succeeded", "ch_0001", 1),
                        _response("ord-5002", "succeeded", "ch_0002", 1)],
          "state": {"charges": [_charge(1, "ord-5001", 1999), _charge(2, "ord-5002", 1999)],
                    "charged_by_order": {"ord-5001": 1999, "ord-5002": 1999},
                    "payments": {"ord-5001": "succeeded", "ord-5002": "succeeded"}}}, True),
    case("Double-click resubmits the same order",
         {"max_attempts": 3, "payments": [_payment("ord-6001", 3000), _payment("ord-6001", 3000)], "provider": ["ok"]},
         {"responses": [_response("ord-6001", "succeeded", "ch_0001", 1),
                        _response("ord-6001", "succeeded", "ch_0001", 1)],
          "state": {"charges": [_charge(1, "ord-6001", 3000)], "charged_by_order": {"ord-6001": 3000},
                    "payments": {"ord-6001": "succeeded"}}}, True),
    case("Decline is final",
         {"max_attempts": 3, "payments": [_payment("ord-7001", 9900)], "provider": ["declined"]},
         {"responses": [_response("ord-7001", "declined", None, 1)],
          "state": {"charges": [], "charged_by_order": {}, "payments": {"ord-7001": "declined"}}}, True),
    case("Timeout, then a new order",
         {"max_attempts": 3, "payments": [_payment("ord-8001", 1500), _payment("ord-8002", 2500)],
          "provider": ["timeout_after_charge", "ok"]},
         {"responses": [_response("ord-8001", "succeeded", "ch_0001", 2),
                        _response("ord-8002", "succeeded", "ch_0002", 1)],
          "state": {"charges": [_charge(1, "ord-8001", 1500), _charge(2, "ord-8002", 2500)],
                    "charged_by_order": {"ord-8001": 1500, "ord-8002": 2500},
                    "payments": {"ord-8001": "succeeded", "ord-8002": "succeeded"}}}, True),
    case("Outage on every attempt",
         {"max_attempts": 3, "payments": [_payment("ord-9001", 4200)],
          "provider": ["unavailable", "unavailable", "unavailable"]},
         {"responses": [_response("ord-9001", "error", None, 3)],
          "state": {"charges": [], "charged_by_order": {}, "payments": {"ord-9001": "failed"}}}, True),
    case("Outage, then a captured timeout",
         {"max_attempts": 3, "payments": [_payment("ord-9201", 6400)],
          "provider": ["unavailable", "timeout_after_charge", "ok"]},
         {"responses": [_response("ord-9201", "succeeded", "ch_0001", 3)],
          "state": {"charges": [_charge(1, "ord-9201", 6400)], "charged_by_order": {"ord-9201": 6400},
                    "payments": {"ord-9201": "succeeded"}}}, True),
]

LOGS = sorted([
    log("2026-05-06T13:10:44.208Z", "INFO", "payments-api", "service started", version="2026.05.06-2"),
    log("2026-05-06T13:02:31.410Z", "WARN", "payments-api", "provider timeout", "t-a050", order_id="ord-47710",
        attempt=1, provider_key="ord-47710", timeout_ms=10000),
    log("2026-05-06T13:02:32.022Z", "INFO", "payments-api", "charge succeeded (idempotent replay)", "t-a051",
        order_id="ord-47710", attempt=2, provider_key="ord-47710", charge_id="ch_7702", replayed=True),
    log("2026-05-06T13:42:10.114Z", "INFO", "payments-api", "charge succeeded", "t-a100", order_id="ord-48001",
        attempt=1, provider_key="ord-48001:1", charge_id="ch_7731", latency_ms=240),
    log("2026-05-06T14:03:12.401Z", "WARN", "payments-api", "provider timeout", "t-a201", order_id="ord-48213",
        attempt=1, provider_key="ord-48213:1", timeout_ms=10000),
    log("2026-05-06T14:03:12.955Z", "INFO", "storefront-api", "retrying payment", "t-a202", order_id="ord-48213",
        attempt=2, reason="timeout"),
    log("2026-05-06T14:03:13.221Z", "INFO", "payments-api", "charge succeeded", "t-a202", order_id="ord-48213",
        attempt=2, provider_key="ord-48213:2", charge_id="ch_8120", latency_ms=268),
    log("2026-05-06T14:03:21.004Z", "INFO", "payments-webhooks", "charge.succeeded received", None,
        charge_id="ch_8119", reference="ord-48213", amount=7500),
    log("2026-05-06T14:03:21.010Z", "WARN", "payments-webhooks", "webhook for a charge not linked to its order", None,
        charge_id="ch_8119", reference="ord-48213", recorded_charge_id="ch_8120"),
    log("2026-05-06T14:03:21.120Z", "INFO", "payments-webhooks", "charge.succeeded received", None,
        charge_id="ch_8120", reference="ord-48213", amount=7500),
    log("2026-05-06T14:04:02.318Z", "WARN", "payments-api", "provider unavailable", "t-a240", order_id="ord-48217",
        attempt=1, provider_key="ord-48217:1", http_status=503),
    log("2026-05-06T14:04:02.880Z", "INFO", "payments-api", "charge succeeded", "t-a241", order_id="ord-48217",
        attempt=2, provider_key="ord-48217:2", charge_id="ch_8124", latency_ms=301),
    log("2026-05-06T14:04:40.507Z", "WARN", "payments-api", "provider timeout", "t-a260", order_id="ord-48230",
        attempt=1, provider_key="ord-48230:1", timeout_ms=10000),
    log("2026-05-06T14:04:51.120Z", "WARN", "payments-api", "provider timeout", "t-a261", order_id="ord-48230",
        attempt=2, provider_key="ord-48230:2", timeout_ms=10000),
    log("2026-05-06T14:04:51.906Z", "INFO", "payments-api", "charge succeeded", "t-a262", order_id="ord-48230",
        attempt=3, provider_key="ord-48230:3", charge_id="ch_8133", latency_ms=286),
    log("2026-05-06T14:05:00.000Z", "ERROR", "alertmanager", "ProviderTimeoutRateHigh firing", None,
        rate_percent=18, threshold_percent=5),
    log("2026-05-06T14:09:12.000Z", "INFO", "payments-api", "configuration reloaded", None, provider_timeout_ms=20000),
    log("2026-05-06T14:12:44.701Z", "WARN", "payments-api", "provider timeout", "t-a300", order_id="ord-48390",
        attempt=1, provider_key="ord-48390:1", timeout_ms=20000),
    log("2026-05-06T14:12:45.310Z", "INFO", "payments-api", "charge succeeded", "t-a301", order_id="ord-48390",
        attempt=2, provider_key="ord-48390:2", charge_id="ch_8301", latency_ms=255),
    log("2026-05-06T14:40:00.420Z", "WARN", "finance-recon", "orders with more than one captured charge", None,
        orders_two_charges=61, orders_three_charges=2),
    log("2026-05-06T14:52:03.000Z", "INFO", "storefront-api", "feature flag changed", None,
        flag="checkout.payment_retries.enabled", value=False),
    log("2026-05-06T14:55:31.665Z", "ERROR", "storefront-api", "checkout failed: provider unavailable", "t-a410",
        order_id="ord-49002", attempt=1, retries_enabled=False),
    log("2026-05-06T15:05:12.000Z", "INFO", "support", "provider ticket updated", None, ticket="CF-20931",
        note="duplicate pairs use different idempotency keys ending in :1 and :2"),
    log("2026-05-06T15:20:00.000Z", "INFO", "storefront-api", "feature flag changed", None,
        flag="checkout.payment_retries.enabled", value=True),
], key=lambda entry: entry["ts"])

START = "2026-05-06T13:00:00Z"
ARTIFACTS = [
    artifact("payment-logs", "logs", "Payment logs", "payments-api, storefront-api, payments-webhooks and "
             "finance-recon logs, 13:00–15:20 UTC.", {"entries": LOGS}),
    artifact("payment-metrics", "metrics", "Checkout payments dashboard", "Ten-minute buckets.", {
        "series": [
            series("provider_timeouts", "count per 10 min", START, 10,
                   [0, 0, 0, 0, 0, 0, 41, 96, 70, 35, 22, 9, 6, 2, 0, 0]),
            series("payment_retries", "count per 10 min", START, 10,
                   [3, 2, 4, 3, 2, 3, 52, 118, 90, 48, 31, 4, 0, 0, 2, 3]),
            series("captured_charges_per_order", "ratio", START, 10,
                   [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.21, 1.38, 1.29, 1.14, 1.09, 1.01, 1.0, 1.0, 1.0, 1.0]),
            series("checkout_payment_failures", "count per 10 min", START, 10,
                   [1, 0, 1, 1, 0, 1, 4, 6, 5, 3, 2, 9, 19, 17, 3, 1]),
        ],
        "annotations": [
            {"at": "2026-05-06T13:10:00Z", "label": "Deploy payments-api 2026.05.06-2"},
            {"at": "2026-05-06T14:02:00Z", "label": "CardFlow latency degraded"},
            {"at": "2026-05-06T14:52:00Z", "label": "Storefront retries disabled"},
            {"at": "2026-05-06T15:20:00Z", "label": "Storefront retries re-enabled"},
        ]}),
    artifact("payment-traces", "traces", "Order ord-48213 and a retry before the deploy",
             "Both attempts for ord-48213, and order ord-47710 retried at 13:02, before the deploy.", {"traces": [
                 {"trace_id": "t-a201", "spans": [
                     span("t-a201-1", None, "storefront-api", "POST /checkout/pay", 0, 10012, "error",
                          order_id="ord-48213", attempt=1),
                     span("t-a201-2", "t-a201-1", "payments-api", "process payment", 1, 10010, "error"),
                     span("t-a201-3", "t-a201-2", "cardflow", "POST /v1/charges", 3, 10000, "error",
                          idempotency_key="ord-48213:1", error="client timeout after 10000 ms"),
                 ]},
                 {"trace_id": "t-a202", "spans": [
                     span("t-a202-1", None, "storefront-api", "POST /checkout/pay", 0, 270, order_id="ord-48213",
                          attempt=2),
                     span("t-a202-2", "t-a202-1", "payments-api", "process payment", 1, 268),
                     span("t-a202-3", "t-a202-2", "cardflow", "POST /v1/charges", 4, 262,
                          idempotency_key="ord-48213:2", charge_id="ch_8120", idempotent_replayed=False),
                 ]},
                 {"trace_id": "t-a051", "spans": [
                     span("t-a051-1", None, "storefront-api", "POST /checkout/pay", 0, 244, order_id="ord-47710",
                          attempt=2),
                     span("t-a051-2", "t-a051-1", "payments-api", "process payment", 1, 241),
                     span("t-a051-3", "t-a051-2", "cardflow", "POST /v1/charges", 3, 236,
                          idempotency_key="ord-47710", charge_id="ch_7702", idempotent_replayed=True),
                 ]},
             ]}),
    artifact("payment-records", "database", "Payments database and CardFlow export",
             "payments-db rows for the sample orders, CardFlow's charge export, and the finance summary.", {"tables": [
                 {"name": "payments", "columns": ["order_key", "status", "charge_id", "attempts", "amount",
                                                  "updated_at"],
                  "rows": [["ord-47710", "succeeded", "ch_7702", 2, 3100, "2026-05-06T13:02:32Z"],
                           ["ord-48001", "succeeded", "ch_7731", 1, 4999, "2026-05-06T13:42:10Z"],
                           ["ord-48213", "succeeded", "ch_8120", 2, 7500, "2026-05-06T14:03:13Z"],
                           ["ord-48217", "succeeded", "ch_8124", 2, 2500, "2026-05-06T14:04:02Z"],
                           ["ord-48230", "succeeded", "ch_8133", 3, 1200, "2026-05-06T14:04:51Z"]]},
                 {"name": "cardflow_charges (export)",
                  "columns": ["charge_id", "idempotency_key", "reference", "amount", "status", "created_at"],
                  "rows": [["ch_7702", "ord-47710", "ord-47710", 3100, "captured", "2026-05-06T13:02:21Z"],
                           ["ch_7731", "ord-48001:1", "ord-48001", 4999, "captured", "2026-05-06T13:42:10Z"],
                           ["ch_8119", "ord-48213:1", "ord-48213", 7500, "captured", "2026-05-06T14:03:04Z"],
                           ["ch_8120", "ord-48213:2", "ord-48213", 7500, "captured", "2026-05-06T14:03:13Z"],
                           ["ch_8124", "ord-48217:2", "ord-48217", 2500, "captured", "2026-05-06T14:04:02Z"],
                           ["ch_8127", "ord-48230:1", "ord-48230", 1200, "captured", "2026-05-06T14:04:33Z"],
                           ["ch_8130", "ord-48230:2", "ord-48230", 1200, "captured", "2026-05-06T14:04:44Z"],
                           ["ch_8133", "ord-48230:3", "ord-48230", 1200, "captured", "2026-05-06T14:04:51Z"]]},
                 {"name": "finance_reconciliation", "columns": ["metric", "value"],
                  "rows": [["orders with two captured charges", 61], ["orders with three captured charges", 2],
                           ["duplicate amount (EUR cents)", 421340]]},
             ]}),
    text_artifact("payment-config", "config", "Payment configuration", "payments-api and storefront checkout "
                  "client settings.", "deploy/payments.yaml", "yaml", '''
payments-api:
  provider:
    name: cardflow
    base_url: https://api.cardflow.example.com
    timeout_ms: 10000            # raised to 20000 at 14:09 UTC
    idempotency_header: Idempotency-Key
storefront-api:
  payment_retries:
    enabled: true
    max_attempts: 3
    retry_on: [timeout, provider_unavailable]
    backoff_ms: 500
'''),
    artifact("deploy-2026-05-06-2", "diff", "Deploy 2026.05.06-2: attempt numbers in provider keys",
             "Deployed 2026-05-06 13:10 UTC.", {
                 "title": "Tag provider requests with the attempt number", "author": "dev-payments-team",
                 "content": '''
--- a/payments/service.py
+++ b/payments/service.py
@@ -52,7 +52,8 @@ class PaymentService:
         record = self.payments.get(key)
         if record and record["status"] in ("succeeded", "declined"):
             return {"status": record["status"], "charge_id": record["charge_id"]}
-        provider_key = key
+        # Unique per attempt so support can tell retries apart in the provider dashboard.
+        provider_key = f"{key}:{attempt}"
         try:
             result = self.provider.charge(provider_key, payment["amount"], reference=key)
         except ProviderTimeout:
'''.strip("\n") + "\n"}),
    text_artifact("cardflow-contract", "api_contract", "CardFlow charges API (excerpt)",
                  "Provider documentation for idempotent charge requests.", "docs/cardflow/charges.md", "markdown", '''
# POST /v1/charges

Headers: `Idempotency-Key` (required, up to 64 characters).

- A request whose key matches an earlier request in the last 24 hours returns the original
  result with `idempotent_replayed: true`. No second charge is created.
- Use one key per payment, not per attempt: retries of the same payment must reuse the key.
- A 503 response means the request was not processed and no charge exists; retry it with the
  same key.
- A client-side timeout says nothing about whether the charge was created. Retry with the same
  key to learn the outcome safely.
'''),
    artifact("payment-architecture", "architecture", "Payment flow", "Checkout payment path.", {
        "nodes": [
            {"id": "storefront", "label": "storefront-api", "kind": "service"},
            {"id": "payments", "label": "payments-api", "kind": "service"},
            {"id": "payments-db", "label": "payments-db (PostgreSQL)", "kind": "database"},
            {"id": "cardflow", "label": "CardFlow (card processor)", "kind": "external"},
            {"id": "webhooks", "label": "payments-webhooks", "kind": "service"},
            {"id": "recon", "label": "finance-recon (hourly)", "kind": "service"},
        ],
        "edges": [
            {"from": "storefront", "to": "payments", "label": "POST /payments (retries up to 3)"},
            {"from": "payments", "to": "cardflow", "label": "POST /v1/charges + Idempotency-Key"},
            {"from": "payments", "to": "payments-db", "label": "payment records"},
            {"from": "cardflow", "to": "webhooks", "label": "charge.succeeded"},
            {"from": "webhooks", "to": "payments-db", "label": "link charges"},
            {"from": "recon", "to": "cardflow", "label": "charge export"},
            {"from": "recon", "to": "payments-db", "label": "compare"},
        ]}),
]

INCIDENT = {
    "slug": "duplicate-payment-retries",
    "title": "Customers charged twice after provider timeouts",
    "summary": "While the card processor was slow, retried checkouts captured a second charge for the same order. "
               "Legitimate retries after provider errors must keep working.",
    "severity": "SEV-1",
    "level": 2,
    "category": "retry_idempotency",
    "taxonomy": {"bug_categories": ["retry_idempotency", "distributed_consistency"],
                 "skills": ["log_investigation", "invariant_reasoning", "reproduction", "state_inspection"]},
    "affected_services": ["payments-api", "storefront-api", "CardFlow (external)"],
    "impact": [
        "63 orders were captured two or three times; 4,213.40 EUR in duplicate charges.",
        "Customers opened support tickets and some disputed the charges with their banks.",
        "Disabling retries during the incident made checkout failures rise for 30 minutes.",
    ],
    "expected_behavior": "Each order is charged at most once, however many times the storefront retries it, "
                         "and a retry after a provider error that created no charge still completes the payment.",
    "observed_symptoms": [
        "Finance reconciliation finds orders with two or three captured charges.",
        "Duplicate charges appear only for orders whose first attempt timed out.",
        "CardFlow latency was degraded between 14:02 and 14:45 UTC.",
        "Webhooks report charges that are not linked to their order's payment record.",
    ],
    "objective": "Explain why a timed-out attempt led to a second capture, fix PaymentService.process(), and "
                 "keep retries working for provider errors.",
    "timeline": [
        event("2026-05-06T13:10:00Z", "deploy", "payments-api 2026.05.06-2",
              "Adds the attempt number to provider requests so support can tell retries apart."),
        event("2026-05-06T14:02:00Z", "symptom", "CardFlow latency degraded",
              "Provider status page reports elevated latency; p99 above 10 seconds."),
        event("2026-05-06T14:05:00Z", "alert", "Provider timeout rate 18%",
              "payments-api timeouts (10-second client timeout) exceed the 5% threshold."),
        event("2026-05-06T14:09:00Z", "action", "Provider timeout raised to 20 s",
              "Fewer timeouts, but timed-out payments are still retried by the storefront."),
        event("2026-05-06T14:31:00Z", "symptom", "Duplicate charge tickets",
              "23 support tickets report two identical charges for one order."),
        event("2026-05-06T14:40:00Z", "alert", "Finance reconciliation mismatch",
              "61 orders have two captured charges and 2 orders have three."),
        event("2026-05-06T14:52:00Z", "action", "Storefront retries disabled",
              "Checkout failures double: payments whose first attempt hit a 503 now fail outright."),
        event("2026-05-06T15:05:00Z", "note", "CardFlow support reply",
              "Duplicate pairs use different idempotency keys ending in :1 and :2."),
        event("2026-05-06T15:20:00Z", "action", "Storefront retries re-enabled",
              "Retries restored because failed checkouts outnumbered duplicates."),
    ],
    "artifacts": ARTIFACTS,
    "scenarios": [
        {"id": "clean-checkout", "name": "Clean checkout", "description": "No provider problems.",
         "tests": ["Clean checkout"]},
        {"id": "timeout-after-capture", "name": "Timeout after the card was charged",
         "description": "CardFlow captures the charge but the response times out; the storefront retries.",
         "tests": ["Timeout after the card was charged"]},
        {"id": "legitimate-retry", "name": "Provider outage before charging",
         "description": "A 503 creates no charge, so the retry must charge.", "tests": ["Provider outage before charging"]},
    ],
    "rubric": {
        "version": 1, "source": "authored",
        "defect_categories": ["retry_idempotency"],
        "related_categories": ["distributed_consistency", "database_transactions"],
        "root_cause": [
            ["idempotency key", "idempotency-key", "idempotency_key", "provider key", "provider_key", "idempotent"],
            ["per attempt", "each attempt", "every attempt", "attempt number", "different key", "new key",
             "changes on retry", "suffix", ":1", ":2"],
            ["timeout", "timed out", "time out", "lost response", "response is lost"],
            ["provider", "cardflow", "charge twice", "second charge", "duplicate charge", "dedupe", "deduplicate",
             "replay"],
        ],
        "component": ["process", "PaymentService", "provider_key", "charge"],
        "invariant": [
            ["charged once", "at most once", "exactly once", "only once", "single charge", "one charge",
             "never charged twice"],
            ["per order", "per payment", "same order", "idempotency key", "same key", "each order"],
        ],
        "correction": [
            ["stable key", "same key", "reuse the key", "original key", "order key", "order's key",
             "payment key", "consistent key", "provider_key = key"],
            ["provider deduplicates", "provider dedupes", "provider idempotency", "idempotent replay",
             "pass the idempotency key", "send the idempotency key", "deduplicate"],
            ["retry", "retries", "keep retries"],
        ],
        "reproduction": [
            ["timeout", "timeout_after_charge", "times out", "slow provider", "timed out"],
            ["retry", "retries", "second attempt", "attempt 2"],
            ["two charges", "charged twice", "duplicate charge", "count charges", "charges"],
        ],
    },
    "evaluation": {
        "remediation_concepts": [
            ["refund", "reverse", "void"],
            ["identify", "query", "find duplicates", "reconcile", "export"],
            ["notify", "customers", "support", "apologize"],
            ["hotfix", "rollback", "revert", "deploy the fix"],
        ],
        "prevention_concepts": [
            ["test", "regression test", "integration test", "timeout test", "fault injection"],
            ["stable key", "idempotency", "one key per payment"],
            ["alert", "monitor", "reconciliation", "duplicate charge alert"],
            ["review", "provider contract", "documentation"],
        ],
        "impact_concepts": [
            ["charged twice", "double charge", "duplicate charge", "duplicate charges"],
            ["customers", "orders"],
            ["refund", "chargeback", "dispute", "support tickets"],
            ["revenue", "trust", "financial", "eur"],
        ],
    },
    "problem": {
        "title": "Incident: one order, two charges",
        "summary": "A captured charge whose response times out is charged again when the storefront retries. "
                   "Make retries safe without breaking retries after provider errors.",
        "category": "business",
        "difficulty": "medium",
        "tags": ["idempotency", "retries", "payments", "timeouts"],
        "requirements": [
            "Input has payments [{key, customer, amount}] processed in order, max_attempts, and provider: the "
            "scripted outcome of each new charge request CardFlow receives (ok, declined, unavailable, "
            "timeout_after_charge).",
            "CardFlow returns the original charge for a repeated idempotency key without using an outcome. The "
            "storefront retries a timeout or provider error with the same order key, up to max_attempts.",
            "Charge each order key at most once, but still charge an order whose earlier attempt failed before a "
            "charge existed. Different orders are always charged, even for the same customer and amount.",
            "Return each order's final response {key, status, charge_id, attempts} and the state {charges, "
            "charged_by_order, payments}.",
        ],
        "starters": {"python": STARTER},
        "solutions": {"python": SOLUTION},
        "tests": TESTS,
        "explanation": "process() sent CardFlow a key that included the attempt number. When a charge was captured "
                       "but its response timed out, the retry arrived with a new key, so CardFlow could not "
                       "recognize it and charged again. Sending the order's own idempotency key on every attempt "
                       "lets CardFlow return the original charge, while a retry after a 503 (no charge yet) still "
                       "charges once. Refusing retries breaks that legitimate case, and deduplicating by customer "
                       "and amount blocks real repeat purchases. Time O(a) for a attempts.",
        "hints": [
            "A timeout does not mean the charge failed. What does CardFlow need to recognize a retry as the same "
            "payment?",
            "Compare the idempotency keys of the two charges for one order in the CardFlow export. What makes them "
            "differ?",
            "The provider key includes the attempt number, so every retry looks like a new payment. Send the "
            "order's own key on every attempt; a retry after a 503 still charges once.",
        ],
        "minutes": 30,
    },
}
