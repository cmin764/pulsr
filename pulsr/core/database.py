from sqlmodel import SQLModel, create_engine, Session
from pulsr.core.config import settings

# Create engine with SQLite
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=settings.debug,  # Log SQL queries in debug mode
)


def create_db_and_tables():
    """Create database tables on application startup."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Dependency to get database session."""
    with Session(engine) as session:
        yield session
