from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from app import rag
from app.assistant.retrieval import adaptive_retrieve, query_topics
from app.catalog import CATALOG
from app.documents import DOCUMENTS

OFFICIAL_HOSTS = {"docs.python.org", "docs.oracle.com", "developer.mozilla.org", "eel.is", "go.dev", "pkg.go.dev",
                  "docs.sqlalchemy.org", "www.postgresql.org", "www.rfc-editor.org"}


def offline():
    raise ConnectionError("Chroma offline")


def make_context(language="python", bug_categories=("race_condition",), tags=("concurrency",), failure=None,
                 message=""):
    execution = None if failure is None else {
        "failure_type": failure, "message": message, "failing_public": [], "hidden_failed": 0,
        "hidden_total": 0, "hidden_evaluated": False}
    return {
        "version": "ctx-v1",
        "problem": {"title": "Two withdrawals, one balance", "summary": "Concurrent withdrawals overdraw a wallet.",
                    "language": language, "bug_categories": list(bug_categories),
                    "bug_category_names": ["Race condition"], "tags": list(tags), "requirements": [],
                    "examples": [], "skills": []},
        "execution": execution, "code": {"changed_identifiers": ["withdraw", "balance"], "current": "", "original": ""},
        "diagnosis": None, "previous_hints": [],
    }


def test_documents_are_official_reviewed_and_tagged():
    ids = [doc["id"] for doc in DOCUMENTS]
    assert len(ids) == len(set(ids)) and len(DOCUMENTS) >= 12 + 15
    for doc in DOCUMENTS:
        assert urlsplit(doc["url"]).scheme == "https" and urlsplit(doc["url"]).hostname in OFFICIAL_HOSTS
        assert doc["language"] in {"python", "java", "javascript", "cpp", "go", "general"}
        assert doc["topics"] and all(isinstance(topic, str) for topic in doc["topics"])
        assert 80 <= len(doc["text"]) <= 900
    assert {doc["language"] for doc in DOCUMENTS} >= {"python", "java", "javascript", "cpp", "go", "general"}


def test_bundled_rerank_prefers_matching_topics_and_language_without_chroma(monkeypatch):
    monkeypatch.setattr(rag, "collection", offline)
    docs, metadata = adaptive_retrieve(make_context(), "why_fix_failed", "Why do both withdrawals succeed?")
    assert metadata["method"] == "bundled-docs" and len(docs) == 3
    assert docs[0]["id"] == "python-locks"
    assert all(doc["language"] in {"python", "general"} for doc in docs)
    assert "race_condition" in metadata["topics"] and metadata["latency_ms"] >= 0
    assert [doc["id"] for doc in docs] == metadata["selected"]
    assert all(doc["score"] >= later["score"] for doc, later in zip(docs, docs[1:], strict=False))
    go_docs, _ = adaptive_retrieve(make_context(language="go"), "why_fix_failed", "data race on balance")
    assert go_docs[0]["id"] == "go-sync-mutex"
    assert all(doc["language"] in {"go", "general"} for doc in go_docs)


def test_failure_type_and_error_message_steer_retrieval(monkeypatch):
    monkeypatch.setattr(rag, "collection", offline)
    context = make_context(bug_categories=("logic_error",), tags=(), failure="runtime_error",
                           message="Traceback\nKeyError: 'discount'")
    assert {"nullability", "runtime_exception"} <= query_topics(context, "explain_runtime_error")
    docs, _ = adaptive_retrieve(context, "explain_runtime_error", "What does this error mean?")
    assert "python-exceptions" in [doc["id"] for doc in docs]
    timezone = make_context(bug_categories=("time_handling",), tags=("time-zones",))
    docs, _ = adaptive_retrieve(timezone, "explain_concept", "how do offsets work")
    assert {"python-datetime-aware", "rfc3339-timestamps"} & {doc["id"] for doc in docs}


