"""Incident: price updates never reach checkout after a cache-key change (caching, level 2)."""
from app.catalog import case, code
from app.incidents.catalog_common import artifact, event, log, series, span, text_artifact

STARTER = code('''
    CURRENCIES = ("USD", "EUR", "GBP")
    CACHE_TTL_SECONDS = 21600


    def price_cache_key(sku, currency):
        return f"price:v2:{sku}:{currency}"


    class Cache:
        """Redis stand-in with per-key expiry. Times are seconds since the scenario started."""

        def __init__(self):
            self.entries = {}

        def get(self, key, now):
            entry = self.entries.get(key)
            if entry is None or entry["expires_at"] <= now:
                return None
            return entry["value"]

        def set(self, key, value, ttl, now):
            self.entries[key] = {"value": value, "expires_at": now + ttl}

        def delete(self, key):
            """Remove a key and return how many keys were deleted (0 or 1), like Redis DEL."""
            return 1 if self.entries.pop(key, None) is not None else 0


    class PriceService:
        def __init__(self, prices, rates):
            self.prices = dict(prices)   # sku -> USD cents; the source of truth
            self.rates = rates           # currency -> basis points per USD (10000 = 1.0)
            self.cache = Cache()

        def convert(self, amount_usd_cents, currency):
            return amount_usd_cents * self.rates[currency] // 10000

        def get_price(self, sku, currency, now):
            key = price_cache_key(sku, currency)
            cached = self.cache.get(key, now)
            if cached is not None:
                return cached
            price = self.convert(self.prices[sku], currency)
            self.cache.set(key, price, CACHE_TTL_SECONDS, now)
            return price

        def update_price(self, sku, amount_usd_cents, now):
            self.prices[sku] = amount_usd_cents
            self.cache.delete(f"price:{sku}")


    def solve(data):
        service = PriceService(data["prices"], data["rates"])
        reads = []
        for event in data["events"]:
            if event["op"] == "update":
                service.update_price(event["sku"], event["amount"], event["at"])
            else:
                reads.append(service.get_price(event["sku"], event["currency"], event["at"]))
        return {"reads": reads, "state": {"prices": dict(sorted(service.prices.items()))}}
''')

SOLUTION = STARTER.replace('''        self.prices[sku] = amount_usd_cents
        self.cache.delete(f"price:{sku}")
''', '''        self.prices[sku] = amount_usd_cents
        # Invalidate exactly the keys the read path creates: one per currency, from the same helper.
        for currency in CURRENCIES:
            self.cache.delete(price_cache_key(sku, currency))
''')
assert SOLUTION != STARTER

RATES = {"USD": 10000, "EUR": 9200, "GBP": 7900}


def _get(sku, currency, at):
    return {"op": "get", "sku": sku, "currency": currency, "at": at}


def _update(sku, amount, at):
    return {"op": "update", "sku": sku, "amount": amount, "at": at}


def _scenario(events, prices=None):
    return {"prices": prices or {"SKU-HEADSET": 12000}, "rates": RATES, "events": events}


