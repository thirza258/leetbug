"""Production incident catalog (PRD §6, Phase 4 initial catalog).

Append only: incident ``n`` (1-based position) is seeded as Incident ``n`` and Problem ``100000 + n``,
so reordering would move IDs and break stored progress. Each definition follows the format validated
by ``app.incidents.validation.validate_definition``. All systems, people, hosts and identifiers are
fictional.
"""
from app.incidents.catalog_inventory import INCIDENT as INVENTORY_RACE
from app.incidents.catalog_orders import INCIDENT as CONNECTION_POOL
from app.incidents.catalog_payments import INCIDENT as DUPLICATE_PAYMENTS
from app.incidents.catalog_pricing import INCIDENT as STALE_PRICE_CACHE
from app.incidents.catalog_retries import INCIDENT as RETRY_AMPLIFICATION
from app.incidents.catalog_scheduler import INCIDENT as SCHEDULER_DST

INCIDENTS: list[dict] = [
    INVENTORY_RACE,
    DUPLICATE_PAYMENTS,
    STALE_PRICE_CACHE,
    CONNECTION_POOL,
    RETRY_AMPLIFICATION,
    SCHEDULER_DST,
]
