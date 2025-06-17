from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlmodel import SQLModel, Field, Relationship, JSON
from pydantic import BaseModel

from pulsr.models.base import BaseModel as PulsrBaseModel


class StepRunStatus(StrEnum):
    """Step run status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Step(PulsrBaseModel, table=True):
    """Step model representing an atomic unit of work."""

    pipeline_id: UUID = Field(foreign_key="pipeline.id")
    name: str = Field(index=True)
    description: str | None = None
    command: str  # Bash command or script path

    # Relationships
    pipeline: "Pipeline" = Relationship(back_populates="steps")
    step_runs: list["StepRun"] = Relationship(
        back_populates="step",
        cascade_delete=True
    )

    # Dependencies handled through StepDependency table


class StepRun(PulsrBaseModel, table=True):
    """Step run model representing a step execution instance."""

    step_id: UUID = Field(foreign_key="step.id")
    pipeline_run_id: UUID = Field(foreign_key="pipelinerun.id")
    status: StepRunStatus = Field(default=StepRunStatus.PENDING)
    logs: str | None = None  # stdout/stderr
    metadata: dict[str, any] | None = Field(default={}, sa_column_kwargs={"type_": JSON})
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Relationships
    step: Step = Relationship(back_populates="step_runs")
    pipeline_run: "PipelineRun" = Relationship(back_populates="step_runs")
    created_artifacts: list["Artifact"] = Relationship(
        back_populates="created_by_step_run",
        cascade_delete=True
    )


class StepDependency(SQLModel, table=True):
    """Step dependency model representing step relationships."""

    step_id: UUID = Field(foreign_key="step.id", primary_key=True)
    depends_on_step_id: UUID = Field(foreign_key="step.id", primary_key=True)


# Schema models for API
class StepCreate(BaseModel):
    """Schema for creating a step."""
    name: str
    description: str | None = None
    command: str


class StepDependencyCreate(BaseModel):
    """Schema for creating a step dependency."""
    step_id: UUID
    depends_on_step_id: UUID


# Import here to avoid circular imports
from pulsr.models.pipeline import Pipeline, PipelineRun
from pulsr.models.artifact import Artifact
