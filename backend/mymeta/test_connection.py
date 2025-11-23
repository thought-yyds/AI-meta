"""
Test script to verify database and API connection.
Run this to check if everything is set up correctly.
"""
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import engine, SessionLocal
from app.models.models import User, Session, Message, Summary
from app.core.config import settings
from sqlalchemy import inspect

def test_database():
    """Test database connection and table creation."""
    print("=" * 50)
    print("Testing Database Connection")
    print("=" * 50)
    
    # Display connection info
    print(f"Connecting to MySQL: {settings.db_host}:{settings.db_port}")
    print(f"Database: {settings.db_name}")
    print(f"User: {settings.db_user}")
    
    # Test connection
    try:
        with engine.connect() as conn:
            print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("\nPlease check:")
        print("1. MySQL server is running")
        print("2. Database credentials in .env file (or default values)")
        print("3. Database exists (run 'python init_db.py' to create it)")
        return False
    
    # Check if tables exist
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    required_tables = ['users', 'sessions', 'messages', 'summaries']
    
    print("\nChecking tables:")
    for table in required_tables:
        if table in tables:
            print(f"  ✅ Table '{table}' exists")
        else:
            print(f"  ❌ Table '{table}' missing")
    
    # Test database operations
    try:
        db = SessionLocal()
        user_count = db.query(User).count()
        session_count = db.query(Session).count()
        print(f"\nDatabase statistics:")
        print(f"  Users: {user_count}")
        print(f"  Sessions: {session_count}")
        db.close()
        print("✅ Database operations working")
    except Exception as e:
        print(f"❌ Database operations failed: {e}")
        return False
    
    return True

def test_config():
    """Test configuration."""
    print("\n" + "=" * 50)
    print("Testing Configuration")
    print("=" * 50)
    print(f"Database URL: {settings.database_url}")
    print(f"API Host: {settings.host}")
    print(f"API Port: {settings.port}")
    print(f"CORS Allowed Origins: {settings.allowed_origins}")
    print("✅ Configuration loaded")

if __name__ == "__main__":
    print("\n🔍 Running connection tests...\n")
    test_config()
    success = test_database()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All tests passed! Database is ready.")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    print("=" * 50)

