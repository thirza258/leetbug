"""Append-only September 2026 expansion: 20 exercises per category."""
from .business import PROBLEMS as BUSINESS
from .edge import PROBLEMS as EDGE
from .logic import PROBLEMS as LOGIC
from .runtime import PROBLEMS as RUNTIME
from .system_design import PROBLEMS as SYSTEM_DESIGN

ADDITIONAL_CATALOG = [*RUNTIME, *LOGIC, *BUSINESS, *EDGE, *SYSTEM_DESIGN]
