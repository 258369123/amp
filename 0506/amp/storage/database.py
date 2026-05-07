"""Database connection and session management."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from amp.storage.schema import Base


class Database:
    """Database connection manager."""

    def __init__(self, database_url: str = "sqlite:///amp.db", echo: bool = False):
        """Initialize database connection.

        Args:
            database_url: SQLAlchemy database URL
            echo: Enable SQL query logging
        """
        # Use StaticPool for SQLite to avoid threading issues
        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
            self.engine = create_engine(
                database_url,
                echo=echo,
                connect_args=connect_args,
                poolclass=StaticPool,
            )
        else:
            self.engine = create_engine(database_url, echo=echo)

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

    def create_tables(self):
        """Create all tables."""
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self):
        """Drop all tables."""
        Base.metadata.drop_all(bind=self.engine)

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Provide a transactional scope for database operations.

        Yields:
            SQLAlchemy session
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session(self) -> Session:
        """Get a new database session.

        Returns:
            SQLAlchemy session (caller must close it)
        """
        return self.SessionLocal()
