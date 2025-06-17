from datetime import datetime, UTC
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, func


class BaseModel(SQLModel):
    """Base model with common fields."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # TODO: better to move these into a mixin
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # updated_at: datetime = Field(
    #     sa_column=Column(
    #         DateTime(timezone=True),
    #         server_default=func.current_timestamp(),
    #         server_onupdate=func.current_timestamp(),
    #     )
    # )
