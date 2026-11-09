import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    bio: Mapped[str] = mapped_column(String(280), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Problem(Base):
    __tablename__ = "problems"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(150))
    summary: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(30), index=True)
    difficulty: Mapped[str] = mapped_column(String(10), index=True)
    tags: Mapped[list] = mapped_column(JSON)
    requirements: Mapped[list] = mapped_column(JSON)
    starters: Mapped[dict] = mapped_column(JSON)
    solutions: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)
    hints: Mapped[list] = mapped_column(JSON)
    tests: Mapped[list] = mapped_column(JSON)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=15)
    # public: listed in the library. incident / assessment: reachable only through an owning
    # session. draft: awaiting quality approval; visible to administrators only.
    visibility: Mapped[str] = mapped_column(String(20), default="public", server_default="public", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    content_hash: Mapped[str | None] = mapped_column(String(64))
    # off | optional | required. Assessments and incidents can require a diagnosis independently.
    diagnosis_mode: Mapped[str] = mapped_column(String(10), default="optional", server_default="optional")
    diagnosis_rubric: Mapped[dict | None] = mapped_column(JSON)
    rubric_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    taxonomy: Mapped[dict | None] = mapped_column(JSON)
    quality_status: Mapped[str] = mapped_column(String(20), default="unvalidated", server_default="unvalidated")
    extra: Mapped[dict | None] = mapped_column(JSON)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    language: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(10))
    kind: Mapped[str] = mapped_column(String(10), default="submit")
    code: Mapped[str] = mapped_column(Text)
    prompt: Mapped[str] = mapped_column(Text, default="")
    generated_code: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    results: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    runtime_ms: Mapped[float | None] = mapped_column(Float)
    memory_kb: Mapped[int | None] = mapped_column(Integer)
    turnaround_ms: Mapped[float | None] = mapped_column(Float)
    llm_tokens: Mapped[int | None] = mapped_column(Integer)
    prompt_words: Mapped[int] = mapped_column(Integer, default=0)
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_id: Mapped[str | None] = mapped_column(ForeignKey("challenge_attempts.id", ondelete="SET NULL"), index=True)
    assessment_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"), index=True)
    diagnosis_id: Mapped[str | None] = mapped_column(ForeignKey("diagnoses.id", ondelete="SET NULL"))
    diff_stats: Mapped[dict | None] = mapped_column(JSON)
    quality: Mapped[dict | None] = mapped_column(JSON)
    __table_args__ = (Index("ix_submission_progress", "user_id", "problem_id", "kind", "status"),)


class Hint(Base):
    __tablename__ = "hints"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"))
    language: Mapped[str] = mapped_column(String(20))
    level: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    text: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    retrieval: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    attempt_id: Mapped[str | None] = mapped_column(ForeignKey("challenge_attempts.id", ondelete="SET NULL"), index=True)
    assessment_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"), index=True)
    # Adaptive-hint request context (current code is transient and removed after generation).
    context: Mapped[dict | None] = mapped_column(JSON)


class Bookmark(Base):
    __tablename__ = "bookmarks"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), primary_key=True)


class Activity(Base):
    __tablename__ = "activities"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)


class Discussion(Base):
    __tablename__ = "discussions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    problem_id: Mapped[int | None] = mapped_column(ForeignKey("problems.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class Reply(Base):
    __tablename__ = "replies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    discussion_id: Mapped[str] = mapped_column(ForeignKey("discussions.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Vote(Base):
    __tablename__ = "votes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    discussion_id: Mapped[str] = mapped_column(ForeignKey("discussions.id", ondelete="CASCADE"))
    __table_args__ = (UniqueConstraint("user_id", "discussion_id"),)


class ProblemSubmission(Base):
    __tablename__ = "problem_submissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(150))
    slug: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(30))
    difficulty: Mapped[str] = mapped_column(String(10))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(20))
    buggy_code: Mapped[str] = mapped_column(Text)
    fixed_code: Mapped[str] = mapped_column(Text)
    test_cases: Mapped[list] = mapped_column(JSON, default=list)
    hint: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    admin_notes: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    # The draft problem created from this submission for quality validation and publication.
    problem_id: Mapped[int | None] = mapped_column(ForeignKey("problems.id", ondelete="SET NULL"))


# ── Debugging assessment platform (PRD 2.0) ─────────────────────────────────────────────


class ChallengeAttempt(Base):
    """One user's work on one challenge in one context: practice, an incident, or an assessment.

    Diagnoses, submissions, hints, explanations and AI interactions attach to an attempt, so every
    scoring path (practice, incidents, assessments) reads the same records.
    """
    __tablename__ = "challenge_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    # "practice", "incident:<session id>" or "assessment:<session id>"
    scope: Mapped[str] = mapped_column(String(80), default="practice")
    context: Mapped[str] = mapped_column(String(20), default="practice")
    assessment_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"), index=True)
    incident_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("incident_sessions.id", ondelete="CASCADE"), index=True)
    # in_progress | solved | completed (solved and explained) | expired
    status: Mapped[str] = mapped_column(String(20), default="in_progress", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    solved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    diagnosis_score: Mapped[float | None] = mapped_column(Float)
    correctness_score: Mapped[float | None] = mapped_column(Float)
    quality_score: Mapped[float | None] = mapped_column(Float)
    explanation_score: Mapped[float | None] = mapped_column(Float)
    verification_score: Mapped[float | None] = mapped_column(Float)
    time_score: Mapped[float | None] = mapped_column(Float)
    total_score: Mapped[float | None] = mapped_column(Float)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("user_id", "problem_id", "scope", name="uq_attempt_scope"),)


