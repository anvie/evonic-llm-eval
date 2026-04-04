"""
Pytest configuration and fixtures for unit tests.
Uses a separate test database to avoid polluting production data.
"""

import pytest
import os
import sys
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def use_test_database(monkeypatch, tmp_path):
    """
    Automatically use a temporary test database for all tests.
    This prevents unit tests from polluting the production database.
    """
    # Create a temporary database file
    test_db_path = str(tmp_path / "test_evaluation.db")
    
    # Patch the database path before importing db
    from models import db as db_module
    
    # Store original path
    original_path = db_module.db.db_path
    
    # Set test database path
    db_module.db.db_path = test_db_path
    
    # Reinitialize tables in test database
    db_module.db._init_tables()
    
    yield
    
    # Restore original path (though not strictly necessary due to test isolation)
    db_module.db.db_path = original_path
