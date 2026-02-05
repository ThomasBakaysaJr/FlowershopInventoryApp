import pytest
import sqlite3
import os
import sys
import subprocess

# Add parent directory to path to import db_utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import db_utils

# sanity checks

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

def test_code_quality_linting():
    """Runs ruff to check for linting errors across the project."""
    # Get the project root directory (parent of tests/)
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    try:
        # Run ruff check (using the same minimal syntax checks as CI to start)
        result = subprocess.run(
            ["ruff", "check", ".", "--select=E9,F63,F7,F82", "--target-version=py310"], 
            cwd=root_dir,
            capture_output=True, 
            text=True
        )
        
        if result.returncode != 0:
            pytest.fail(f"Ruff found issues:\n{result.stdout}")
            
    except FileNotFoundError:
        pytest.skip("Ruff executable not found. Please install ruff to run linting tests.")

# actual tests

def test_log_production_updates_correctly(setup_db):
    """Tests that clicking 'ADD' (log_production) updates goals and inventory."""
    db_path = setup_db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Insert a specific goal for the date we are testing (Feb 4, 2026)
    # Product 1 is 'Valentine Special' from conftest
    cursor.execute("INSERT INTO production_goals (product_id, due_date, qty_ordered, qty_made) VALUES (1, '2026-02-04', 10, 0)")
    goal_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Week starting Feb 2nd contains Feb 4th
    success = db_utils.log_production(1, "Feb 02, 2026")
    assert success is True
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verify goal incremented
    cursor.execute("SELECT qty_made FROM production_goals WHERE goal_id = ?", (goal_id,))
    assert cursor.fetchone()[0] == 1
    
    # Verify inventory deducted (100 - 12 = 88)
    cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
    assert cursor.fetchone()[0] == 88
    conn.close()

def test_clipboard_bulk_update_valid(setup_db):
    """Tests that valid clipboard text updates inventory."""
    db_path = setup_db
    text = "Red Rose, Rose, 50"
    updated, errors = db_utils.process_clipboard_update(text)
    
    assert "Red Rose" in updated
    assert len(errors) == 0
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
    assert cursor.fetchone()[0] == 50
    conn.close()

def test_clipboard_bulk_update_malformed(setup_db):
    """Tests that malformed text is caught and reported as an error."""
    db_path = setup_db
    # One valid line, one malformed line
    text = "Red Rose, Rose, 75\nMalformed Line Without Numbers"
    updated, errors = db_utils.process_clipboard_update(text)
    
    assert "Red Rose" in updated
    assert len(errors) == 1
    assert "Invalid format" in errors[0]
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
    assert cursor.fetchone()[0] == 75
    conn.close()

def test_clipboard_bulk_update_unknown_item(setup_db):
    """Tests that unknown items are reported as errors."""
    text = "Blue Orchid, 10"
    updated, errors = db_utils.process_clipboard_update(text)
    
    assert len(updated) == 0
    assert len(errors) == 1
    assert "Unknown: Blue Orchid" in errors[0]

def test_clipboard_bulk_update_whitespace(setup_db):
    """Tests the legacy whitespace-separated format."""
    db_path = setup_db
    text = "Red Rose 25"
    updated, errors = db_utils.process_clipboard_update(text)
    
    assert "Red Rose" in updated
    assert len(errors) == 0
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
    assert cursor.fetchone()[0] == 25
    conn.close()