class Diagnosis(Base):
    __tablename__ = "diagnoses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("challenge_attempts.id", ondelete="CASCADE"), index=True)
    assessment_session_id: Mapped[str | None] = mapped_column(String(36), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    language: Mapped[str | None] = mapped_column(String(20))
    defect_category: Mapped[str] = mapped_column(String(40))
    root_cause: Mapped[str] = mapped_column(Text)
    affected_component: Mapped[str] = mapped_column(Text)
    violated_invariant: Mapped[str] = mapped_column(Text)
    proposed_correction: Mapped[str] = mapped_column(Text)
    reproduction_strategy: Mapped[str] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)
    deterministic_score: Mapped[float | None] = mapped_column(Float)
    ai_score: Mapped[float | None] = mapped_column(Float)
    evaluation_details: Mapped[dict] = mapped_column(JSON, default=dict)
    rubric_version: Mapped[int] = mapped_column(Integer, default=1)
    evaluator_version: Mapped[str] = mapped_column(String(40), default="deterministic-v1")
    # skipped | queued | running | completed | failed
    ai_status: Mapped[str] = mapped_column(String(20), default="skipped")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class FixExplanation(Base):
    __tablename__ = "fix_explanations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("challenge_attempts.id", ondelete="CASCADE"), index=True)
    submission_id: Mapped[str | None] = mapped_column(ForeignKey("submissions.id", ondelete="SET NULL"))
    why_failed: Mapped[str] = mapped_column(Text)
    why_works: Mapped[str] = mapped_column(Text)
    invariant_preserved: Mapped[str] = mapped_column(Text)
    side_effects: Mapped[str] = mapped_column(Text, default="")
    additional_tests: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float | None] = mapped_column(Float)
    deterministic_score: Mapped[float | None] = mapped_column(Float)
    ai_score: Mapped[float | None] = mapped_column(Float)
    evaluation_details: Mapped[dict] = mapped_column(JSON, default=dict)
    rubric_version: Mapped[int] = mapped_column(Integer, default=1)
    evaluator_version: Mapped[str] = mapped_column(String(40), default="deterministic-v1")
    ai_status: Mapped[str] = mapped_column(String(20), default="skipped")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), unique=True)
    title: Mapped[str] = mapped_column(String(150))
    summary: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(10))
    level: Mapped[int] = mapped_column(Integer, default=1)
    category: Mapped[str] = mapped_column(String(40), index=True)
    affected_services: Mapped[list] = mapped_column(JSON, default=list)
    impact: Mapped[list] = mapped_column(JSON, default=list)
    expected_behavior: Mapped[str] = mapped_column(Text, default="")
    observed_symptoms: Mapped[list] = mapped_column(JSON, default=list)
    timeline: Mapped[list] = mapped_column(JSON, default=list)
    artifacts: Mapped[list] = mapped_column(JSON, default=list)
    scenarios: Mapped[list] = mapped_column(JSON, default=list)
    evaluation_config: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="published", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class IncidentSession(Base):
    __tablename__ = "incident_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # active | resolved | abandoned
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # {"viewed": {artifact_id: iso timestamp}, ...}; investigation evidence for scoring
    investigation: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[float | None] = mapped_column(Float)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)


