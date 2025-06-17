import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session

from pulsr.main import app
from pulsr.core.database import get_session
from pulsr.models import *


@pytest.fixture(name="session")
def session_fixture():
    """Create a test database session."""
    engine = create_engine(
        "sqlite:///./test_pulsr.db",
        connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    # Clean up
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Create a test client with dependency overrides."""
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
