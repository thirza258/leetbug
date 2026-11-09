"""Built-in assessment packs (PRD Phase 5 "Initial assessment packs").

Each pack selects existing, sandbox-verified catalog problems. Seeding is insert-only, so edits
here apply to fresh installations; running installations keep their stored configuration.
"""
from app.scoring import ASSESSMENT_WEIGHTS

ASSESSMENT_PACKS = [
    {
        "slug": "backend-engineer-go",
        "title": "Backend Engineer — Go",
        "description": "Five Go backend defects: nil maps, quota windows, deadline propagation, channel deadlocks and "
                       "graceful shutdown. Diagnose each root cause before patching. No hints or AI assistance.",
        "assessment_type": "specialized",
        "duration_seconds": 90 * 60,
        "configuration": {
            "problems": ["nil-map", "daily-usage-reset", "deadline-budget-propagation",
                         "unbuffered-channel-deadlock", "graceful-drain-deadline"],
            "languages": ["go"], "diagnosis_required": True, "explanation_required": True,
            "max_attempts": 10, "max_sessions": None, "randomize_order": False, "feedback": "immediate",
            "candidate_report": "full", "require_quality_approved": False,
        },
        "assistance_policy": {"ai": "disabled", "hints": "disabled"},
    },
    {
        "slug": "backend-engineer-python",
        "title": "Backend Engineer — Python",
        "description": "Four Python service defects covering authorization, idempotent retries, a concurrent wallet "
                       "race and cache invalidation. Restricted: only the first conceptual hint, no AI.",
        "assessment_type": "specialized",
        "duration_seconds": 90 * 60,
        "configuration": {
            "problems": ["role-confusion", "inventory-retry", "wallet-race", "cache-write-invalidation"],
            "languages": ["python"], "diagnosis_required": True, "explanation_required": True,
            "max_attempts": 10, "max_sessions": None, "randomize_order": False, "feedback": "immediate",
            "candidate_report": "full", "require_quality_approved": False,
        },
        "assistance_policy": {"ai": "disabled", "hints": "restricted"},
    },
    {
        "slug": "ai-backend-engineer",
        "title": "AI Backend Engineer",
        "description": "Model evaluation and data-pipeline reliability: leakage, metric denominators, duplicate "
                       "events, retry backoff and rate limiting. Guided: conceptual AI help and the first hint only.",
        "assessment_type": "specialized",
        "duration_seconds": 90 * 60,
        "configuration": {
            "problems": ["scaler-fit-before-split", "recall-denominator", "retry-duplicate-events",
                         "backoff-cap-before-growth", "token-bucket-capacity"],
            "languages": ["python"], "diagnosis_required": True, "explanation_required": False,
            "max_attempts": 10, "max_sessions": None, "randomize_order": False, "feedback": "immediate",
            "candidate_report": "full", "require_quality_approved": False,
        },
        "assistance_policy": {"ai": "guided", "hints": "restricted"},
    },
    {
        "slug": "general-software-debugging",
        "title": "General Software Debugging",
        "description": "A learning-oriented practice assessment across languages and bug categories. Hints and AI "
                       "assistance are allowed and recorded; results are reported separately from restricted runs.",
        "assessment_type": "practice",
        "duration_seconds": 60 * 60,
        "configuration": {
            "problems": ["missing-last-item", "checkout-underflow", "cached-zero", "retry-budget", "integer-overflow"],
            "languages": [], "diagnosis_required": False, "explanation_required": False,
            "max_attempts": None, "max_sessions": None, "randomize_order": False, "feedback": "immediate",
            "candidate_report": "full", "require_quality_approved": False,
        },
        "assistance_policy": {"ai": "enabled", "hints": "enabled"},
    },
]

DEFAULT_RUBRIC = {"weights": dict(ASSESSMENT_WEIGHTS)}
