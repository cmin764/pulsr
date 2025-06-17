from enum import StrEnum
from typing import Any
from uuid import UUID
from datetime import datetime

from sqlmodel import SQLModel, Field, Relationship, JSON
from pydantic import BaseModel

from pulsr.models.base import BaseModel as PulsrBaseModel


class ArtifactType(StrEnum):
    """Artifact type enumeration."""
    FILE = "file"
    TEXT = "text"


class UsageType(StrEnum):
    """Artifact usage type enumeration."""
    INPUT = "input"
    OUTPUT = "output"


# Base classes with core fields - inherit from SQLModel (no table creation)
class BaseArtifact(SQLModel):
    """Base artifact model with core fields."""
    name: str = Field(index=True)
    artifact_type: ArtifactType
    uri: str | None = None  # For file type artifacts
    data: str | None = None  # For text type artifacts
    artifact_metadata: dict[str, Any] | None = Field(default={}, sa_type=JSON, alias="metadata")
    created_by_step_run_id: UUID = Field(foreign_key="steprun.id")


class BaseArtifactUsage(SQLModel):
    """Base artifact usage model with core fields."""
    step_run_id: UUID = Field(foreign_key="steprun.id", primary_key=True)
    artifact_id: UUID = Field(foreign_key="artifact.id", primary_key=True)
    usage_type: UsageType


# Table models - only these inherit from SQLModel with table=True
class Artifact(BaseArtifact, PulsrBaseModel, table=True):
    """Artifact table model representing data passed between steps."""

    # Relationships
    created_by_step_run: "StepRun" = Relationship(back_populates="created_artifacts")


class ArtifactUsage(BaseArtifactUsage, PulsrBaseModel, table=True):
    """Artifact usage table model representing how step runs use artifacts."""
    pass


# API schema models - inherit from base classes (no table creation)
class CreateArtifact(BaseModel):
    """Schema for creating an artifact."""
    name: str
    artifact_type: ArtifactType
    uri: str | None = None
    data: str | None = None
    metadata: dict[str, Any] | None = None


class RetrieveArtifact(BaseArtifact):
    """Schema for retrieving an artifact."""
    id: UUID
    created_at: datetime
    # updated_at: datetime | None


class CreateArtifactUsage(BaseModel):
    """Schema for creating an artifact usage."""
    step_run_id: UUID
    artifact_id: UUID
    usage_type: UsageType


class RetrieveArtifactUsage(BaseArtifactUsage):
    """Schema for retrieving an artifact usage."""
    id: UUID
    created_at: datetime
    # updated_at: datetime | None
