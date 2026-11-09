"""Engineering skill taxonomy and concept graph (PRD 10.1 and 10.4).

The same identifiers classify challenges, label diagnoses, break down assessment competencies,
and drive recommendations. Problems may override the derived classification through
``Problem.taxonomy = {"bug_categories": [...], "skills": [...]}``.
"""
from collections import OrderedDict

TAXONOMY_VERSION = 1

# PRD 10.1 bug categories, plus four that the existing catalog needs for precise labels
# (boundaries, runtime exceptions, numeric precision, data/statistical reasoning).
BUG_CATEGORIES: "OrderedDict[str, dict]" = OrderedDict([
    ("logic_error", {"name": "Logic error", "description": "Code runs but computes the wrong result."}),
    ("boundary_condition", {"name": "Boundary condition", "description": "Off-by-one, empty input, or limit handling.",
                            "extension": True}),
    ("nullability", {"name": "Nullability", "description": "Missing, null, nil, or optional values."}),
    ("runtime_exception", {"name": "Runtime exception", "description": "An unhandled error or crash on valid input.",
                           "extension": True}),
    ("numeric_precision", {"name": "Numeric precision", "description": "Overflow, rounding, or floating-point error.",
                           "extension": True}),
    ("state_corruption", {"name": "State corruption", "description": "Shared or persisted state left inconsistent."}),
    ("race_condition", {"name": "Race condition", "description": "Interleaved operations violate an invariant."}),
    ("deadlock", {"name": "Deadlock", "description": "Operations wait on each other forever."}),
    ("resource_leak", {"name": "Resource leak", "description": "Connections, handles, or memory are not released."}),
    ("database_transactions", {"name": "Database transactions", "description": "Missing or wrong transaction boundaries."}),
    ("serialization", {"name": "Serialization", "description": "Parsing, encoding, or format conversion errors."}),
    ("caching", {"name": "Caching", "description": "Stale, missing, or incorrectly invalidated cache entries."}),
    ("authentication", {"name": "Authentication", "description": "Identity, credentials, or token validation."}),
    ("authorization", {"name": "Authorization", "description": "Permission and ownership checks."}),
    ("validation", {"name": "Validation", "description": "Inputs or business rules are not enforced."}),
    ("retry_idempotency", {"name": "Retry and idempotency", "description": "Retries duplicate or amplify effects."}),
    ("distributed_consistency", {"name": "Distributed consistency",
                                 "description": "Replicas, events, or services disagree."}),
    ("configuration", {"name": "Configuration", "description": "Wrong settings, defaults, or limits."}),
    ("time_handling", {"name": "Time handling", "description": "Time zones, clocks, deadlines, and calendars."}),
    ("observability", {"name": "Observability", "description": "Errors hidden by logging or aggregation."}),
    ("data_reasoning", {"name": "Data and statistical reasoning",
                        "description": "Metrics, models, or aggregations are defined incorrectly.", "extension": True}),
])

# PRD 10.1 debugging skills.
DEBUGGING_SKILLS: "OrderedDict[str, dict]" = OrderedDict([
    ("stack_trace_analysis", {"name": "Stack-trace analysis"}),
    ("log_investigation", {"name": "Log investigation"}),
    ("reproduction", {"name": "Reproduction"}),
    ("binary_search_debugging", {"name": "Binary search debugging"}),
    ("invariant_reasoning", {"name": "Invariant reasoning"}),
    ("differential_debugging", {"name": "Differential debugging"}),
    ("state_inspection", {"name": "State inspection"}),
    ("concurrency_reasoning", {"name": "Concurrency reasoning"}),
    ("contract_analysis", {"name": "Contract analysis"}),
    ("dependency_analysis", {"name": "Dependency analysis"}),
    ("performance_profiling", {"name": "Performance profiling"}),
    ("regression_testing", {"name": "Regression testing"}),
])