class IncidentResolution(Base):
    __tablename__ = "incident_resolutions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("incident_sessions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    diagnosis_id: Mapped[str | None] = mapped_column(ForeignKey("diagnoses.id", ondelete="SET NULL"))
    submission_id: Mapped[str | None] = mapped_column(ForeignKey("submissions.id", ondelete="SET NULL"))
    impact_assessment: Mapped[str] = mapped_column(Text, default="")
    remediation: Mapped[str] = mapped_column(Text, default="")
    prevention: Mapped[str] = mapped_column(Text, default="")
    regression_tests: Mapped[list] = mapped_column(JSON, default=list)
    regression_results: Mapped[list] = mapped_column(JSON, default=list)
    # queued | running | evaluated | error
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    score: Mapped[float | None] = mapped_column(Float)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    rubric_version: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MutationRun(Base):
    __tablename__ = "mutation_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    problem_version: Mapped[int] = mapped_column(Integer, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    language: Mapped[str] = mapped_column(String(20))
    # queued | validating | running | completed | failed
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    total_mutations: Mapped[int] = mapped_column(Integer, default=0)
    killed_mutations: Mapped[int] = mapped_column(Integer, default=0)
    survived_mutations: Mapped[int] = mapped_column(Integer, default=0)
    timed_out_mutations: Mapped[int] = mapped_column(Integer, default=0)
    invalid_mutations: Mapped[int] = mapped_column(Integer, default=0)
    equivalent_mutations: Mapped[int] = mapped_column(Integer, default=0)
    error_mutations: Mapped[int] = mapped_column(Integer, default=0)
    mutation_score: Mapped[float | None] = mapped_column(Float)
    # approved | requires_revision
    gate_status: Mapped[str | None] = mapped_column(String(20))
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    execution_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MutationCase(Base):
    __tablename__ = "mutation_cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("mutation_runs.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    operator: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(300), default="")
    line: Mapped[int | None] = mapped_column(Integer)
    critical: Mapped[bool] = mapped_column(Boolean, default=False)
    original_snippet: Mapped[str] = mapped_column(Text, default="")
    mutated_snippet: Mapped[str] = mapped_column(Text, default="")
    original_code_hash: Mapped[str] = mapped_column(String(64), default="")
    mutated_code_hash: Mapped[str] = mapped_column(String(64), default="")
    mutated_code: Mapped[str] = mapped_column(Text, default="")
    # queued | running | killed | survived | timeout | invalid | equivalent | error
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    failure_classification: Mapped[str | None] = mapped_column(String(30))
    killing_tests: Mapped[list] = mapped_column(JSON, default=list)
    is_equivalent: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    execution_duration_ms: Mapped[float | None] = mapped_column(Float)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QualityGate(Base):
    __tablename__ = "quality_gates"
    category: Mapped[str] = mapped_column(String(30), primary_key=True)
    thresholds: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    updated_by: Mapped[str | None] = mapped_column(String(36))


class AIInteraction(Base):
    __tablename__ = "ai_interactions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    attempt_id: Mapped[str | None] = mapped_column(ForeignKey("challenge_attempts.id", ondelete="SET NULL"), index=True)
    assessment_session_id: Mapped[str | None] = mapped_column(String(36), index=True)
    intent: Mapped[str] = mapped_column(String(40))
    question: Mapped[str] = mapped_column(Text, default="")
    # queued | running | completed | error
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    context_version: Mapped[str] = mapped_column(String(20), default="ctx-v1")
    # Transient request data such as the current editor code; cleared once the response is produced.
    payload: Mapped[dict | None] = mapped_column(JSON)
    context_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    retrieval_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    response_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    response: Mapped[dict | None] = mapped_column(JSON)
    response_text: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    token_usage: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    retrieval_ms: Mapped[float | None] = mapped_column(Float)
    generation_ms: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150))
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    # owner | admin | reviewer
    role: Mapped[str] = mapped_column(String(20), default="reviewer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CompetencyProfile(Base):
    __tablename__ = "competency_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    # {skill or bug-category id: weight}
    weights: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_competency_profile_slug"),)


class Assessment(Base):
    __tablename__ = "assessments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    # individual | interview | specialized | practice
    assessment_type: Mapped[str] = mapped_column(String(20), default="individual")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    # problems (slugs), languages, diagnosis_required, explanation_required, max_attempts,
    # max_sessions, randomize_order, feedback
    configuration: Mapped[dict] = mapped_column(JSON, default=dict)
    scoring_rubric: Mapped[dict] = mapped_column(JSON, default=dict)
    # {"ai": "disabled|guided|enabled", "hints": "disabled|restricted|enabled"}
    assistance_policy: Mapped[dict] = mapped_column(JSON, default=dict)
    # public | private | invitation
    visibility: Mapped[str] = mapped_column(String(20), default="public")
    # draft | published | archived
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    competency_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("competency_profiles.id", ondelete="SET NULL"))
    available_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class AssessmentInvitation(Base):
    __tablename__ = "assessment_invitations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # pending | accepted | revoked | expired
    status: Mapped[str] = mapped_column(String(20), default="pending")
    invited_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    invitation_id: Mapped[str | None] = mapped_column(
        ForeignKey("assessment_invitations.id", ondelete="SET NULL"))
    # active | completed | expired | cancelled
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Immutable copy of the assessment configuration, rubric, policy and version at start.
    config_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    challenge_order: Mapped[list] = mapped_column(JSON, default=list)
    total_score: Mapped[float | None] = mapped_column(Float)
    scoring_details: Mapped[dict] = mapped_column(JSON, default=dict)
    assistance_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    report: Mapped[dict | None] = mapped_column(JSON)
    report_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class Event(Base):
    """Append-only product instrumentation (PRD Phase 0, AS-008, incident investigation evidence)."""
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(60), index=True)
    problem_id: Mapped[int | None] = mapped_column(Integer)
    attempt_id: Mapped[str | None] = mapped_column(String(36), index=True)
    assessment_session_id: Mapped[str | None] = mapped_column(String(36), index=True)
    incident_session_id: Mapped[str | None] = mapped_column(String(36), index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
