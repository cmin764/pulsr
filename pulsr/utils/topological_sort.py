from uuid import UUID

from pulsr.core.exceptions import InvalidPipelineError


def topological_sort(dependencies: dict[UUID, list[UUID]]) -> list[UUID]:
    """
    Perform topological sort on step dependencies.

    Args:
        dependencies: Dict mapping step_id to list of step_ids it depends on

    Returns:
        List of step_ids in execution order

    Raises:
        InvalidPipelineError: If circular dependencies are detected
    """
    # Create a copy to avoid modifying the original
    deps = {k: set(v) for k, v in dependencies.items()}
    result = []

    # Get all nodes (steps)
    all_nodes = set(deps.keys())
    for dep_list in deps.values():
        all_nodes.update(dep_list)

    # Add nodes with no dependencies if they're not in the dict
    for node in all_nodes:
        if node not in deps:
            deps[node] = set()

    # Kahn's algorithm
    in_degree = {node: 0 for node in all_nodes}
    for node in deps:
        for dependency in deps[node]:
            in_degree[node] += 1

    # Find nodes with no incoming edges
    queue = [node for node in all_nodes if in_degree[node] == 0]

    while queue:
        current = queue.pop(0)
        result.append(current)

        # Remove edges from current node
        for node in deps:
            if current in deps[node]:
                deps[node].remove(current)
                in_degree[node] -= 1
                if in_degree[node] == 0:
                    queue.append(node)

    # Check for cycles
    if len(result) != len(all_nodes):
        raise InvalidPipelineError("Circular dependency detected in pipeline steps")

    return result


def validate_dependencies(step_dependencies: list[dict[str, UUID]]) -> dict[UUID, list[UUID]]:
    """
    Validate and convert step dependencies to a format suitable for topological sort.

    Args:
        step_dependencies: List of dicts with 'step_id' and 'depends_on_step_id'

    Returns:
        Dict mapping step_id to list of dependencies

    Raises:
        InvalidPipelineError: If dependencies are invalid
    """
    dependencies = {}

    for dep in step_dependencies:
        step_id = dep["step_id"]
        depends_on_id = dep["depends_on_step_id"]

        # Check for self-dependency
        if step_id == depends_on_id:
            raise InvalidPipelineError(f"Step {step_id} cannot depend on itself")

        if step_id not in dependencies:
            dependencies[step_id] = []
        dependencies[step_id].append(depends_on_id)

    return dependencies