def test_novelty_penalizes_sources_already_cited_in_hints(monkeypatch):
    monkeypatch.setattr(rag, "collection", offline)
    first, _ = adaptive_retrieve(make_context(), "progressive_hint")
    repeat, metadata = adaptive_retrieve(make_context(), "progressive_hint", previous_urls={first[0]["url"]})
    assert repeat[0]["url"] != first[0]["url"]
    assert any(row["repeated"] for row in metadata["candidates"])


class FakeCollection:
    def __init__(self, rows):
        self.rows, self.upserts, self.queries = rows, [], []

    def count(self):
        return len(self.rows) or 1

    def upsert(self, **kwargs):
        self.upserts.append(kwargs)

    def query(self, **kwargs):
        self.queries.append(kwargs)
        return {"ids": [[row["id"] for row in self.rows]], "documents": [[row["text"] for row in self.rows]],
                "metadatas": [[rag.document_metadata(row) for row in self.rows]]}


def test_chroma_candidates_include_general_docs_and_are_reranked(monkeypatch):
    # Chroma returns a poor order; the reranker restores the topic match first.
    rows = [next(doc for doc in DOCUMENTS if doc["id"] == key)
            for key in ("python-sequences", "rfc3339-timestamps", "python-locks", "postgres-transaction-isolation")]
    fake = FakeCollection(rows)
    monkeypatch.setattr(rag, "collection", lambda: fake)
    docs, metadata = adaptive_retrieve(make_context(), "why_fix_failed", "overdraft")
    assert metadata["method"] == "chroma-lexical"
    assert fake.queries[0]["where"] == {"language": {"$in": ["python", "general"]}}
    assert docs[0]["id"] in {"python-locks", "postgres-transaction-isolation"}
    assert docs[-1]["id"] != "python-locks"


def test_ingestion_stores_scalar_metadata_and_never_problem_knowledge(monkeypatch):
    fake = FakeCollection([])
    monkeypatch.setattr(rag, "collection", lambda: fake)
    assert rag.ingest() == len(DOCUMENTS)
    ids = [doc_id for batch in fake.upserts for doc_id in batch["ids"]]
    texts = [text for batch in fake.upserts for text in batch["documents"]]
    metadatas = [meta for batch in fake.upserts for meta in batch["metadatas"]]
    assert ids == [doc["id"] for doc in DOCUMENTS]
    assert all(isinstance(value, (str, int, float, bool)) for meta in metadatas for value in meta.values())
    assert all(urlsplit(meta["url"]).hostname in OFFICIAL_HOSTS for meta in metadatas)
    corpus = "\n".join(texts)
    # Curated hints, explanations and reference solutions are problem-specific knowledge: never indexed.
    for item in CATALOG:
        assert item["explanation"] not in corpus
        assert not any(hint in corpus for hint in item["hints"])
        assert not any(source.strip() in corpus for source in item["solutions"].values())


@pytest.mark.parametrize("language", ["python", "java", "javascript", "cpp", "go"])
def test_every_language_has_language_specific_candidates(monkeypatch, language):
    monkeypatch.setattr(rag, "collection", offline)
    docs, method = rag.retrieve_candidates("error handling and boundaries", language)
    assert method == "bundled-docs"
    assert any(doc["language"] == language for doc in docs)
    assert all(doc["language"] in {language, "general"} for doc in docs)


def test_legacy_retrieve_keeps_language_only_results(monkeypatch):
    monkeypatch.setattr(rag, "collection", offline)
    problem = SimpleNamespace(title="Rollback", summary="Preserve a wallet balance on transaction failure",
                              tags=["transactions"], hints=["Validate before changing balances."])
    docs, method = rag.retrieve("transaction rollback", "python")
    assert method == "bundled-docs" and all(doc["language"] == "python" for doc in docs)
    assert rag.generate_hint(problem, "python", 1)["retrieval"] == "bundled-docs"