TESTS = [
    case("Repeated reads hit the cache",
         _scenario([_get("SKU-HEADSET", "USD", 0), _get("SKU-HEADSET", "USD", 60), _get("SKU-HEADSET", "EUR", 120)]),
         {"reads": [12000, 12000, 11040], "state": {"prices": {"SKU-HEADSET": 12000}}}),
    case("Price drop after a cached read",
         _scenario([_get("SKU-HEADSET", "USD", 0), _update("SKU-HEADSET", 9000, 100), _get("SKU-HEADSET", "USD", 200)]),
         {"reads": [12000, 9000], "state": {"prices": {"SKU-HEADSET": 9000}}},
         assertions=[{"path": "reads.1", "equals": 9000}]),
    case("Euro shopper after a price drop",
         _scenario([_get("SKU-HEADSET", "EUR", 0), _update("SKU-HEADSET", 9000, 100), _get("SKU-HEADSET", "EUR", 200)]),
         {"reads": [11040, 8280], "state": {"prices": {"SKU-HEADSET": 9000}}}),
    case("Every currency refreshes",
         _scenario([_get("SKU-HEADSET", "USD", 0), _get("SKU-HEADSET", "EUR", 1), _get("SKU-HEADSET", "GBP", 2),
                    _update("SKU-HEADSET", 10000, 10), _get("SKU-HEADSET", "USD", 20),
                    _get("SKU-HEADSET", "EUR", 21), _get("SKU-HEADSET", "GBP", 22)]),
         {"reads": [12000, 11040, 9480, 10000, 9200, 7900], "state": {"prices": {"SKU-HEADSET": 10000}}}, True),
    case("Expired entries reload",
         _scenario([_get("SKU-HEADSET", "USD", 0), _update("SKU-HEADSET", 9000, 100),
                    _get("SKU-HEADSET", "USD", 21600)]),
         {"reads": [12000, 9000], "state": {"prices": {"SKU-HEADSET": 9000}}}, True),
    case("Update before the first read",
         _scenario([_update("SKU-HEADSET", 8000, 0), _get("SKU-HEADSET", "GBP", 10)]),
         {"reads": [6320], "state": {"prices": {"SKU-HEADSET": 8000}}}, True),
    case("Only the changed product refreshes",
         _scenario([_get("SKU-HEADSET", "USD", 0), _get("SKU-MOUSE", "USD", 1), _update("SKU-MOUSE", 2500, 5),
                    _get("SKU-HEADSET", "USD", 6), _get("SKU-MOUSE", "USD", 7)],
                   {"SKU-HEADSET": 12000, "SKU-MOUSE": 3000}),
         {"reads": [12000, 3000, 12000, 2500], "state": {"prices": {"SKU-HEADSET": 12000, "SKU-MOUSE": 2500}}}, True),
    case("Two updates in a row",
         _scenario([_get("SKU-HEADSET", "EUR", 0), _update("SKU-HEADSET", 10000, 5), _get("SKU-HEADSET", "EUR", 6),
                    _update("SKU-HEADSET", 8000, 7), _get("SKU-HEADSET", "EUR", 8)]),
         {"reads": [11040, 9200, 7360], "state": {"prices": {"SKU-HEADSET": 8000}}}, True),
    case("A currency first cached after the update",
         _scenario([_get("SKU-HEADSET", "USD", 0), _update("SKU-HEADSET", 6000, 5), _get("SKU-HEADSET", "GBP", 6),
                    _get("SKU-HEADSET", "USD", 7)]),
         {"reads": [12000, 4740, 6000], "state": {"prices": {"SKU-HEADSET": 6000}}}, True),
]

