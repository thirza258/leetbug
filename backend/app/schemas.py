from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

Language = Literal["python", "java", "javascript", "cpp", "go"]


class Register(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=10, max_length=128)


class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ProfileUpdate(BaseModel):
    bio: str = Field(max_length=280)


class SubmissionCreate(BaseModel):
    problem_id: int
    language: Language
    mode: Literal["manual", "ai"] = "manual"
    kind: Literal["run", "submit"] = "submit"
    code: str = Field(min_length=1, max_length=50000)
    prompt: str = Field(default="", max_length=4000)


class HintCreate(BaseModel):
    language: Language = "python"


class DiscussionCreate(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    body: str = Field(min_length=10, max_length=10000)
    problem_id: int | None = None

    @field_validator("title", "body", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class ReplyCreate(BaseModel):
    body: str = Field(min_length=2, max_length=5000)

    @field_validator("body", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

