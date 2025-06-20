"""Worker agent for managing execution backends."""

import logging
import os
import platform
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Dict, List, Optional, Tuple, Union, Any

from pydantic import BaseModel, Field

from pulsr.executors.base import (
    ArtifactConfig,
    ErrorType,
    ExecutionBackend,
    ExecutionResult,
    ExecutionStatus,
    ExecutorConfig,
    ExecutorError
)


class WorkerStatus(StrEnum):
    """Status of a worker."""
    OFFLINE = "offline"
    ONLINE = "online"
    BUSY = "busy"
    MAINTENANCE = "maintenance"


class WorkerCapability(BaseModel):
    """Capability of a worker."""
    backend_type: str  # "local", "docker", etc.
    properties: Dict[str, Any] = Field(default_factory=dict)


class WorkerConfig(BaseModel):
    """Configuration for a worker agent."""
    worker_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    capabilities: List[WorkerCapability] = Field(default_factory=list)
    max_concurrent_executions: int = 5
    heartbeat_interval_seconds: int = 60
    artifact_dir: Optional[str] = None

    # Platform info is collected automatically if not provided
    platform_info: Dict[str, str] = Field(default_factory=dict)


@dataclass
class WorkerExecution:
    """Information about an execution managed by a worker."""
    execution_id: uuid.UUID
    step_run_id: uuid.UUID
    backend_type: str
    backend_execution_id: uuid.UUID
    start_time: float
    status: ExecutionStatus = ExecutionStatus.PENDING


