import pytest
import os

# Set testing mode BEFORE any imports
os.environ["TESTING"] = "true"

from backend.database import Base, engine, init_db


@pytest.fixture(scope="function", autouse=True)
def setup_test_database():
    """Create tables before each test and drop them after"""
    # Create all tables in the test database
    Base.metadata.create_all(bind=engine)
    
    yield
    
    # Clean up - drop all tables after test
    Base.metadata.drop_all(bind=engine)
