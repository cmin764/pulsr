from datetime import datetime, UTC
from typing import Any
from uuid import UUID, uuid4

from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from pulsr.models.pipeline import Pipeline, PipelineRun, PipelineRunStatus
from pulsr.models.step import CreateStep, CreateStepDependency, Step, StepRun, StepRunStatus, StepDependency
from pulsr.core.exceptions import PipelineNotFoundError, PipelineRunNotFoundError
from pulsr.services.validation_service import ValidationService


class PipelineService:
    """Service for managing pipelines and their operations."""

    def __init__(self, session: Session):
        self.session = session
        self.validation_service = ValidationService()

    def create_pipeline(
        self,
        name: str,
        description: str | None,
        steps: list[CreateStep],
        step_dependencies: list[CreateStepDependency] | None = None
    ) -> Pipeline:
        """
        Create a new pipeline with steps and dependencies.

        Args:
            name: Pipeline name
            description: Pipeline description
            steps: List of step definitions
            step_dependencies: List of step dependency definitions

        Returns:
            Created Pipeline instance

        Raises:
            InvalidPipelineError: If pipeline definition is invalid
        """
        if step_dependencies is None:
            step_dependencies = []

        # Validate dependencies and get execution order
        steps_dict = {}
        for step in steps:
            steps_dict[step.name] = {"id": uuid4(), **step.model_dump()}
        steps = list(steps_dict.values())
        step_dependencies = [
            {
                "step_id": steps_dict[dep.step_name]["id"],
                "depends_on_step_id": steps_dict[dep.depends_on_step_name]["id"],
                **dep.model_dump()
            }
            for dep in step_dependencies
        ]
        execution_order = self.validation_service.validate_pipeline_dependencies(
            steps, step_dependencies
        )

        # Create pipeline
        pipeline = Pipeline(
            name=name,
            description=description,
        )
        self.session.add(pipeline)
        self.session.flush()  # to get the pipeline ID

        # Create steps
        step_objects = {}
        for step_def in steps:
            step = Step(
                id=step_def["id"],
                pipeline_id=pipeline.id,
                name=step_def["name"],
                description=step_def.get("description"),
                command=step_def["command"]
            )
            self.session.add(step)
            self.session.flush()
            step_objects[step.name] = step.id

        # Create step dependencies
        for dep in step_dependencies:
            dependency = StepDependency(
                step_id=step_objects[dep["step_name"]],
                depends_on_step_id=step_objects[dep["depends_on_step_name"]]
            )
            self.session.add(dependency)

        self.session.commit()
        self.session.refresh(pipeline)
        return pipeline

    def get_pipeline(self, pipeline_id: UUID) -> Pipeline:
        """
        Get pipeline by ID with steps.

        Args:
            pipeline_id: Pipeline ID

        Returns:
            Pipeline instance with loaded steps

        Raises:
            PipelineNotFoundError: If pipeline not found
        """
        statement = select(Pipeline).options(selectinload(Pipeline.steps)).where(Pipeline.id == pipeline_id)
        pipeline = self.session.exec(statement).first()
        if not pipeline:
            raise PipelineNotFoundError(str(pipeline_id))
        return pipeline

    def list_pipelines(self, skip: int = 0, limit: int = 100) -> list[Pipeline]:
        """
        List all pipelines.

        Args:
            skip: Number of pipelines to skip
            limit: Maximum number of pipelines to return

        Returns:
            List of Pipeline instances
        """
        statement = select(Pipeline).offset(skip).limit(limit)
        pipelines = self.session.exec(statement).all()
        return list(pipelines)

    def trigger_pipeline_run(self, pipeline_id: UUID) -> PipelineRun:
        """
        Trigger a new pipeline run.

        Args:
            pipeline_id: Pipeline ID

        Returns:
            Created PipelineRun instance

        Raises:
            PipelineNotFoundError: If pipeline not found
        """
        # Verify pipeline exists
        pipeline = self.get_pipeline(pipeline_id)

        # Create pipeline run
        pipeline_run = PipelineRun(
            pipeline_id=pipeline_id,
            status=PipelineRunStatus.PENDING
        )
        self.session.add(pipeline_run)
        self.session.flush()  # Get the run ID

        # Create step runs for all steps in the pipeline
        for step in pipeline.steps:
            step_run = StepRun(
                step_id=step.id,
                pipeline_run_id=pipeline_run.id,
                status=StepRunStatus.PENDING
            )
            self.session.add(step_run)

        self.session.commit()
        self.session.refresh(pipeline_run)
        return pipeline_run

    def get_pipeline_run(self, pipeline_id: UUID, run_id: UUID) -> PipelineRun:
        """
        Get pipeline run by ID with step runs.

        Args:
            pipeline_id: Pipeline ID
            run_id: Run ID

        Returns:
            PipelineRun instance with loaded step runs

        Raises:
            PipelineNotFoundError: If pipeline not found
            PipelineRunNotFoundError: If run not found
        """
        # Verify pipeline exists
        self.get_pipeline(pipeline_id)

        # Get run with step runs loaded
        statement = select(PipelineRun).options(selectinload(PipelineRun.step_runs)).where(
            PipelineRun.id == run_id,
            PipelineRun.pipeline_id == pipeline_id
        )
        pipeline_run = self.session.exec(statement).first()

        if not pipeline_run:
            raise PipelineRunNotFoundError(str(run_id))

        return pipeline_run

    def list_pipeline_runs(
        self,
        pipeline_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> list[PipelineRun]:
        """
        List all runs for a pipeline.

        Args:
            pipeline_id: Pipeline ID
            skip: Number of runs to skip
            limit: Maximum number of runs to return

        Returns:
            List of PipelineRun instances

        Raises:
            PipelineNotFoundError: If pipeline not found
        """
        # Verify pipeline exists
        self.get_pipeline(pipeline_id)

        statement = select(PipelineRun).where(
            PipelineRun.pipeline_id == pipeline_id
        ).offset(skip).limit(limit).order_by(PipelineRun.created_at.desc())

        runs = self.session.exec(statement).all()
        return list(runs)