# Assessment report competency areas (PRD 9.6) and the categories/skills that feed each one.
COMPETENCY_AREAS: "OrderedDict[str, dict]" = OrderedDict([
    ("root_cause_analysis", {"name": "Root-cause analysis", "dimension": "diagnosis"}),
    ("debugging_methodology", {"name": "Debugging methodology", "dimension": "verification",
                               "skills": ["reproduction", "differential_debugging", "binary_search_debugging",
                                          "log_investigation", "stack_trace_analysis"]}),
    ("code_correctness", {"name": "Code correctness", "dimension": "correctness"}),
    ("backend_engineering", {"name": "Backend engineering", "dimension": "correctness",
                             "bug_categories": ["validation", "authorization", "authentication",
                                                "retry_idempotency", "state_corruption", "configuration"]}),
    ("concurrency", {"name": "Concurrency", "dimension": "correctness",
                     "bug_categories": ["race_condition", "deadlock"]}),
    ("database_reasoning", {"name": "Database reasoning", "dimension": "correctness",
                            "bug_categories": ["database_transactions", "caching", "distributed_consistency"]}),
    ("testing_verification", {"name": "Testing and verification", "dimension": "verification"}),
    ("code_quality", {"name": "Code quality", "dimension": "quality"}),
])

# Concept graph (PRD 10.4): concept -> children. Leaves link to bug categories and skills.
CONCEPT_GRAPH = {
    "concurrency": {"name": "Concurrency", "children": ["race-conditions", "deadlocks", "distributed-consistency"],
                    "bug_categories": [], "skills": ["concurrency_reasoning"]},
    "race-conditions": {"name": "Race conditions", "children": ["shared-state", "atomic-operations", "mutex"],
                        "bug_categories": ["race_condition"], "skills": ["concurrency_reasoning"]},
    "shared-state": {"name": "Shared state", "children": [], "bug_categories": ["race_condition", "state_corruption"],
                     "skills": ["state_inspection"]},
    "atomic-operations": {"name": "Atomic operations", "children": [],
                          "bug_categories": ["race_condition", "database_transactions"],
                          "skills": ["invariant_reasoning"]},
    "mutex": {"name": "Mutex", "children": [], "bug_categories": ["race_condition", "deadlock"],
              "skills": ["concurrency_reasoning"]},
    "deadlocks": {"name": "Deadlocks", "children": ["lock-ordering", "resource-contention"],
                  "bug_categories": ["deadlock"], "skills": ["concurrency_reasoning"]},
    "lock-ordering": {"name": "Lock ordering", "children": [], "bug_categories": ["deadlock"],
                      "skills": ["concurrency_reasoning"]},
    "resource-contention": {"name": "Resource contention", "children": [],
                            "bug_categories": ["deadlock", "resource_leak"], "skills": ["performance_profiling"]},
    "distributed-consistency": {"name": "Distributed consistency", "children": ["idempotency", "transactions"],
                                "bug_categories": ["distributed_consistency"], "skills": ["dependency_analysis"]},
    "idempotency": {"name": "Idempotency", "children": [], "bug_categories": ["retry_idempotency"],
                    "skills": ["invariant_reasoning"]},
    "transactions": {"name": "Transactions", "children": [], "bug_categories": ["database_transactions"],
                     "skills": ["state_inspection"]},
    "correctness": {"name": "Program correctness", "children": ["boundaries", "null-safety", "numbers", "exceptions"],
                    "bug_categories": ["logic_error"], "skills": ["invariant_reasoning"]},
    "boundaries": {"name": "Boundaries and empty inputs", "children": [], "bug_categories": ["boundary_condition"],
                   "skills": ["contract_analysis"]},
    "null-safety": {"name": "Null safety", "children": [], "bug_categories": ["nullability"],
                    "skills": ["stack_trace_analysis"]},
    "numbers": {"name": "Numeric representation", "children": [], "bug_categories": ["numeric_precision"],
                "skills": ["state_inspection"]},
    "exceptions": {"name": "Error handling", "children": [], "bug_categories": ["runtime_exception", "observability"],
                   "skills": ["stack_trace_analysis"]},
    "contracts": {"name": "Contracts and data", "children": ["validation-rules", "data-formats", "time"],
                  "bug_categories": [], "skills": ["contract_analysis"]},
    "validation-rules": {"name": "Validation rules", "children": [], "bug_categories": ["validation", "authorization"],
                         "skills": ["contract_analysis"]},
    "data-formats": {"name": "Data formats", "children": [], "bug_categories": ["serialization"],
                     "skills": ["differential_debugging"]},
    "time": {"name": "Time and clocks", "children": [], "bug_categories": ["time_handling"],
             "skills": ["state_inspection"]},
    "operations": {"name": "Operations", "children": ["caching-concept", "resources", "observability-concept"],
                   "bug_categories": ["configuration"], "skills": ["log_investigation"]},
    "caching-concept": {"name": "Caching", "children": [], "bug_categories": ["caching"],
                        "skills": ["state_inspection"]},
    "resources": {"name": "Resource lifecycles", "children": [], "bug_categories": ["resource_leak"],
                  "skills": ["performance_profiling"]},
    "observability-concept": {"name": "Observability", "children": [], "bug_categories": ["observability"],
                              "skills": ["log_investigation"]},
}

