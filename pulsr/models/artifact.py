from enum import StrEnum
from uuid import UUID

from sqlmodel import SQLModel, Field, Relationship, JSON

from pulsr.models.base import BaseModel as PulsrBaseModel


class ArtifactType(StrEnum):
    """Artifact type enumeration."""
    FILE = "file"
    TEXT = "text"


class UsageType(StrEnum):
    """Artifact usage type enumeration."""
    INPUT = "input"
    OUTPUT = "output"


class Artifact(PulsrBaseModel, table=True):
    """Artifact model representing data passed between steps."""

    name: str = Field(index=True)
    artifact_type: ArtifactType
    uri: str | None = None  # For file type artifacts
    data: str | None = None  # For text type artifacts
    metadata: dict[str, any] | None = Field(default={}, sa_column_kwargs={"type_": JSON})
    created_by_step_run_id: UUID = Field(foreign_key="steprun.id")

    # Relationships
    created_by_step_run: "StepRun" = Relationship(back_populates="created_artifacts")


class ArtifactUsage(SQLModel, table=True):
    """Artifact usage model representing how step runs use artifacts."""

    step_run_id: UUID = Field(foreign_key="steprun.id", primary_key=True)
    artifact_id: UUID = Field(foreign_key="artifact.id", primary_key=True)
    usage_type: UsageType


# Import here to avoid circular imports
from pulsr.models.step import StepRun
