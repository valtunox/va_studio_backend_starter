from datetime import datetime
from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class ProjectCreate(ProjectBase):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "My Project",
                    "description": "A sample project description.",
                }
            ]
        }
    }


class ProjectUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class ProjectResponse(ProjectBase):
    id: int
    is_active: bool
    owner_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