LOGS = sorted([
    log("2026-06-01T16:31:02.114Z", "INFO", "pricing-api", "service started", version="2026.06.01-3",
        cache_key_version="v2", cache_ttl_seconds=21600),
    log("2026-06-02T07:58:44.310Z", "INFO", "checkout-api", "price lookup", "t-p001", sku="SKU-HEADSET",
        currency="EUR", cache="miss", key="price:v2:SKU-HEADSET:EUR", price=11040),
    log("2026-06-02T07:59:12.702Z", "INFO", "checkout-api", "price lookup", "t-p002", sku="SKU-HEADSET",
        currency="USD", cache="miss", key="price:v2:SKU-HEADSET:USD", price=12000),
    log("2026-06-02T08:00:00.120Z", "INFO", "pricing-admin", "price updated", "t-p010", sku="SKU-HEADSET",
        old=12000, new=9000, campaign="summer-drop"),
    log("2026-06-02T08:00:00.131Z", "INFO", "pricing-api", "cache invalidated", "t-p010", key="price:SKU-HEADSET",
        keys_deleted=0),
    log("2026-06-02T08:00:00.204Z", "INFO", "pricing-admin", "price updated", "t-p011", sku="SKU-MOUSE", old=3000,
        new=2500, campaign="summer-drop"),
    log("2026-06-02T08:00:00.212Z", "INFO", "pricing-api", "cache invalidated", "t-p011", key="price:SKU-MOUSE",
        keys_deleted=0),
    log("2026-06-02T08:00:03.900Z", "INFO", "pricing-admin", "campaign applied", None, campaign="summer-drop",
        skus_updated=120),
    log("2026-06-02T08:21:13.441Z", "INFO", "checkout-api", "price lookup", "t-p020", sku="SKU-HEADSET",
        currency="EUR", cache="hit", key="price:v2:SKU-HEADSET:EUR", price=11040),
    log("2026-06-02T08:21:13.502Z", "INFO", "cms", "campaign banner rendered", None, sku="SKU-HEADSET",
        price_eur=8280, source="pricing-db"),
    log("2026-06-02T08:34:50.019Z", "INFO", "checkout-api", "price lookup", "t-p021", sku="SKU-HEADSET",
        currency="USD", cache="hit", key="price:v2:SKU-HEADSET:USD", price=12000),
    log("2026-06-02T09:05:00.000Z", "WARN", "price-audit", "checkout price differs from source of truth", None,
        sku="SKU-HEADSET", currency="EUR", served=11040, expected=8280, mismatched_skus=117),
    log("2026-06-02T09:40:11.000Z", "INFO", "cdn", "purge requested", None, path="/api/prices/*",
        note="API responses are served with Cache-Control: no-store"),
    log("2026-06-02T09:52:37.880Z", "INFO", "checkout-api", "price lookup", "t-p030", sku="SKU-HEADSET",
        currency="EUR", cache="hit", key="price:v2:SKU-HEADSET:EUR", price=11040),
    log("2026-06-02T10:15:02.300Z", "INFO", "checkout-api", "price lookup", "t-p031", sku="SKU-MOUSE",
        currency="GBP", cache="hit", key="price:v2:SKU-MOUSE:GBP", price=2370),
    log("2026-06-02T11:40:00.000Z", "WARN", "pricing-api", "manual cache flush", None, actor="oncall-sre",
        keys_deleted=18342),
    log("2026-06-02T11:41:02.115Z", "INFO", "checkout-api", "price lookup", "t-p040", sku="SKU-HEADSET",
        currency="EUR", cache="miss", key="price:v2:SKU-HEADSET:EUR", price=8280),
    log("2026-06-02T11:43:10.402Z", "INFO", "checkout-api", "price lookup", "t-p041", sku="SKU-HEADSET",
        currency="USD", cache="miss", key="price:v2:SKU-HEADSET:USD", price=9000),
    log("2026-06-02T12:00:00.000Z", "INFO", "price-audit", "checkout prices match source of truth", None,
        mismatched_skus=0),
    log("2026-06-02T12:30:00.101Z", "INFO", "pricing-admin", "price updated", "t-p050", sku="SKU-HEADSET", old=9000,
        new=8900, campaign="summer-drop"),
    log("2026-06-02T12:30:00.109Z", "INFO", "pricing-api", "cache invalidated", "t-p050", key="price:SKU-HEADSET",
        keys_deleted=0),
    log("2026-06-02T12:44:30.660Z", "INFO", "checkout-api", "price lookup", "t-p051", sku="SKU-HEADSET",
        currency="EUR", cache="hit", key="price:v2:SKU-HEADSET:EUR", price=8280),
    log("2026-06-02T13:00:00.000Z", "WARN", "price-audit", "checkout price differs from source of truth", None,
        sku="SKU-HEADSET", currency="EUR", served=8280, expected=8188, mismatched_skus=1),
], key=lambda entry: entry["ts"])

