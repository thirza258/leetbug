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

