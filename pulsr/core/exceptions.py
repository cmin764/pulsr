from fastapi import HTTPException


class PulsrException(Exception):
    """Base exception for Pulsr application."""

    def __init__(self, message: str, details: dict[str, any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class PulsrHTTPException(HTTPException):
    """Base HTTP exception for Pulsr API."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class PipelineNotFoundError(PulsrHTTPException):
    """Raised when a pipeline is not found."""

    def __init__(self, pipeline_id: str):
        super().__init__(
            status_code=404,
            detail=f"Pipeline with id '{pipeline_id}' not found"
        )


class PipelineRunNotFoundError(PulsrHTTPException):
    """Raised when a pipeline run is not found."""

    def __init__(self, run_id: str):
        super().__init__(
            status_code=404,
            detail=f"Pipeline run with id '{run_id}' not found"
        )


class InvalidPipelineError(PulsrHTTPException):
    """Raised when pipeline definition is invalid."""

    def __init__(self, message: str):
        super().__init__(
            status_code=400,
            detail=f"Invalid pipeline definition: {message}"
        )


class PipelineExecutionError(PulsrHTTPException):
    """Raised when pipeline execution fails."""

    def __init__(self, message: str):
        super().__init__(
            status_code=500,
            detail=f"Pipeline execution error: {message}"
        )
