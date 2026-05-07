"""Initialize AMP database schema."""

from amp.config import settings
from amp.storage.database import Database
from amp.storage.schema import Base

def main():
    """Create all database tables."""
    print(f"Initializing database at {settings.database.url}")

    database = Database(settings.database.url)

    # Create all tables
    Base.metadata.create_all(database.engine)

    print("Database tables created successfully!")
    print("\nCreated tables:")
    for table in Base.metadata.sorted_tables:
        print(f"  - {table.name}")

if __name__ == "__main__":
    main()
