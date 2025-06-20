"""Docker-based execution backend implementation."""

import json
import os
import shutil
import subprocess
import tempfile
import time
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


class DockerExecutorConfig(ExecutorConfig):
    """Docker-specific configuration for executors."""
    base_image: str = "python:3.9-slim"
    dockerfile_template: Optional[str] = None
    requirements_file: Optional[str] = None
    network_mode: str = "bridge"  # bridge, host, none, or container:name|id
    resource_limits: Dict[str, str] = {}  # e.g., {"memory": "512m", "cpu": "1.0"}
    volumes: Dict[str, str] = {}  # host_path -> container_path
    image_pull_policy: str = "if-not-present"  # always, if-not-present, never
    cleanup_image: bool = False


class DockerExecutionBackend(ExecutionBackend):
    """Docker execution backend that runs commands in containers."""

    def __init__(self):
        self.config = None
        self.executions = {}
        self.temp_dir = tempfile.mkdtemp(prefix="pulsr_docker_")
        self._check_docker()

    def initialize(self, config: DockerExecutorConfig) -> None:
        """
        Initialize the Docker execution backend.

        Args:
            config: Docker executor configuration

        Raises:
            ExecutorError: If initialization fails
        """
        if not isinstance(config, DockerExecutorConfig):
            raise ExecutorError("DockerExecutionBackend requires DockerExecutorConfig")

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
        Submit a job for execution in a Docker container.

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

        # Create input directory for artifacts if needed
        input_dir = None
        if input_artifacts:
            input_dir = os.path.join(execution_dir, "inputs")
            os.makedirs(input_dir, exist_ok=True)

            # Copy input artifacts
            for name, path in input_artifacts.items():
                target_path = os.path.join(input_dir, name)
                try:
                    if os.path.isfile(path):
                        shutil.copy2(path, target_path)
                    elif os.path.isdir(path):
                        shutil.copytree(path, target_path)
                except Exception as e:
                    raise ExecutorError(f"Failed to copy input artifact '{name}': {e}")

        # Create Dockerfile
        dockerfile_path = self._create_dockerfile(execution_dir)

        # Build Docker image
        image_name = f"pulsr-exec-{execution_id}"
        self._build_docker_image(image_name, execution_dir)

        # Prepare container run command
        container_name = f"pulsr-exec-{execution_id}"
        run_cmd = ["docker", "run"]

        # Set resource limits
        if self.config.resource_limits:
            if "memory" in self.config.resource_limits:
                run_cmd.extend(["--memory", self.config.resource_limits["memory"]])
            if "cpu" in self.config.resource_limits:
                run_cmd.extend(["--cpus", self.config.resource_limits["cpu"]])

        # Set network mode
        run_cmd.extend(["--network", self.config.network_mode])

        # Set container name
        run_cmd.extend(["--name", container_name])

        # Add volumes
        # Mount artifacts directory
        run_cmd.extend(["-v", f"{artifacts_dir}:/app/artifacts"])

        # Mount input directory if exists
        if input_dir:
            run_cmd.extend(["-v", f"{input_dir}:/app/inputs"])

        # Add custom volumes
        for host_path, container_path in self.config.volumes.items():
            run_cmd.extend(["-v", f"{host_path}:{container_path}"])

        # Set environment variables
        for key, value in self.config.env_vars.items():
            run_cmd.extend(["-e", f"{key}={value}"])

        # Set secret environment variables
        for key, value in self.config.secrets.items():
            run_cmd.extend(["-e", f"{key}={value}"])

        # Set artifact and execution-related environment variables
        run_cmd.extend(["-e", f"PULSR_ARTIFACTS_DIR=/app/artifacts"])
        run_cmd.extend(["-e", f"PULSR_EXECUTION_ID={execution_id}"])
        run_cmd.extend(["-e", f"PULSR_STEP_RUN_ID={step_run_id}"])

        if input_dir:
            run_cmd.extend(["-e", f"PULSR_INPUTS_DIR=/app/inputs"])

        # Run detached (background)
        run_cmd.append("-d")

        # Add image name
        run_cmd.append(image_name)

        # Override CMD with the actual command
        if command:
            # Split command into parts for exec form
            import shlex
            run_cmd.extend(["/bin/sh", "-c", command])

        # Execute docker run command
        try:
            container_id = subprocess.check_output(run_cmd).decode('utf-8').strip()
        except subprocess.CalledProcessError as e:
            raise ExecutorError(f"Failed to start Docker container: {e.output.decode('utf-8') if e.output else str(e)}")

        # Store execution information
        self.executions[execution_id] = {
            "container_id": container_id,
            "container_name": container_name,
            "image_name": image_name,
            "status": ExecutionStatus.RUNNING,
            "step_run_id": step_run_id,
            "command": command,
            "execution_dir": execution_dir,
            "artifacts_dir": artifacts_dir,
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

        # Check container status
        try:
            container_id = execution["container_id"]
            output = subprocess.check_output(
                ["docker", "inspect", "--format={{.State.Status}}", container_id]
            ).decode('utf-8').strip()

            # Check timeout
            if self.config.timeout_seconds > 0:
                elapsed = time.time() - execution["start_time"]
                if elapsed > self.config.timeout_seconds:
                    self.cancel(execution_id)
                    execution["status"] = ExecutionStatus.FAILED
                    return ExecutionStatus.FAILED

            if output == "running":
                return ExecutionStatus.RUNNING
            elif output == "exited":
                # Get exit code
                exit_code = int(subprocess.check_output(
                    ["docker", "inspect", "--format={{.State.ExitCode}}", container_id]
                ).decode('utf-8').strip())

                if exit_code == 0:
                    execution["status"] = ExecutionStatus.COMPLETED
                else:
                    execution["status"] = ExecutionStatus.FAILED

                return execution["status"]
            else:
                execution["status"] = ExecutionStatus.FAILED
                return ExecutionStatus.FAILED

        except subprocess.CalledProcessError:
            # Container may have been removed
            execution["status"] = ExecutionStatus.FAILED
            return ExecutionStatus.FAILED

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

        # Get container logs
        try:
            logs = subprocess.check_output(
                ["docker", "logs", execution["container_id"]]
            ).decode('utf-8')
        except subprocess.CalledProcessError:
            logs = "Failed to retrieve Docker logs"

        # Get exit code
        exit_code = -1
        try:
            exit_code = int(subprocess.check_output(
                ["docker", "inspect", "--format={{.State.ExitCode}}", execution["container_id"]]
            ).decode('utf-8').strip())
        except subprocess.CalledProcessError:
            pass

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
            # Default to application error
            error_type = ErrorType.APPLICATION
            error_message = f"Container failed with exit code {exit_code}"

            # Try to detect business errors from logs or other indicators
            # This is a simple heuristic that could be improved
            if "BUSINESS_ERROR" in logs:
                error_type = ErrorType.BUSINESS

        return ExecutionResult(
            status=status,
            exit_code=exit_code,
            logs=logs,
            artifacts=artifacts,
            error_type=error_type,
            error_message=error_message,
            metadata={
                "execution_time": time.time() - execution["start_time"],
                "container_id": execution["container_id"],
                "image_name": execution["image_name"]
            }
        )

    def cancel(self, execution_id: UUID) -> bool:
        """
        Cancel an execution by stopping the Docker container.

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

        try:
            # Stop the container (with a 10-second timeout)
            subprocess.check_call(["docker", "stop", "--time=10", execution["container_id"]])
            execution["status"] = ExecutionStatus.CANCELLED
            return True
        except subprocess.CalledProcessError as e:
            raise ExecutorError(f"Failed to cancel Docker container: {e}")

    def cleanup(self, execution_id: UUID) -> None:
        """
        Cleanup resources used by an execution.

        Args:
            execution_id: ID of the execution

        Raises:
            ExecutorError: If cleanup fails
        """
        execution = self._get_execution(execution_id)

        try:
            # Remove the container
            container_id = execution["container_id"]
            subprocess.call(["docker", "rm", "-f", container_id], stderr=subprocess.DEVNULL)

            # Optionally remove the image
            if self.config.cleanup_image:
                image_name = execution["image_name"]
                subprocess.call(["docker", "rmi", "-f", image_name], stderr=subprocess.DEVNULL)

            # Remove from execution tracking
            self.executions.pop(execution_id, None)
        except Exception as e:
            raise ExecutorError(f"Failed to clean up Docker execution: {e}")

    def _check_docker(self) -> None:
        """Check if Docker is installed and running."""
        try:
            # Check if docker command is available
            subprocess.check_output(["docker", "--version"])

            # Check if docker daemon is running
            subprocess.check_output(["docker", "info"])
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise ExecutorError(f"Docker is not available: {e}")

    def _create_dockerfile(self, execution_dir: str) -> str:
        """Create Dockerfile for executing the step."""
        dockerfile_path = os.path.join(execution_dir, "Dockerfile")

        if self.config.dockerfile_template:
            # Use provided template
            with open(dockerfile_path, 'w') as f:
                f.write(self.config.dockerfile_template)
        else:
            # Create default Dockerfile
            with open(dockerfile_path, 'w') as f:
                f.write(f"FROM {self.config.base_image}\n")
                f.write("\n")
                f.write("WORKDIR /app\n\n")

                # Add requirements file if provided
                if self.config.requirements_file and os.path.exists(self.config.requirements_file):
                    # Copy requirements file to execution directory
                    shutil.copy2(self.config.requirements_file, os.path.join(execution_dir, "requirements.txt"))
                    f.write("COPY requirements.txt /app/\n")
                    f.write("RUN pip install --no-cache-dir -r requirements.txt\n\n")

                # Create artifact directories
                f.write("RUN mkdir -p /app/artifacts\n")

                # Set environment variables
                f.write("ENV PYTHONUNBUFFERED=1\n")

                # Set default command
                f.write('CMD ["/bin/sh", "-c", "echo Container started && tail -f /dev/null"]\n')

        return dockerfile_path

    def _build_docker_image(self, image_name: str, context_dir: str) -> None:
        """Build Docker image from Dockerfile."""
        try:
            build_cmd = ["docker", "build", "-t", image_name, context_dir]

            # Execute build command
            subprocess.check_output(build_cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise ExecutorError(f"Failed to build Docker image: {e.output.decode('utf-8') if e.output else str(e)}")

    def _get_execution(self, execution_id: UUID) -> dict:
        """Helper method to get execution information and validate it exists."""
        if execution_id not in self.executions:
            raise ExecutorError(f"Execution {execution_id} not found")
        return self.executions[execution_id]
