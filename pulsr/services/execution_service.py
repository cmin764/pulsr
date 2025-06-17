from datetime import datetime, UTC
from uuid import UUID

from sqlmodel import Session, select

from pulsr.models.pipeline import PipelineRun, PipelineRunStatus
from pulsr.models.step import StepRun, StepRunStatus
from pulsr.core.exceptions import PipelineExecutionError


class ExecutionService:
    """Service for managing pipeline execution."""

    def __init__(self, session: Session):
        self.session = session

    def start_pipeline_execution(self, pipeline_run_id: UUID) -> None:
        """
        Start pipeline execution by updating status to running.

        Args:
            pipeline_run_id: Pipeline run ID

        Raises:
            PipelineExecutionError: If execution cannot be started
        """
        pipeline_run = self.session.get(PipelineRun, pipeline_run_id)
        if not pipeline_run:
            raise PipelineExecutionError("Pipeline run not found")

        if pipeline_run.status != PipelineRunStatus.PENDING:
            raise PipelineExecutionError(f"Cannot start pipeline run with status: {pipeline_run.status}")

        # Update pipeline run status
        pipeline_run.status = PipelineRunStatus.RUNNING
        pipeline_run.started_at = datetime.now(UTC)
        pipeline_run.updated_at = datetime.now(UTC)

        self.session.add(pipeline_run)
        self.session.commit()

    def complete_pipeline_execution(self, pipeline_run_id: UUID, status: PipelineRunStatus) -> None:
        """
        Complete pipeline execution with final status.

        Args:
            pipeline_run_id: Pipeline run ID
            status: Final status (completed, failed, cancelled)

        Raises:
            PipelineExecutionError: If execution cannot be completed
        """
        pipeline_run = self.session.get(PipelineRun, pipeline_run_id)
        if not pipeline_run:
            raise PipelineExecutionError("Pipeline run not found")

        if pipeline_run.status not in [PipelineRunStatus.RUNNING, PipelineRunStatus.PENDING]:
            raise PipelineExecutionError(f"Cannot complete pipeline run with status: {pipeline_run.status}")

        # Update pipeline run status
        pipeline_run.status = status
        pipeline_run.completed_at = datetime.now(UTC)
        pipeline_run.updated_at = datetime.now(UTC)

        self.session.add(pipeline_run)
        self.session.commit()

    def start_step_execution(self, step_run_id: UUID) -> None:
        """
        Start step execution by updating status to running.

        Args:
            step_run_id: Step run ID

        Raises:
            PipelineExecutionError: If step execution cannot be started
        """
        step_run = self.session.get(StepRun, step_run_id)
        if not step_run:
            raise PipelineExecutionError("Step run not found")

        if step_run.status != StepRunStatus.PENDING:
            raise PipelineExecutionError(f"Cannot start step run with status: {step_run.status}")

        # Update step run status
        step_run.status = StepRunStatus.RUNNING
        step_run.started_at = datetime.now(UTC)
        step_run.updated_at = datetime.now(UTC)

        self.session.add(step_run)
        self.session.commit()

    def complete_step_execution(
        self,
        step_run_id: UUID,
        status: StepRunStatus,
        logs: str = None,
        metadata: dict = None
    ) -> None:
        """
        Complete step execution with final status and results.

        Args:
            step_run_id: Step run ID
            status: Final status (completed, failed, skipped)
            logs: Execution logs
            metadata: Execution metadata

        Raises:
            PipelineExecutionError: If step execution cannot be completed
        """
        step_run = self.session.get(StepRun, step_run_id)
        if not step_run:
            raise PipelineExecutionError("Step run not found")

        if step_run.status not in [StepRunStatus.RUNNING, StepRunStatus.PENDING]:
            raise PipelineExecutionError(f"Cannot complete step run with status: {step_run.status}")

        # Update step run status
        step_run.status = status
        step_run.completed_at = datetime.now(UTC)
        step_run.updated_at = datetime.now(UTC)

        if logs is not None:
            step_run.logs = logs

        if metadata is not None:
            step_run.step_metadata = metadata

        self.session.add(step_run)
        self.session.commit()

    def get_step_runs_for_pipeline_run(self, pipeline_run_id: UUID) -> list[StepRun]:
        """
        Get all step runs for a pipeline run.

        Args:
            pipeline_run_id: Pipeline run ID

        Returns:
            List of StepRun instances
        """
        statement = select(StepRun).where(StepRun.pipeline_run_id == pipeline_run_id)
        step_runs = self.session.exec(statement).all()
        return list(step_runs)