HOURLY = "2026-06-01T14:00:00Z"
ARTIFACTS = [
    artifact("pricing-logs", "logs", "Pricing and checkout logs", "pricing-api, pricing-admin, checkout-api, "
             "price-audit, cms and CDN logs from the deploy to 13:00 UTC the next day.", {"entries": LOGS}),
    artifact("pricing-metrics", "metrics", "Pricing dashboard", "Hourly values from 2026-06-01 14:00 UTC.", {
        "series": [
            series("price_cache_hit_ratio", "percent", HOURLY, 60,
                   [96.1, 96.0, 96.2, 99.4, 99.5, 99.5, 99.6, 99.6, 99.5, 99.6, 99.6, 99.5, 99.6, 99.6, 99.6,
                    99.5, 99.6, 99.6, 99.7, 99.6, 99.6, 99.5, 63.0, 98.9, 99.4]),
            series("price_updates", "count per hour", HOURLY, 60,
                   [2, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 120, 0, 0, 0, 1, 0, 0]),
            series("cache_keys_deleted_on_update", "count per hour", HOURLY, 60, [2, 0, 1] + [0] * 22),
            series("checkout_price_mismatches", "count per hour", HOURLY, 60,
                   [0] * 18 + [412, 655, 590, 380, 14, 22, 19]),
        ],
        "annotations": [
            {"at": "2026-06-01T16:30:00Z", "label": "Deploy pricing-api 2026.06.01-3"},
            {"at": "2026-06-02T08:00:00Z", "label": "summer-drop campaign applied"},
            {"at": "2026-06-02T09:40:00Z", "label": "CDN purge"},
            {"at": "2026-06-02T11:40:00Z", "label": "Manual cache flush"},
            {"at": "2026-06-02T12:30:00Z", "label": "Second price update"},
        ]}),
    artifact("pricing-traces", "traces", "Price update and checkout lookup",
             "The campaign update for SKU-HEADSET and a checkout lookup 21 minutes later.", {"traces": [
                 {"trace_id": "t-p010", "spans": [
                     span("t-p010-1", None, "pricing-admin", "PUT /prices/SKU-HEADSET", 0, 14.2),
                     span("t-p010-2", "t-p010-1", "pricing-api", "update_price", 1.1, 12.5, sku="SKU-HEADSET"),
                     span("t-p010-3", "t-p010-2", "pricing-db", "UPDATE prices SET amount = $1", 2.0, 6.4,
                          **{"db.rows_affected": 1}),
                     span("t-p010-4", "t-p010-2", "pricing-cache", "DEL price:SKU-HEADSET", 9.3, 0.6,
                          **{"redis.keys_deleted": 0}),
                 ]},
                 {"trace_id": "t-p020", "spans": [
                     span("t-p020-1", None, "checkout-api", "GET /cart/total", 0, 9.8, currency="EUR"),
                     span("t-p020-2", "t-p020-1", "pricing-api", "get_price", 1.0, 2.1, sku="SKU-HEADSET",
                          currency="EUR"),
                     span("t-p020-3", "t-p020-2", "pricing-cache", "GET price:v2:SKU-HEADSET:EUR", 1.4, 0.5,
                          **{"cache.hit": True, "cache.value": 11040}),
                 ]},
             ]}),
    artifact("pricing-data", "database", "Prices and cache keys", "pricing-db rows and a Redis key scan taken at "
             "12:50 UTC on 2026-06-02.", {"tables": [
                 {"name": "prices", "columns": ["sku", "amount_usd_cents", "updated_at", "updated_by"],
                  "rows": [["SKU-HEADSET", 8900, "2026-06-02T12:30:00Z", "pricing-admin"],
                           ["SKU-MOUSE", 2500, "2026-06-02T08:00:00Z", "pricing-admin"],
                           ["SKU-KEYBOARD", 7900, "2026-05-20T10:12:00Z", "pricing-admin"]]},
                 {"name": "pricing-cache keys (SCAN price:*SKU-HEADSET*, price:*SKU-MOUSE*)",
                  "columns": ["key", "value", "ttl_seconds"],
                  "rows": [["price:v2:SKU-HEADSET:EUR", 8280, 17462], ["price:v2:SKU-HEADSET:USD", 9000, 17590],
                           ["price:v2:SKU-MOUSE:GBP", 1975, 20402]]},
             ]}),
    text_artifact("pricing-config", "config", "pricing-api configuration", "Deployed configuration.",
                  "deploy/pricing-api.yaml", "yaml", '''
service: pricing-api
version: 2026.06.01-3
cache:
  backend: redis
  host: pricing-cache.internal
  key_version: v2               # price:v2:{sku}:{currency}
  ttl_seconds: 21600
currencies: [USD, EUR, GBP]
rates_basis_points:
  USD: 10000
  EUR: 9200
  GBP: 7900
'''),
    artifact("deploy-2026-06-01-3", "diff", "Deploy 2026.06.01-3: cache converted prices per currency",
             "Deployed 2026-06-01 16:30 UTC.", {
                 "title": "Cache converted prices per currency (v2 keys)", "author": "dev-pricing-team",
                 "content": '''
--- a/pricing/service.py
+++ b/pricing/service.py
@@ -1,6 +1,10 @@
 CURRENCIES = ("USD", "EUR", "GBP")
 CACHE_TTL_SECONDS = 21600

+
+def price_cache_key(sku, currency):
+    return f"price:v2:{sku}:{currency}"
+
@@ -38,11 +42,11 @@ class PriceService:
     def get_price(self, sku, currency, now):
-        key = f"price:{sku}"
+        key = price_cache_key(sku, currency)
         cached = self.cache.get(key, now)
         if cached is not None:
-            return self.convert(cached, currency)
-        amount = self.prices[sku]
-        self.cache.set(key, amount, CACHE_TTL_SECONDS, now)
-        return self.convert(amount, currency)
+            return cached
+        price = self.convert(self.prices[sku], currency)
+        self.cache.set(key, price, CACHE_TTL_SECONDS, now)
+        return price
'''.strip("\n") + "\n"}),
    artifact("pricing-architecture", "architecture", "Pricing services", "Where prices are read and written.", {
        "nodes": [
            {"id": "cdn", "label": "CDN", "kind": "external"},
            {"id": "storefront", "label": "storefront-web", "kind": "service"},
            {"id": "checkout", "label": "checkout-api", "kind": "service"},
            {"id": "cms", "label": "cms (campaign banners)", "kind": "service"},
            {"id": "admin", "label": "pricing-admin", "kind": "service"},
            {"id": "pricing", "label": "pricing-api", "kind": "service"},
            {"id": "cache", "label": "pricing-cache (Redis)", "kind": "cache"},
            {"id": "db", "label": "pricing-db (PostgreSQL)", "kind": "database"},
        ],
        "edges": [
            {"from": "cdn", "to": "storefront", "label": "static pages"},
            {"from": "storefront", "to": "checkout", "label": "cart and checkout"},
            {"from": "checkout", "to": "pricing", "label": "GET /prices"},
            {"from": "admin", "to": "pricing", "label": "PUT /prices"},
            {"from": "pricing", "to": "cache", "label": "GET / SET / DEL"},
            {"from": "pricing", "to": "db", "label": "source of truth"},
            {"from": "cms", "to": "db", "label": "reads prices directly"},
        ]}),
]

