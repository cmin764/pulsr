"""Base executor interface and common utilities."""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionStatus(StrEnum):
    """Status of an execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ErrorType(StrEnum):
    """Type of error encountered during execution."""
    APPLICATION = "application"  # Retryable error (e.g., network timeout)
    BUSINESS = "business"        # Non-retryable error (e.g., invalid input data)


@dataclass
class ExecutionResult:
    """Result of an execution."""
    status: ExecutionStatus
    exit_code: int
    logs: str
    artifacts: Dict[str, str]  # name -> path
    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None


class ArtifactConfig(BaseModel):
    """Configuration for an artifact."""
    name: str
    path: str  # Path where the artifact is stored
    retention_days: int = 14  # Default retention period


class ExecutorConfig(BaseModel):
    """Base configuration for executors."""
    max_retries: int = 3
    retry_delay_seconds: int = 30
    timeout_seconds: int = 3600  # 1 hour
    env_vars: Dict[str, str] = Field(default_factory=dict)
    secrets: Dict[str, str] = Field(default_factory=dict)
    working_directory: Optional[str] = None


class ExecutionBackend(ABC):
    """Abstract base class for execution backends."""

    @abstractmethod
    def initialize(self, config: ExecutorConfig) -> None:
        """
        Initialize the execution backend.

        Args:
            config: Executor configuration

        Raises:
            ExecutorError: If initialization fails
        """
        pass

    @abstractmethod
    def submit(self,
               step_run_id: UUID,
               command: str,
               input_artifacts: Dict[str, str] = None,  # name -> path
               expected_output_artifacts: List[ArtifactConfig] = None) -> UUID:
        """
        Submit a job for execution.

        Args:
            step_run_id: ID of the step run
            command: Command to execute
            input_artifacts: Dictionary of input artifacts (name -> path)
            expected_output_artifacts: List of expected output artifacts

        Returns:
            Execution ID

        Raises:
            ExecutorError: If job submission fails
        """
        pass

    @abstractmethod
    def get_status(self, execution_id: UUID) -> ExecutionStatus:
        """
        Get the status of an execution.

        Args:
            execution_id: ID of the execution

        Returns:
            Status of the execution

        Raises:
            ExecutorError: If status check fails
        """
        pass

    @abstractmethod
    def get_result(self, execution_id: UUID) -> ExecutionResult:
        """
        Get the result of an execution.

        Args:
            execution_id: ID of the execution

        Returns:
            Result of the execution

        Raises:
            ExecutorError: If result retrieval fails
        """
        pass

    @abstractmethod
    def cancel(self, execution_id: UUID) -> bool:
        """
        Cancel an execution.

        Args:
            execution_id: ID of the execution

        Returns:
            True if cancellation was successful, False otherwise

        Raises:
            ExecutorError: If cancellation fails
        """
        pass

    @abstractmethod
    def cleanup(self, execution_id: UUID) -> None:
        """
        Cleanup resources used by an execution.

        Args:
            execution_id: ID of the execution

        Raises:
            ExecutorError: If cleanup fails
        """
        pass


class ExecutorError(Exception):
    """Base exception for executor errors."""
    pass
