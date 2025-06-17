from datetime import datetime, UTC
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


class BaseModel(SQLModel):
    """Base model with common fields."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = Field(default=None)

    def __init__(self, **data):
        super().__init__(**data)
        self.updated_at = datetime.now(UTC)

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name != "updated_at":  # Prevent infinite recursion
            self.updated_at = datetime.now(UTC)
