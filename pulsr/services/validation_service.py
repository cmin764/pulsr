from uuid import UUID

from pulsr.utils.topological_sort import topological_sort, validate_dependencies
from pulsr.core.exceptions import InvalidPipelineError


class ValidationService:
    """Service for validating pipeline definitions and dependencies."""

    @staticmethod
    def validate_pipeline_dependencies(
        steps: list[dict],
        step_dependencies: list[dict[str, UUID]]
    ) -> list[UUID]:
        """
        Validate pipeline step dependencies and return execution order.

        Args:
            steps: List of step definitions
            step_dependencies: List of step dependency definitions

        Returns:
            List of step IDs in execution order

        Raises:
            InvalidPipelineError: If validation fails
        """
        if not steps:
            raise InvalidPipelineError("Pipeline must have at least one step")

        step_ids = {step["id"] for step in steps}

        # Validate that all dependencies reference valid steps
        for dep in step_dependencies:
            step_id = dep["step_id"]
            depends_on_id = dep["depends_on_step_id"]

            if step_id not in step_ids:
                raise InvalidPipelineError(f"Step dependency references unknown step: {step_id}")

            if depends_on_id not in step_ids:
                raise InvalidPipelineError(f"Step dependency references unknown step: {depends_on_id}")

        # Convert to format expected by topological sort
        dependencies = validate_dependencies(step_dependencies)

        # Perform topological sort to check for cycles and get execution order
        execution_order = topological_sort(dependencies)

        return execution_order

    @staticmethod
    def validate_step_definition(step: dict) -> None:
        """
        Validate a single step definition.

        Args:
            step: Step definition dictionary

        Raises:
            InvalidPipelineError: If step definition is invalid
        """
        required_fields = ["name", "command"]
        for field in required_fields:
            if field not in step or not step[field]:
                raise InvalidPipelineError(f"Step is missing required field: {field}")

        # Validate step name format (basic validation)
        if not isinstance(step["name"], str) or len(step["name"].strip()) == 0:
            raise InvalidPipelineError("Step name must be a non-empty string")

        # Validate command format
        if not isinstance(step["command"], str) or len(step["command"].strip()) == 0:
            raise InvalidPipelineError("Step command must be a non-empty string")
