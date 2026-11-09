"""Request bodies for assessment endpoints (PRD 9.3)."""
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.schemas import Language
from app.scoring import ASSESSMENT_WEIGHTS

AssessmentType = Literal["individual", "interview", "specialized", "practice"]
Visibility = Literal["public", "private", "invitation"]
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")


class AssistancePolicy(BaseModel):
    ai: Literal["disabled", "guided", "enabled"] = "disabled"
    hints: Literal["disabled", "restricted", "enabled"] = "disabled"


class AssessmentConfiguration(BaseModel):
    problems: list[str] = Field(min_length=1, max_length=20)
    languages: list[Language] = Field(default_factory=list, max_length=5)
    diagnosis_required: bool = True
    explanation_required: bool = False
    max_attempts: int | None = Field(default=None, ge=1, le=50)
    max_sessions: int | None = Field(default=None, ge=1, le=50)
    randomize_order: bool = False
    feedback: Literal["immediate", "delayed"] = "immediate"
    candidate_report: Literal["full", "summary"] = "full"
    require_quality_approved: bool = False

    @field_validator("problems")
    @classmethod
    def unique_problem_slugs(cls, value: list[str]) -> list[str]:
        slugs = [item.strip().lower() for item in value]
        if any(not SLUG.match(slug) for slug in slugs):
            raise ValueError("Problem slugs use lowercase letters, digits and hyphens.")
        if len(set(slugs)) != len(slugs):
            raise ValueError("Each challenge can appear only once.")
        return slugs

    @field_validator("languages")
    @classmethod
    def unique_languages(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class ScoringRubric(BaseModel):
    weights: dict[str, float] = Field(default_factory=lambda: dict(ASSESSMENT_WEIGHTS))

    @field_validator("weights")
    @classmethod
    def valid_weights(cls, value: dict[str, float]) -> dict[str, float]:
        unknown = set(value) - set(ASSESSMENT_WEIGHTS)
        if unknown:
            raise ValueError(f"Unknown scoring dimensions: {', '.join(sorted(unknown))}.")
        if any(weight < 0 or weight > 100 for weight in value.values()):
            raise ValueError("Weights must be between 0 and 100.")
        if sum(value.values()) <= 0:
            raise ValueError("At least one scoring dimension needs a positive weight.")
        return {key: float(weight) for key, weight in value.items()}


class AssessmentCreate(BaseModel):
    title: str = Field(min_length=5, max_length=150)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{2,99}$")
    description: str = Field(default="", max_length=5000)
    assessment_type: AssessmentType = "individual"
    duration_seconds: int = Field(default=3600, ge=300, le=4 * 3600)
    configuration: AssessmentConfiguration
    scoring_rubric: ScoringRubric = Field(default_factory=ScoringRubric)
    assistance_policy: AssistancePolicy = Field(default_factory=AssistancePolicy)
    visibility: Visibility = "public"
    organization_id: str | None = Field(default=None, max_length=36)
    competency_profile_id: str | None = Field(default=None, max_length=36)
    available_from: datetime | None = None
    available_until: datetime | None = None

    @field_validator("title", "description", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def window_order(self):
        if self.available_from and self.available_until and self.available_until <= self.available_from:
            raise ValueError("The availability window must end after it starts.")
        return self


class AssessmentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=150)
    description: str | None = Field(default=None, max_length=5000)
    assessment_type: AssessmentType | None = None
    duration_seconds: int | None = Field(default=None, ge=300, le=4 * 3600)
    configuration: AssessmentConfiguration | None = None
    scoring_rubric: ScoringRubric | None = None
    assistance_policy: AssistancePolicy | None = None
    visibility: Visibility | None = None
    competency_profile_id: str | None = Field(default=None, max_length=36)
    available_from: datetime | None = None
    available_until: datetime | None = None

    @field_validator("title", "description", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class InvitationCreate(BaseModel):
    emails: list[EmailStr] = Field(min_length=1, max_length=100)
    expires_in_days: int = Field(default=14, ge=1, le=90)


class InvitationAccept(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class CorrectionCreate(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)
    # {problem slug or id: {dimension: 0-100}}
    challenge_scores: dict[str, dict[str, float]] = Field(default_factory=dict, max_length=20)
    total_score: float | None = Field(default=None, ge=0, le=100)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_reason(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("challenge_scores")
    @classmethod
    def valid_components(cls, value: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
        for components in value.values():
            unknown = set(components) - set(ASSESSMENT_WEIGHTS)
            if unknown:
                raise ValueError(f"Unknown scoring dimensions: {', '.join(sorted(unknown))}.")
            if any(score < 0 or score > 100 for score in components.values()):
                raise ValueError("Corrected scores must be between 0 and 100.")
        return value

    @model_validator(mode="after")
    def has_adjustment(self):
        if not self.challenge_scores and self.total_score is None:
            raise ValueError("Provide at least one score adjustment.")
        return self
