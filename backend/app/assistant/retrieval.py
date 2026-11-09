"""Adaptive retrieval and reranking (PRD 8.5; AR-005, AR-009).

Candidates come from Chroma (or the bundled summaries when Chroma is unavailable) for the problem's
language plus language-agnostic references. They are reranked by query similarity, topic overlap
with the challenge's bug categories, tags and failure type, source reliability, language match, and
novelty relative to sources already cited in earlier hints. Only official documentation is
retrievable; problem-specific knowledge stays in the database.
"""
import re
import time

from app import rag

FAILURE_TOPICS = {
    "compile_error": ["compilation", "syntax"],
    "runtime_error": ["runtime_exception", "exceptions", "stack_trace"],
    "timeout": ["deadlock", "concurrency", "performance"],
    "memory": ["resource_leak"],
    "output_limit": ["serialization"],
}
INTENT_TOPICS = {
    "explain_runtime_error": ["runtime_exception", "exceptions", "stack_trace"],
    "reproduction_strategy": ["testing"],
}
# Error-message fragments mapped to topics, so a KeyError retrieves dictionary/None documentation.
MESSAGE_TOPICS = [
    (r"KeyError|NoneType|NullPointer|null|undefined|nil (map|pointer)|Optional", ["nullability"]),
    (r"IndexError|out of range|OutOfBounds|index out", ["boundary_condition", "indexing"]),
    (r"ZeroDivision|divide by zero|/ by zero", ["division", "runtime_exception"]),
    (r"JSON|json|Unexpected token|serialize|circular", ["serialization", "json"]),
    (r"deadlock|goroutines are asleep", ["deadlock", "channels"]),
    (r"BigInt", ["bigint", "numeric_precision"]),
    (r"overflow|NumberFormat|Non-terminating", ["numeric_precision"]),
    (r"ConcurrentModification|changed size during iteration", ["state_corruption", "iteration"]),
    (r"datetime|offset-naive|offset-aware|tzinfo|time zone|timezone", ["time_handling"]),
]
WEIGHTS = {"similarity": 0.45, "topics": 0.35, "reliability": 0.1, "language": 0.1}
REPEAT_PENALTY = 0.25


def normalize(topic: str) -> str:
    return topic.strip().lower().replace("-", "_").replace(" ", "_")


def query_topics(context: dict, intent: str) -> set[str]:
    problem = context["problem"]
    topics = {normalize(value) for value in problem["bug_categories"] + problem["tags"]}
    execution = context.get("execution") or {}
    topics.update(FAILURE_TOPICS.get(execution.get("failure_type") or "", []))
    topics.update(INTENT_TOPICS.get(intent, []))
    message = execution.get("message") or ""
    for pattern, names in MESSAGE_TOPICS:
        if message and re.search(pattern, message):
            topics.update(names)
    return {normalize(topic) for topic in topics if topic}


def build_query(context: dict, intent: str, question: str = "") -> str:
    problem = context["problem"]
    execution = context.get("execution") or {}
    parts = [question or "", problem["title"]]
    if intent in {"explain_problem", "progressive_hint", "explain_concept", "find_documentation"}:
        parts.append(problem["summary"])
    parts += problem["bug_category_names"] + problem["tags"]
    if execution.get("message"):
        # The last line of an error output usually names the exception.
        lines = [line.strip() for line in execution["message"].splitlines() if line.strip()]
        parts += lines[-2:]
    parts += context["code"]["changed_identifiers"][:5]
    if intent == "review_diagnosis" and context.get("diagnosis"):
        parts += [context["diagnosis"]["root_cause"], context["diagnosis"]["violated_invariant"]]
    return " ".join(part for part in parts if part)[:1200]


def adaptive_retrieve(context: dict, intent: str, question: str = "", *, previous_urls=(), limit: int = 3):
    """Return (documents, metadata). Documents keep title, url, text, language, topics and a score."""
    started = time.perf_counter()
    language = context["problem"]["language"]
    query = build_query(context, intent, question)
    topics = query_topics(context, intent)
    candidates, method = rag.retrieve_candidates(query, language, limit=8)
    previous = {url for url in previous_urls if url}
    query_vector = rag.local_embedding(query)
    ranked = []
    for position, doc in enumerate(candidates):
        doc_topics = {normalize(topic) for topic in rag.doc_topics(doc)}
        overlap = sorted(doc_topics & topics)
        similarity = max(0.0, rag.similarity(query_vector, rag.local_embedding(f"{doc['title']}. {doc['text']}")))
        reliability = 1.0 if (doc.get("source_type") or "official") == "official" else 0.5
        language_score = 1.0 if doc.get("language") == language else 0.7
        repeated = doc.get("url") in previous
        score = (WEIGHTS["similarity"] * similarity + WEIGHTS["topics"] * min(1.0, len(overlap) / 2)
                 + WEIGHTS["reliability"] * reliability + WEIGHTS["language"] * language_score
                 - (REPEAT_PENALTY if repeated else 0.0))
        ranked.append((round(score, 4), -position, doc, {"similarity": round(similarity, 4), "topics": overlap,
                                                          "repeated": repeated}))
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    selected = ranked[:limit]
    docs = [{"id": doc.get("id") or doc.get("url"), "title": doc["title"], "url": doc["url"], "text": doc["text"],
             "language": doc.get("language"), "topics": rag.doc_topics(doc), "score": score,
             "source_type": doc.get("source_type") or "official"} for score, _, doc, _ in selected]
    metadata = {
        "method": method, "intent": intent, "topics": sorted(topics)[:16],
        "candidates": [{"id": doc.get("id") or doc.get("url"), "title": doc["title"], "score": score,
                        "similarity": features["similarity"], "topic_overlap": features["topics"],
                        "repeated": features["repeated"]} for score, _, doc, features in ranked],
        "selected": [doc["id"] for doc in docs], "latency_ms": round((time.perf_counter() - started) * 1000, 2),
    }
    return docs, metadata
