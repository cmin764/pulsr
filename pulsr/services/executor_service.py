"""Service for managing execution backends and workers."""

import logging
import os
import tempfile
from typing import Dict, List, Optional, Union
from uuid import UUID

from sqlmodel import Session

from pulsr.core.exceptions import ExecutionError
from pulsr.executors.base import (
    ArtifactConfig,
    ExecutionBackend,
    ExecutionResult,
    ExecutionStatus,
    ExecutorConfig,
    ErrorType,
)
from pulsr.executors.docker import DockerExecutionBackend, DockerExecutorConfig
from pulsr.executors.local import LocalExecutionBackend
from pulsr.executors.worker import WorkerAgent, WorkerConfig, WorkerStatus, WorkerCapability
from pulsr.models.step import StepRun, StepRunStatus
from pulsr.models.artifact import Artifact
from pulsr.models.pipeline import PipelineRun, PipelineRunStatus
from pulsr.services.execution_service import ExecutionService


class ExecutorService:
    """Service for managing execution backends and workers."""

    def __init__(self, session: Session):
        self.session = session
        self.execution_service = ExecutionService(session)
        self.logger = logging.getLogger(__name__)

        # Initialize backends
        self.backends: Dict[str, ExecutionBackend] = {
            "local": LocalExecutionBackend(),
            "docker": DockerExecutionBackend(),
        }

        # Initialize local worker
        local_worker_config = WorkerConfig(
            name="local-worker",
            description="Local worker for development",
            capabilities=[
                WorkerCapability(backend_type="local"),
                WorkerCapability(backend_type="docker"),
            ],
            artifact_dir=os.path.join(tempfile.gettempdir(), "pulsr_artifacts")
        )

        self.local_worker = WorkerAgent(local_worker_config)
        self.local_worker.register_backend("local", self.backends["local"])
        self.local_worker.register_backend("docker", self.backends["docker"])

        # Start local worker
        self.local_worker.start()

        # In a full implementation, we would have a registry of remote workers
        # For this MVP, we just use the local worker
        self.workers = {"local": self.local_worker}

    def execute_step(
        self,
        step_run_id: UUID,
        command: str,
        backend_type: str = "local",
        worker_id: str = "local",
        env_vars: Dict[str, str] = None,
        secrets: Dict[str, str] = None,
        input_artifacts: Dict[str, str] = None,
        expected_output_artifacts: List[ArtifactConfig] = None,
    ) -> UUID:
        """
        Execute a step using the specified backend.

        Args:
            step_run_id: ID of the step run
            command: Command to execute
            backend_type: Type of backend to use (local, docker)
            worker_id: ID of the worker to use
            env_vars: Environment variables
            secrets: Secrets
            input_artifacts: Input artifacts
            expected_output_artifacts: Expected output artifacts

        Returns:
            Execution ID

        Raises:
            ExecutionError: If execution fails
        """
        # Validate backend type
        if backend_type not in self.backends:
            raise ExecutionError(f"Unknown backend type: {backend_type}")

        # Validate worker
        if worker_id not in self.workers:
            raise ExecutionError(f"Unknown worker: {worker_id}")

        worker = self.workers[worker_id]

        # Check if worker is available
        if worker.status == WorkerStatus.OFFLINE:
            raise ExecutionError(f"Worker {worker_id} is offline")

        # Update step run status
        try:
            self.execution_service.start_step_execution(step_run_id)
        except Exception as e:
            raise ExecutionError(f"Failed to update step run status: {e}")

        # Create executor config
        if backend_type == "local":
            config = ExecutorConfig(
                env_vars=env_vars or {},
                secrets=secrets or {},
                working_directory=tempfile.mkdtemp(prefix="pulsr_step_")
            )
        elif backend_type == "docker":
            config = DockerExecutorConfig(
                base_image="python:3.9-slim",
                env_vars=env_vars or {},
                secrets=secrets or {},
                requirements_file=None,  # In a real implementation, we'd support requirements
                network_mode="bridge",
                resource_limits={"memory": "1g", "cpu": "1.0"}
            )

        try:
            # Submit execution to worker
            execution_id = worker.submit_execution(
                step_run_id=step_run_id,
                backend_type=backend_type,
                command=command,
                config=config,
                input_artifacts=input_artifacts,
                expected_output_artifacts=expected_output_artifacts
            )

            return execution_id
        except Exception as e:
            # Update step run status to failed
            self.execution_service.complete_step_execution(
                step_run_id,
                status=StepRunStatus.FAILED,
                logs=str(e)
            )
            raise ExecutionError(f"Failed to submit execution: {e}")

    def get_execution_status(self, execution_id: UUID, worker_id: str = "local") -> ExecutionStatus:
        """
        Get the status of an execution.

        Args:
            execution_id: ID of the execution
            worker_id: ID of the worker

        Returns:
            Status of the execution

        Raises:
            ExecutionError: If status check fails
        """
        if worker_id not in self.workers:
            raise ExecutionError(f"Unknown worker: {worker_id}")

        worker = self.workers[worker_id]

        try:
            status = worker.get_execution_status(execution_id)
            return status
        except Exception as e:
            raise ExecutionError(f"Failed to get execution status: {e}")

    def get_execution_result(self, execution_id: UUID, worker_id: str = "local") -> ExecutionResult:
        """
        Get the result of an execution.

        Args:
            execution_id: ID of the execution
            worker_id: ID of the worker

        Returns:
            Result of the execution

        Raises:
            ExecutionError: If result retrieval fails
        """
        if worker_id not in self.workers:
            raise ExecutionError(f"Unknown worker: {worker_id}")

        worker = self.workers[worker_id]

        try:
            result = worker.get_execution_result(execution_id)
            return result
        except Exception as e:
            raise ExecutionError(f"Failed to get execution result: {e}")

    def complete_step_execution(self, execution_id: UUID, worker_id: str = "local") -> None:
        """
        Complete step execution by collecting results and updating step run status.

        Args:
            execution_id: ID of the execution
            worker_id: ID of the worker

        Raises:
            ExecutionError: If completion fails
        """
        try:
            # Get execution result
            result = self.get_execution_result(execution_id, worker_id)

            # Get worker execution to get step_run_id
            worker = self.workers[worker_id]
            execution = worker._get_execution(execution_id)
            step_run_id = execution.step_run_id

            # Map status
            status_map = {
                ExecutionStatus.COMPLETED: StepRunStatus.COMPLETED,
                ExecutionStatus.FAILED: StepRunStatus.FAILED,
                ExecutionStatus.CANCELLED: StepRunStatus.FAILED,
            }

            step_status = status_map.get(result.status, StepRunStatus.FAILED)

            # Generate metadata
            metadata = {
                "execution_time": result.metadata.get("execution_time", 0),
                "exit_code": result.exit_code,
            }

            if result.error_type:
                metadata["error_type"] = result.error_type
                metadata["error_message"] = result.error_message

            # Update step run
            self.execution_service.complete_step_execution(
                step_run_id=step_run_id,
                status=step_status,
                logs=result.logs,
                metadata=metadata
            )

            # Register artifacts (in a full implementation)
            # for name, path in result.artifacts.items():
            #    self.register_artifact(step_run_id, name, path)

            # Cleanup execution
            worker.cleanup_execution(execution_id)

        except Exception as e:
            raise ExecutionError(f"Failed to complete step execution: {e}")

    def cancel_execution(self, execution_id: UUID, worker_id: str = "local") -> bool:
        """
        Cancel an execution.

        Args:
            execution_id: ID of the execution
            worker_id: ID of the worker

        Returns:
            True if cancellation was successful, False otherwise

        Raises:
            ExecutionError: If cancellation fails
        """
        if worker_id not in self.workers:
            raise ExecutionError(f"Unknown worker: {worker_id}")

        worker = self.workers[worker_id]

        try:
            result = worker.cancel_execution(execution_id)

            # Get step_run_id
            execution = worker._get_execution(execution_id)
            step_run_id = execution.step_run_id

            # Update step run status
            self.execution_service.complete_step_execution(
                step_run_id=step_run_id,
                status=StepRunStatus.FAILED,
                logs="Execution cancelled by user",
                metadata={"cancelled": True}
            )

            return result
        except Exception as e:
            raise ExecutionError(f"Failed to cancel execution: {e}")

    def shutdown(self) -> None:
        """Shutdown all workers."""
        for worker_id, worker in self.workers.items():
            try:
                worker.stop()
            except Exception as e:
                self.logger.error(f"Error stopping worker {worker_id}: {e}")

    def __del__(self):
        """Ensure workers are stopped on service deletion."""
        self.shutdown()