# Tag -> bug categories. Tags are the catalog's existing vocabulary.
TAG_CATEGORIES = {
    "concurrency": ["race_condition"], "locks": ["race_condition"], "atomicity": ["race_condition"],
    "optimistic-concurrency": ["race_condition"], "stale-writes": ["race_condition", "distributed_consistency"],
    "fencing": ["distributed_consistency"], "channels": ["deadlock"], "termination": ["deadlock"],
    "transactions": ["database_transactions"], "rollback": ["database_transactions"],
    "two-phase-commit": ["database_transactions", "distributed_consistency"], "outbox": ["database_transactions"],
    "write-ahead-log": ["database_transactions"], "sagas": ["distributed_consistency"],
    "compensation": ["distributed_consistency"], "durability": ["database_transactions"],
    "idempotency": ["retry_idempotency"], "retries": ["retry_idempotency"], "deduplication": ["retry_idempotency"],
    "redelivery": ["retry_idempotency"], "at-least-once": ["retry_idempotency"], "backoff": ["retry_idempotency"],
    "duplicates": ["retry_idempotency"], "request-coalescing": ["retry_idempotency"],
    "caching": ["caching"], "cache": ["caching"], "invalidation": ["caching"], "eviction": ["caching"],
    "replication": ["distributed_consistency"], "consistency": ["distributed_consistency"],
    "quorums": ["distributed_consistency"], "quorum": ["distributed_consistency"], "crdt": ["distributed_consistency"],
    "raft": ["distributed_consistency"], "consensus": ["distributed_consistency"],
    "leader-election": ["distributed_consistency"], "read-repair": ["distributed_consistency"],
    "vector-clocks": ["distributed_consistency"], "conflict-resolution": ["distributed_consistency"],
    "event-sourcing": ["distributed_consistency"], "offsets": ["distributed_consistency"],
    "leases": ["distributed_consistency", "time_handling"],
    "authorization": ["authorization"], "rbac": ["authorization"], "ownership": ["authorization"],
    "separation-of-duties": ["authorization"], "policy-gates": ["authorization"], "security": ["authorization"],
    "identity": ["authentication"],
    "validation": ["validation"], "eligibility": ["validation"], "invariants": ["validation"],
    "length-validation": ["validation"], "constraints": ["validation"], "limits": ["validation"],
    "parsing": ["serialization"], "json": ["serialization"], "encoding": ["serialization"],
    "serialization": ["serialization"], "decoding": ["serialization"], "escaping": ["serialization"],
    "unicode": ["serialization"], "formatting": ["serialization"], "iso-8601": ["serialization", "time_handling"],
    "gson": ["serialization"], "schema": ["serialization"], "regex": ["serialization"],
    "dates": ["time_handling"], "time": ["time_handling"], "time-zones": ["time_handling"],
    "timezones": ["time_handling"], "calendar": ["time_handling"], "datetime": ["time_handling"],
    "timestamps": ["time_handling"], "clocks": ["time_handling"], "deadlines": ["time_handling"],
    "timeouts": ["time_handling", "configuration"], "expiration": ["time_handling"], "expiry": ["time_handling"],
    "leap-years": ["time_handling"], "time-windows": ["time_handling"], "scheduling": ["time_handling"],
    "sla": ["time_handling"], "timers": ["time_handling"], "effective-dating": ["time_handling"],
    "null": ["nullability"], "null-pointers": ["nullability"], "nil-pointers": ["nullability"],
    "optional-values": ["nullability"], "optional-fields": ["nullability"], "truthiness": ["nullability"],
    "maps": ["nullability"], "initialization": ["nullability"],
    "exceptions": ["runtime_exception"], "error-handling": ["runtime_exception"], "type-assertions": ["runtime_exception"],
    "casting": ["runtime_exception"], "autoboxing": ["runtime_exception"], "division": ["runtime_exception"],
    "recursion": ["runtime_exception"], "iterators": ["runtime_exception"], "mutability": ["state_corruption"],
    "aliasing": ["state_corruption"], "mutable-defaults": ["state_corruption"], "copying": ["state_corruption"],
    "state": ["state_corruption"], "state-machine": ["state_corruption"], "state-machines": ["state_corruption"],
    "cumulative-state": ["state_corruption"], "inventory": ["state_corruption"], "slices": ["state_corruption"],
    "overflow": ["numeric_precision"], "integer-arithmetic": ["numeric_precision"], "rounding": ["numeric_precision"],
    "precision": ["numeric_precision"], "floating-point": ["numeric_precision"], "money": ["numeric_precision"],
    "bigint": ["numeric_precision"], "big-integers": ["numeric_precision"], "unsigned-integers": ["numeric_precision"],
    "integer-width": ["numeric_precision"], "decimals": ["numeric_precision"], "bigdecimal": ["numeric_precision"],
    "integer-division": ["numeric_precision"], "negative-zero": ["numeric_precision"],
    "numerical-stability": ["numeric_precision"], "exact-integers": ["numeric_precision"],
    "off-by-one": ["boundary_condition"], "bounds": ["boundary_condition"], "boundaries": ["boundary_condition"],
    "empty-input": ["boundary_condition"], "sentinels": ["boundary_condition"], "loop-boundaries": ["boundary_condition"],
    "base-cases": ["boundary_condition"], "ranges": ["boundary_condition"], "indexing": ["boundary_condition"],
    "pagination": ["boundary_condition"], "negative-values": ["boundary_condition"], "zero": ["boundary_condition"],
    "configuration": ["configuration"], "defaults": ["configuration"], "thresholds": ["configuration"],
    "rate-limiting": ["configuration"], "capacity": ["configuration"], "autoscaling": ["configuration"],
    "logging": ["observability"], "monitoring": ["observability"], "metrics": ["observability", "data_reasoning"],
    "health-checks": ["observability"], "failure-detection": ["observability"], "heartbeats": ["observability"],
    "resource-lifecycle": ["resource_leak"], "cleanup": ["resource_leak"], "graceful-shutdown": ["resource_leak"],
    "bulkheads": ["resource_leak"], "backpressure": ["resource_leak"],
    "statistics": ["data_reasoning"], "analytics": ["data_reasoning"], "product-analytics": ["data_reasoning"],
    "leakage": ["data_reasoning"], "evaluation": ["data_reasoning"], "classification": ["data_reasoning"],
    "regression": ["data_reasoning"], "cohorts": ["data_reasoning"], "retention": ["data_reasoning"],
    "funnel": ["data_reasoning"], "attribution": ["data_reasoning"], "percentiles": ["data_reasoning"],
}