class WorkerAgent:
    """Agent that manages execution backends and communicates with the central service."""

    def __init__(self, config: WorkerConfig):
        self.config = config

        # Initialize platform info if not provided
        if not config.platform_info:
            self.config.platform_info = {
                "system": platform.system(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python": platform.python_version(),
                "hostname": platform.node()
            }

        # Create artifact directory if needed
        if not config.artifact_dir:
            self.config.artifact_dir = os.path.join(tempfile.gettempdir(), f"pulsr_worker_{config.worker_id}")

        os.makedirs(self.config.artifact_dir, exist_ok=True)

        self.status = WorkerStatus.OFFLINE
        self.backends: Dict[str, ExecutionBackend] = {}
        self.executions: Dict[uuid.UUID, WorkerExecution] = {}

        self.heartbeat_thread = None
        self.status_check_thread = None
        self.shutdown_event = threading.Event()

        self.logger = logging.getLogger(__name__)

    def register_backend(self, backend_type: str, backend: ExecutionBackend) -> None:
        """
        Register an execution backend with the worker.

        Args:
            backend_type: Type of backend (e.g., "local", "docker")
            backend: Backend instance
        """
        self.backends[backend_type] = backend

        # Add capability if not already present
        capability_exists = False
        for capability in self.config.capabilities:
            if capability.backend_type == backend_type:
                capability_exists = True
                break

        if not capability_exists:
            self.config.capabilities.append(WorkerCapability(backend_type=backend_type))

        self.logger.info(f"Registered backend of type '{backend_type}'")

    def start(self) -> None:
        """Start the worker agent."""
        if self.status != WorkerStatus.OFFLINE:
            return

        # Start heartbeat thread
        self.shutdown_event.clear()
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

        # Start execution status check thread
        self.status_check_thread = threading.Thread(target=self._status_check_loop, daemon=True)
        self.status_check_thread.start()

        self.status = WorkerStatus.ONLINE
        self.logger.info(f"Worker '{self.config.name}' (ID: {self.config.worker_id}) started")

    def stop(self) -> None:
        """Stop the worker agent."""
        if self.status == WorkerStatus.OFFLINE:
            return

        self.shutdown_event.set()

        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=2)

        if self.status_check_thread:
            self.status_check_thread.join(timeout=2)

        # Cancel all running executions
        for execution_id in list(self.executions.keys()):
            self.cancel_execution(execution_id)

        self.status = WorkerStatus.OFFLINE
        self.logger.info(f"Worker '{self.config.name}' stopped")

    def submit_execution(
        self,
        step_run_id: uuid.UUID,
        backend_type: str,
        command: str,
        config: ExecutorConfig,
        input_artifacts: Dict[str, str] = None,
        expected_output_artifacts: List[ArtifactConfig] = None
    ) -> uuid.UUID:
        """
        Submit an execution to the appropriate backend.

        Args:
            step_run_id: ID of the step run
            backend_type: Type of backend to use (e.g., "local", "docker")
            command: Command to execute
            config: Executor configuration
            input_artifacts: Dictionary of input artifacts (name -> path)
            expected_output_artifacts: List of expected output artifacts

        Returns:
            Execution ID

        Raises:
            ExecutorError: If submission fails
        """
        # Check if worker has capacity for more executions
        if len(self.executions) >= self.config.max_concurrent_executions:
            raise ExecutorError("Worker has reached maximum concurrent executions")

        # Check if backend exists
        if backend_type not in self.backends:
            raise ExecutorError(f"Backend of type '{backend_type}' is not registered")

        # Update worker status
        self.status = WorkerStatus.BUSY

        # Initialize backend if needed
        backend = self.backends[backend_type]
        try:
            backend.initialize(config)

            # Submit execution
            backend_execution_id = backend.submit(
                step_run_id=step_run_id,
                command=command,
                input_artifacts=input_artifacts,
                expected_output_artifacts=expected_output_artifacts
            )

            execution_id = uuid.uuid4()

            # Store execution information
            self.executions[execution_id] = WorkerExecution(
                execution_id=execution_id,
                step_run_id=step_run_id,
                backend_type=backend_type,
                backend_execution_id=backend_execution_id,
                start_time=time.time(),
                status=ExecutionStatus.RUNNING
            )

            self.logger.info(f"Submitted execution {execution_id} to {backend_type} backend")

            return execution_id
        except Exception as e:
            # Update worker status if no more executions
            if len(self.executions) == 0:
                self.status = WorkerStatus.ONLINE
            raise ExecutorError(f"Failed to submit execution: {e}")

    def get_execution_status(self, execution_id: uuid.UUID) -> ExecutionStatus:
        """
        Get the status of an execution.

        Args:
            execution_id: ID of the execution

        Returns:
            Status of the execution

        Raises:
            ExecutorError: If status check fails
        """
        execution = self._get_execution(execution_id)

        try:
            backend = self.backends[execution.backend_type]
            status = backend.get_status(execution.backend_execution_id)

            # Update stored status
            execution.status = status

            return status
        except Exception as e:
            raise ExecutorError(f"Failed to get execution status: {e}")

    def get_execution_result(self, execution_id: uuid.UUID) -> ExecutionResult:
        """
        Get the result of an execution.

        Args:
            execution_id: ID of the execution

        Returns:
            Result of the execution

        Raises:
            ExecutorError: If result retrieval fails
        """
        execution = self._get_execution(execution_id)

        try:
            backend = self.backends[execution.backend_type]
            result = backend.get_result(execution.backend_execution_id)

            # Update stored status
            execution.status = result.status

            return result
        except Exception as e:
            raise ExecutorError(f"Failed to get execution result: {e}")

    def cancel_execution(self, execution_id: uuid.UUID) -> bool:
        """
        Cancel an execution.

        Args:
            execution_id: ID of the execution

        Returns:
            True if cancellation was successful, False otherwise

        Raises:
            ExecutorError: If cancellation fails
        """
        execution = self._get_execution(execution_id)

        try:
            backend = self.backends[execution.backend_type]
            result = backend.cancel(execution.backend_execution_id)

            # Update stored status
            execution.status = ExecutionStatus.CANCELLED

            return result
        except Exception as e:
            raise ExecutorError(f"Failed to cancel execution: {e}")

    def cleanup_execution(self, execution_id: uuid.UUID) -> None:
        """
        Cleanup resources used by an execution.

        Args:
            execution_id: ID of the execution

        Raises:
            ExecutorError: If cleanup fails
        """
        execution = self._get_execution(execution_id)

        try:
            backend = self.backends[execution.backend_type]
            backend.cleanup(execution.backend_execution_id)

            # Remove from tracked executions
            del self.executions[execution_id]

            # Update worker status if no more executions
            if len(self.executions) == 0:
                self.status = WorkerStatus.ONLINE

        except Exception as e:
            raise ExecutorError(f"Failed to clean up execution: {e}")

    def _heartbeat_loop(self) -> None:
        """Background thread for sending heartbeats to the central service."""
        while not self.shutdown_event.is_set():
            try:
                self._send_heartbeat()
            except Exception as e:
                self.logger.error(f"Error sending heartbeat: {e}")

            # Sleep for heartbeat interval
            self.shutdown_event.wait(self.config.heartbeat_interval_seconds)

    def _status_check_loop(self) -> None:
        """Background thread for checking the status of running executions."""
        while not self.shutdown_event.is_set():
            try:
                self._check_executions_status()
            except Exception as e:
                self.logger.error(f"Error checking executions status: {e}")

            # Sleep for a short interval (5 seconds)
            self.shutdown_event.wait(5)

    def _send_heartbeat(self) -> None:
        """Send heartbeat to the central service."""
        # In a real implementation, this would make an API call to the central service
        # For this MVP, we just log the heartbeat
        self.logger.debug(f"Worker '{self.config.name}' heartbeat: {self.status.value}")

    def _check_executions_status(self) -> None:
        """Check the status of all running executions."""
        for execution_id, execution in list(self.executions.items()):
            if execution.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
                continue  # Skip already completed executions

            try:
                # Get current status from backend
                backend = self.backends[execution.backend_type]
                status = backend.get_status(execution.backend_execution_id)

                # Update stored status if changed
                if status != execution.status:
                    execution.status = status

                    # In a real implementation, report status change to central service
                    self.logger.info(f"Execution {execution_id} status changed to {status.value}")

            except Exception as e:
                self.logger.error(f"Error checking execution {execution_id} status: {e}")

    def _get_execution(self, execution_id: uuid.UUID) -> WorkerExecution:
        """Helper method to get execution information and validate it exists."""
        if execution_id not in self.executions:
            raise ExecutorError(f"Execution {execution_id} not found")
        return self.executions[execution_id]