INCIDENT = {
    "slug": "stale-price-cache",
    "title": "Checkout keeps charging pre-campaign prices",
    "summary": "After a price-drop campaign, checkout charged the old prices for hours while campaign banners showed "
               "the new ones. A manual cache flush fixed it until the next price update.",
    "severity": "SEV-3",
    "level": 2,
    "category": "caching",
    "taxonomy": {"bug_categories": ["caching", "configuration"],
                 "skills": ["log_investigation", "differential_debugging", "state_inspection", "reproduction"]},
    "affected_services": ["pricing-api", "pricing-cache", "checkout-api"],
    "impact": [
        "For about 3.5 hours, 117 of 120 campaign products were charged at their old prices.",
        "Customers saw one price on the campaign banner and another at checkout.",
        "Support had to refund price differences on affected orders.",
    ],
    "expected_behavior": "A price change is visible at checkout on the next lookup, in every currency, without "
                         "waiting for the cache to expire.",
    "observed_symptoms": [
        "Checkout serves cached prices from before the campaign; the database holds the new prices.",
        "The cache hit ratio rose from 96% to 99.6% after the previous day's deploy.",
        "A CDN purge changed nothing; a manual Redis flush fixed prices until the next update.",
        "Every 'cache invalidated' log reports keys_deleted=0.",
    ],
    "objective": "Find why price updates no longer reach checkout, fix PriceService so updates invalidate the "
                 "cached prices, and explain why the flush only helped temporarily.",
    "timeline": [
        event("2026-06-01T16:30:00Z", "deploy", "pricing-api 2026.06.01-3",
              "Caches converted prices per currency under v2 keys."),
        event("2026-06-02T08:00:00Z", "action", "summer-drop campaign applied",
              "Merchandising lowers prices for 120 products."),
        event("2026-06-02T08:20:00Z", "symptom", "Checkout shows old prices",
              "Customers report that checkout totals ignore the campaign shown on banners."),
        event("2026-06-02T09:05:00Z", "alert", "Price audit mismatch",
              "117 products are served at prices that differ from pricing-db."),
        event("2026-06-02T09:40:00Z", "action", "CDN purge",
              "No change: price API responses are not cached by the CDN."),
        event("2026-06-02T11:40:00Z", "action", "Manual cache flush",
              "On-call flushes the pricing cache; checkout prices match the database again."),
        event("2026-06-02T12:30:00Z", "symptom", "Second price update not visible",
              "SKU-HEADSET is lowered again, and checkout still serves the 11:41 price."),
        event("2026-06-02T13:10:00Z", "note", "Cache hit ratio",
              "The hit ratio has been 99.6% since the deploy, compared with 96% before."),
    ],
    "artifacts": ARTIFACTS,
    "scenarios": [
        {"id": "cache-baseline", "name": "Repeated reads hit the cache",
         "description": "Reads without updates behave correctly.", "tests": ["Repeated reads hit the cache"]},
        {"id": "price-drop", "name": "Price drop after a cached read",
         "description": "A cached USD price must change after an update.", "tests": ["Price drop after a cached read"]},
        {"id": "euro-shopper", "name": "Euro shopper after a price drop",
         "description": "The same in another currency.", "tests": ["Euro shopper after a price drop"]},
    ],
    "rubric": {
        "version": 1, "source": "authored",
        "defect_categories": ["caching"],
        "related_categories": ["configuration", "state_corruption", "distributed_consistency"],
        "root_cause": [
            ["cache key", "key format", "key mismatch", "wrong key", "different key", "legacy key", "old key", "v2"],
            ["invalidate", "invalidation", "delete", "deletes", "evict", "purge", "keys_deleted"],
            ["currency", "per currency", "eur", "variant", "variants"],
            ["stale", "old price", "ttl", "until expiry", "until it expires", "expire"],
        ],
        "component": ["update_price", "price_cache_key", "PriceService", "get_price"],
        "invariant": [
            ["after an update", "after update", "after a price change", "once updated", "next read", "next lookup"],
            ["current price", "latest price", "new price", "database price", "source of truth", "fresh"],
            ["every currency", "all currencies", "each currency", "never stale", "not stale"],
        ],
        "correction": [
            ["same key", "shared key", "price_cache_key", "key function", "key builder", "same helper"],
            ["every currency", "all currencies", "each currency", "each variant", "all variants", "loop"],
            ["delete", "invalidate", "evict", "write-through", "update the cache"],
        ],
        "reproduction": [
            ["read", "get", "cached", "warm the cache", "cache hit", "lookup"],
            ["update", "change the price", "price drop", "lower the price"],
            ["read again", "second read", "then read", "stale", "old price"],
        ],
    },
    "evaluation": {
        "remediation_concepts": [
            ["flush", "purge", "clear the cache", "delete the keys", "invalidate"],
            ["refund", "honor", "price difference", "credit", "compensate"],
            ["hotfix", "deploy the fix", "rollback", "revert"],
            ["affected orders", "identify orders", "query orders", "audit"],
        ],
        "prevention_concepts": [
            ["shared key function", "single key builder", "key helper", "one place"],
            ["test", "integration test", "cache test", "invalidation test"],
            ["shorter ttl", "ttl"],
            ["monitor", "alert", "price audit", "keys_deleted", "mismatch"],
            ["versioned", "version", "migration"],
        ],
        "impact_concepts": [
            ["old price", "stale price", "wrong price", "pre-campaign"],
            ["checkout", "orders", "customers"],
            ["refund", "revenue", "overcharged", "price difference"],
            ["hours", "duration", "ttl", "3.5"],
        ],
    },
    "problem": {
        "title": "Incident: the price that would not change",
        "summary": "Price updates write the database but checkout keeps serving the cached price until the TTL "
                   "expires. Make every update invalidate what the read path caches.",
        "category": "system_design",
        "difficulty": "medium",
        "tags": ["caching", "invalidation", "pricing", "configuration"],
        "requirements": [
            "Input has prices (USD cents per SKU, the source of truth), rates (basis points per USD for USD, EUR and "
            "GBP), and events in time order: {op: \"get\", sku, currency, at} or {op: \"update\", sku, amount, at}.",
            "Prices are cached per SKU and currency for 21,600 seconds; an entry expires when the event time reaches "
            "its expiry.",
            "After an update, every later read of that SKU in any currency returns the new price converted as "
            "amount * rate // 10000. Other SKUs keep their cached prices.",
            "Return {reads: [the price returned by each get, in order], state: {prices}}.",
        ],
        "starters": {"python": STARTER},
        "solutions": {"python": SOLUTION},
        "tests": TESTS,
        "explanation": "The deploy moved get_price() to per-currency keys (price:v2:{sku}:{currency}), but "
                       "update_price() still deleted the legacy key price:{sku}, which no longer existed. Updates "
                       "deleted nothing, so checkout served cached prices until the 6-hour TTL expired, and a "
                       "manual flush only helped until the next update. Invalidating the keys the read path "
                       "creates, for every currency and built with the same price_cache_key() helper, makes the "
                       "next read reload the source of truth. Time O(c) per update for c currencies.",
        "hints": [
            "The database has the new price but checkout does not. Which layer still answers with the old one, and "
            "for how long?",
            "Compare the key the update path deletes with the keys the read path writes. Does the invalidation "
            "delete anything?",
            "The read path uses per-currency v2 keys but the update path still deletes the legacy key. Build the "
            "keys with price_cache_key() and invalidate every currency.",
        ],
        "minutes": 25,
    },
}
