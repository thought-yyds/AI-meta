"""
Database initialization script.
Run this script to create the database and all tables.
"""
import sys
from pathlib import Path
import pymysql
from sqlalchemy import create_engine, text

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import engine, Base
from app.models.models import User, Session, Message, Summary  # noqa: F401
from app.core.config import settings

def create_database_if_not_exists():
    """Create the database if it doesn't exist."""
    # Connect to MySQL server (without specifying database)
    temp_url = f"mysql+pymysql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/"
    temp_engine = create_engine(temp_url)
    
    with temp_engine.connect() as conn:
        # Create database if it doesn't exist
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{settings.db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        conn.commit()
    
    print(f"✅ Database '{settings.db_name}' is ready")

def init_database():
    """Initialize the database by creating all tables."""
    print(f"Connecting to MySQL at: {settings.db_host}:{settings.db_port}")
    print(f"Database: {settings.db_name}")
    print(f"User: {settings.db_user}")
    
    # Create database if it doesn't exist
    try:
        create_database_if_not_exists()
    except Exception as e:
        print(f"⚠️  Warning: Could not create database (it may already exist): {e}")
    
    print("Creating all tables...")
    
    # Create all tables
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database initialized successfully!")
        print(f"✅ All tables created in database '{settings.db_name}'")
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        print("\nPlease ensure:")
        print("1. MySQL server is running")
        print("2. Database credentials are correct")
        print("3. User has CREATE DATABASE and CREATE TABLE permissions")
        sys.exit(1)

if __name__ == "__main__":
    init_database()

