"""Local execution backend implementation using subprocess."""

import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from pulsr.executors.base import (
    ArtifactConfig,
    ErrorType,
    ExecutionBackend,
    ExecutionResult,
    ExecutionStatus,
    ExecutorConfig,
    ExecutorError,
)


class LocalExecutionBackend(ExecutionBackend):
    """Execution backend that runs commands locally using subprocess."""

    def __init__(self):
        self.config = None
        self.executions = {}  # execution_id -> dict with process, status, etc.
        self.temp_dir = tempfile.mkdtemp(prefix="pulsr_local_")

    def initialize(self, config: ExecutorConfig) -> None:
        """
        Initialize the local execution backend.

        Args:
            config: Executor configuration

        Raises:
            ExecutorError: If initialization fails
        """
        self.config = config

        # Create working directory if specified and doesn't exist
        if config.working_directory:
            try:
                os.makedirs(config.working_directory, exist_ok=True)
            except OSError as e:
                raise ExecutorError(f"Failed to create working directory: {e}")

    def submit(
        self,
        step_run_id: UUID,
        command: str,
        input_artifacts: Dict[str, str] = None,
        expected_output_artifacts: List[ArtifactConfig] = None
    ) -> UUID:
        """
        Submit a command for execution in a local process.

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
        if not self.config:
            raise ExecutorError("Backend not initialized. Call initialize() first")

        execution_id = uuid4()

        # Create execution directory
        execution_dir = os.path.join(self.temp_dir, str(execution_id))
        os.makedirs(execution_dir, exist_ok=True)

        # Create output directory for artifacts
        artifacts_dir = os.path.join(execution_dir, "artifacts")
        os.makedirs(artifacts_dir, exist_ok=True)

        # Prepare environment variables
        env = os.environ.copy()
        if self.config.env_vars:
            env.update(self.config.env_vars)
        if self.config.secrets:
            env.update(self.config.secrets)

        # Set artifact-related environment variables
        env["PULSR_ARTIFACTS_DIR"] = artifacts_dir
        env["PULSR_EXECUTION_ID"] = str(execution_id)
        env["PULSR_STEP_RUN_ID"] = str(step_run_id)

        # Create links or copies of input artifacts if provided
        if input_artifacts:
            input_dir = os.path.join(execution_dir, "inputs")
            os.makedirs(input_dir, exist_ok=True)
            env["PULSR_INPUTS_DIR"] = input_dir

            for name, path in input_artifacts.items():
                target_path = os.path.join(input_dir, name)
                try:
                    # Create symlink if possible, otherwise copy the file
                    if os.path.isfile(path):
                        os.symlink(path, target_path)
                    elif os.path.isdir(path):
                        os.symlink(path, target_path, target_is_directory=True)
                except OSError:
                    import shutil
                    if os.path.isfile(path):
                        shutil.copy2(path, target_path)
                    elif os.path.isdir(path):
                        shutil.copytree(path, target_path)

        # Create expected output artifact directories
        if expected_output_artifacts:
            for artifact in expected_output_artifacts:
                artifact_dir = os.path.dirname(os.path.join(artifacts_dir, artifact.name))
                os.makedirs(artifact_dir, exist_ok=True)

        # Prepare stdout/stderr log file
        log_file = os.path.join(execution_dir, "output.log")

        try:
            # Start the process
            with open(log_file, 'w') as log_file_obj:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    cwd=self.config.working_directory or execution_dir,
                    env=env,
                    stdout=log_file_obj,
                    stderr=subprocess.STDOUT,
                    start_new_session=True  # Ensure process group for clean termination
                )
        except Exception as e:
            raise ExecutorError(f"Failed to start process: {e}")

        # Store execution information
        self.executions[execution_id] = {
            "process": process,
            "pid": process.pid,
            "status": ExecutionStatus.RUNNING,
            "step_run_id": step_run_id,
            "command": command,
            "execution_dir": execution_dir,
            "artifacts_dir": artifacts_dir,
            "log_file": log_file,
            "start_time": time.time(),
            "expected_output_artifacts": expected_output_artifacts or []
        }

        return execution_id

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
        execution = self._get_execution(execution_id)

        # Check if status is already final
        if execution["status"] in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
            return execution["status"]

        # Check process status
        process = execution["process"]
        if process.poll() is None:
            # Still running
            # Check timeout
            if self.config.timeout_seconds > 0:
                elapsed = time.time() - execution["start_time"]
                if elapsed > self.config.timeout_seconds:
                    self.cancel(execution_id)
                    execution["status"] = ExecutionStatus.FAILED
                    return ExecutionStatus.FAILED

            return ExecutionStatus.RUNNING

        # Process finished
        if process.returncode == 0:
            execution["status"] = ExecutionStatus.COMPLETED
        else:
            execution["status"] = ExecutionStatus.FAILED

        return execution["status"]

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
        execution = self._get_execution(execution_id)

        # Force status update if not already done
        status = self.get_status(execution_id)

        # Read log file
        try:
            with open(execution["log_file"], 'r') as f:
                logs = f.read()
        except Exception as e:
            logs = f"Failed to read logs: {e}"

        # Collect artifacts
        artifacts = {}
        artifacts_dir = execution["artifacts_dir"]

        if os.path.exists(artifacts_dir):
            for expected in execution["expected_output_artifacts"]:
                artifact_path = os.path.join(artifacts_dir, expected.name)
                if os.path.exists(artifact_path):
                    artifacts[expected.name] = artifact_path

        # Determine error type for failures
        error_type = None
        error_message = None

        if status == ExecutionStatus.FAILED:
            process = execution["process"]
            if process.returncode == -9:  # SIGKILL
                error_type = ErrorType.APPLICATION
                error_message = "Process was killed (timeout or resource limit exceeded)"
            elif process.returncode < 0:
                error_type = ErrorType.APPLICATION
                error_message = f"Process terminated by signal {-process.returncode}"
            else:
                # Default to application error, more sophisticated parsing would be needed
                # to determine if it's a business error
                error_type = ErrorType.APPLICATION
                error_message = f"Process failed with exit code {process.returncode}"

        return ExecutionResult(
            status=status,
            exit_code=execution["process"].returncode if execution["process"].returncode is not None else -1,
            logs=logs,
            artifacts=artifacts,
            error_type=error_type,
            error_message=error_message,
            metadata={
                "execution_time": time.time() - execution["start_time"]
            }
        )

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
        execution = self._get_execution(execution_id)

        if execution["status"] in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
            return True  # Already finished

        process = execution["process"]

        if process.poll() is None:
            # Still running, try to terminate gracefully first
            try:
                # Send SIGTERM to the process group
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)

                # Wait for a short time to see if it terminates
                for _ in range(5):
                    if process.poll() is not None:
                        break
                    time.sleep(0.5)

                # If still running, force kill
                if process.poll() is None:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except ProcessLookupError:
                # Process is already gone
                pass
            except Exception as e:
                raise ExecutorError(f"Failed to cancel execution: {e}")

        execution["status"] = ExecutionStatus.CANCELLED
        return True

    def cleanup(self, execution_id: UUID) -> None:
        """
        Cleanup resources used by an execution.

        Args:
            execution_id: ID of the execution

        Raises:
            ExecutorError: If cleanup fails
        """
        execution = self._get_execution(execution_id)

        # Make sure process is terminated
        process = execution["process"]
        if process.poll() is None:
            self.cancel(execution_id)

        # Keep artifacts but clean up temporary files
        # Do not remove the entire execution directory as it contains artifacts

        # Remove from execution tracking
        self.executions.pop(execution_id, None)

    def _get_execution(self, execution_id: UUID) -> dict:
        """Helper method to get execution information and validate it exists."""
        if execution_id not in self.executions:
            raise ExecutorError(f"Execution {execution_id} not found")
        return self.executions[execution_id]