CATEGORY_DEFAULTS = {
    "runtime": {"bug_categories": ["runtime_exception"], "skills": ["stack_trace_analysis", "state_inspection"]},
    "logic": {"bug_categories": ["logic_error"], "skills": ["invariant_reasoning", "differential_debugging"]},
    "business": {"bug_categories": ["validation"],
                 "skills": ["invariant_reasoning", "contract_analysis", "state_inspection"]},
    "edge": {"bug_categories": ["boundary_condition"], "skills": ["contract_analysis", "regression_testing"]},
    "system_design": {"bug_categories": ["distributed_consistency"],
                      "skills": ["dependency_analysis", "invariant_reasoning"]},
    "data_science": {"bug_categories": ["data_reasoning"], "skills": ["differential_debugging", "invariant_reasoning"]},
    "data_analytics": {"bug_categories": ["data_reasoning"], "skills": ["differential_debugging", "state_inspection"]},
}

CATEGORY_SKILLS = {
    "race_condition": ["concurrency_reasoning"], "deadlock": ["concurrency_reasoning"],
    "database_transactions": ["state_inspection"], "distributed_consistency": ["dependency_analysis"],
    "retry_idempotency": ["invariant_reasoning"], "caching": ["state_inspection"],
    "time_handling": ["state_inspection"], "serialization": ["differential_debugging"],
    "resource_leak": ["performance_profiling"], "observability": ["log_investigation"],
    "boundary_condition": ["binary_search_debugging"], "runtime_exception": ["stack_trace_analysis"],
    "nullability": ["stack_trace_analysis"], "numeric_precision": ["differential_debugging"],
}


