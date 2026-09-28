"""Append-only September 28, 2026 expansion: ten exercises per category in five languages."""
from .business import PROBLEMS as BUSINESS
from .edge import PROBLEMS as EDGE
from .logic import PROBLEMS as LOGIC
from .runtime import PROBLEMS as RUNTIME
from .system_design import PROBLEMS as SYSTEM_DESIGN

SECOND_WAVE = [*RUNTIME, *LOGIC, *BUSINESS, *EDGE, *SYSTEM_DESIGN]
