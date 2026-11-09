"""Context-aware debugging assistant API (PRD 8.6, 11.5)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assistant import service
from app.assistant.tasks import assistant_task
from app.auth import current_user
from app.db import get_db
from app.limits import rate_limit
from app.models import AIInteraction, User
from app.schemas import Language

router = APIRouter(prefix="/api", tags=["assistant"])
SessionId = Field(default=None, min_length=36, max_length=36)


class WhyFixFailedRequest(BaseModel):
    language: Language
    code: str | None = Field(default=None, max_length=50000)
    submission_id: str | None = Field(default=None, max_length=36)
    assessment_session_id: str | None = SessionId
    incident_session_id: str | None = SessionId


class AssistantRequest(WhyFixFailedRequest):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question", mode="before")
    @classmethod
    def strip_question(cls, value):
        return value.strip() if isinstance(value, str) else value


def _queue(db, user, slug: str, data: WhyFixFailedRequest, *, question: str = "", intent: str | None = None):
    from app.api import enqueue, get_problem
    rate_limit(f"assistant:{user.id}", 10)
    problem = get_problem(db, slug, user)
    interaction = service.create_interaction(
        db, user, problem, language=data.language, question=question, code=data.code,
        submission_id=data.submission_id, assessment_session_id=data.assessment_session_id,
        incident_session_id=data.incident_session_id, intent=intent)
    db.commit()
    enqueue(db, assistant_task, interaction)
    return service.interaction_view(interaction)


@router.post("/problems/{slug}/debug-assistant", status_code=202)
def debug_assistant(slug: str, data: AssistantRequest, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    return _queue(db, user, slug, data, question=data.question)


@router.post("/problems/{slug}/why-fix-failed", status_code=202)
def why_fix_failed(slug: str, data: WhyFixFailedRequest, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    return _queue(db, user, slug, data, question="Why did my fix fail?", intent="why_fix_failed")


@router.get("/ai-interactions/{interaction_id}")
def get_interaction(interaction_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(AIInteraction, interaction_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "Assistant request not found.")
    return service.interaction_view(row)


@router.get("/problems/{slug}/ai-interactions")
def problem_interactions(slug: str, page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=50),
                         user: User = Depends(current_user), db: Session = Depends(get_db)):
    from app.api import get_problem
    problem = get_problem(db, slug, user)
    condition = [AIInteraction.user_id == user.id, AIInteraction.problem_id == problem.id]
    total = db.scalar(select(func.count()).select_from(AIInteraction).where(*condition))
    rows = db.scalars(select(AIInteraction).where(*condition).order_by(AIInteraction.created_at.desc())
                      .offset((page - 1) * limit).limit(limit))
    return {"items": [service.interaction_view(row) for row in rows], "total": total, "page": page, "limit": limit}