def _unique(values):
    return list(dict.fromkeys(value for value in values if value))


def classify(category: str, tags: list[str], override: dict | None = None) -> dict:
    """Deterministic bug categories and skills for a challenge. The first bug category is primary."""
    if override and (override.get("bug_categories") or override.get("skills")):
        bugs = [b for b in override.get("bug_categories", []) if b in BUG_CATEGORIES]
        skills = [s for s in override.get("skills", []) if s in DEBUGGING_SKILLS]
        return {"bug_categories": _unique(bugs) or CATEGORY_DEFAULTS.get(category, {}).get("bug_categories", []),
                "skills": _unique(skills)}
    default = CATEGORY_DEFAULTS.get(category, {"bug_categories": ["logic_error"], "skills": ["invariant_reasoning"]})
    from_tags = [bug for tag in tags for bug in TAG_CATEGORIES.get(tag, [])]
    # Tag-derived categories are more specific than the broad catalog category, so they lead.
    bugs = _unique(from_tags + default["bug_categories"])[:4]
    skills = _unique(default["skills"] + [skill for bug in bugs for skill in CATEGORY_SKILLS.get(bug, [])]
                     + (["reproduction"] if category in {"business", "edge", "system_design"} else []))
    return {"bug_categories": bugs, "skills": skills[:5]}


def classify_problem(problem) -> dict:
    return classify(problem.category, list(problem.tags or []), getattr(problem, "taxonomy", None))


def describe(classification: dict) -> dict:
    """Attach display names to a classification for API responses."""
    return {
        "bug_categories": [{"id": bug, "name": BUG_CATEGORIES[bug]["name"]}
                           for bug in classification.get("bug_categories", []) if bug in BUG_CATEGORIES],
        "skills": [{"id": skill, "name": DEBUGGING_SKILLS[skill]["name"]}
                   for skill in classification.get("skills", []) if skill in DEBUGGING_SKILLS],
    }


def related_categories(bug: str) -> list[str]:
    """Categories that share a concept-graph node with ``bug``; used for partial diagnosis credit."""
    related = set()
    for node in CONCEPT_GRAPH.values():
        if bug in node["bug_categories"]:
            related.update(node["bug_categories"])
            for child in node["children"]:
                related.update(CONCEPT_GRAPH[child]["bug_categories"])
    for node in CONCEPT_GRAPH.values():
        if any(bug in CONCEPT_GRAPH[child]["bug_categories"] for child in node["children"]):
            related.update(node["bug_categories"])
    related.discard(bug)
    return sorted(related)


def concepts_for(bug_categories: list[str]) -> list[str]:
    return [concept for concept, node in CONCEPT_GRAPH.items() if set(node["bug_categories"]) & set(bug_categories)]


def taxonomy_document() -> dict:
    return {
        "version": TAXONOMY_VERSION,
        "bug_categories": [{"id": key, **value} for key, value in BUG_CATEGORIES.items()],
        "skills": [{"id": key, **value} for key, value in DEBUGGING_SKILLS.items()],
        "competency_areas": [{"id": key, **value} for key, value in COMPETENCY_AREAS.items()],
        "concept_graph": [{"id": key, **value} for key, value in CONCEPT_GRAPH.items()],
    }
