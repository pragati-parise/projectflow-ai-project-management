from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def name_has_text(cls, value):
        if not value.strip():
            raise ValueError("Name cannot be blank.")
        return value.strip()


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    description: str = ""
    due_date: date | None = None
    status: Literal["active", "completed"] = "active"

    @field_validator("name")
    @classmethod
    def project_name_has_text(cls, value):
        if not value.strip():
            raise ValueError("Project name cannot be blank.")
        return value.strip()


class MemberInput(BaseModel):
    email: EmailStr


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str = ""
    status: str = "todo"
    priority: str = "medium"
    due_date: date | None = None
    assigned_to: int | None = None

    @field_validator("title")
    @classmethod
    def task_title_has_text(cls, value):
        if not value.strip():
            raise ValueError("Task title cannot be blank.")
        return value.strip()


class CommentInput(BaseModel):
    content: str = Field(min_length=1, max_length=5000)

    @field_validator("content")
    @classmethod
    def comment_has_text(cls, value):
        if not value.strip():
            raise ValueError("Comment cannot be blank.")
        return value.strip()


class BreakdownInput(BaseModel):
    requirement: str = Field(min_length=5, max_length=5000)


class AssistantInput(BaseModel):
    question: str = Field(min_length=2, max_length=3000)
    project_id: int | None = None
