"""Append-only September 28, 2026 expansion to 324 cases: 10 per category plus 13 system design."""
from .business import PROBLEMS as BUSINESS
from .edge import PROBLEMS as EDGE
from .logic import PROBLEMS as LOGIC
from .runtime import PROBLEMS as RUNTIME
from .system_design import PROBLEMS as SYSTEM_DESIGN

THIRD_WAVE = [*RUNTIME, *LOGIC, *BUSINESS, *EDGE, *SYSTEM_DESIGN]
