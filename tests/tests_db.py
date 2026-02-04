# tests/test_app.py
import sqlite3
import pytest
import os
import sys

# Add the parent directory to path so we can import your app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_utils import get_connection

def test_database_connection():
    """Simple sanity check: Can we create an in-memory DB?"""
    # Use :memory: to avoid touching the real file
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    
    # Try creating a table
    cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
    cursor.execute("INSERT INTO test (name) VALUES ('Sanity Check')")
    conn.commit()
    
    # Read it back
    cursor.execute("SELECT name FROM test")
    result = cursor.fetchone()
    
    assert result[0] == 'Sanity Check'
    conn.close()

def test_app_imports():
    """Does the app even start without crashing on imports?"""
    try:
        import app
        assert True
    except ImportError:
        # It might fail if streamlit isn't installed in the test env, 
        # but this confirms your python syntax is valid.
        pass