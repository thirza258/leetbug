"""Request bodies for organization endpoints (PRD 9.7)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app import taxonomy
from app.assessments.schemas import AssessmentCreate

Role = Literal["owner", "admin", "reviewer"]
SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{2,99}$"
PROFILE_KEYS = {**taxonomy.COMPETENCY_AREAS, **taxonomy.BUG_CATEGORIES, **taxonomy.DEBUGGING_SKILLS}


def _strip(value):
    return value.strip() if isinstance(value, str) else value


def validate_weights(value: dict[str, float]) -> dict[str, float]:
    """Competency-profile weights: taxonomy ids (competency areas, bug categories, skills) → 0 < w ≤ 100."""
    if not value:
        raise ValueError("Add at least one weighted competency.")
    if len(value) > 40:
        raise ValueError("A profile can weight at most 40 competencies.")
    unknown = sorted(set(value) - set(PROFILE_KEYS))
    if unknown:
        raise ValueError(f"Unknown competencies: {', '.join(unknown)}.")
    if any(not isinstance(weight, (int, float)) or not 0 < float(weight) <= 100 for weight in value.values()):
        raise ValueError("Weights must be greater than 0 and at most 100.")
    return {key: float(weight) for key, weight in value.items()}


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str | None = Field(default=None, pattern=SLUG_PATTERN)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return _strip(value)


class OrganizationUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=150)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return _strip(value)


class MemberCreate(BaseModel):
    email: EmailStr
    role: Role = "reviewer"


class MemberUpdate(BaseModel):
    role: Role


class ProfileCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str | None = Field(default=None, pattern=SLUG_PATTERN)
    description: str = Field(default="", max_length=2000)
    weights: dict[str, float]

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_text(cls, value):
        return _strip(value)

    @field_validator("weights")
    @classmethod
    def valid_weights(cls, value):
        return validate_weights(value)


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    weights: dict[str, float] | None = None

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_text(cls, value):
        return _strip(value)

    @field_validator("weights")
    @classmethod
    def valid_weights(cls, value):
        return None if value is None else validate_weights(value)


class OrganizationAssessmentCreate(AssessmentCreate):
    """Organization packs are private: members and invited candidates, or invitation only."""
    visibility: Literal["private", "invitation"] = "invitation"


class ExpirationUpdate(BaseModel):
    available_until: datetime | None = None


class InvitationUpdate(BaseModel):
    expires_at: datetime | None = None
    extend_days: int | None = Field(default=None, ge=1, le=90)

    @model_validator(mode="after")
    def one_change(self):
        if (self.expires_at is None) == (self.extend_days is None):
            raise ValueError("Provide either expires_at or extend_days.")
        return self
