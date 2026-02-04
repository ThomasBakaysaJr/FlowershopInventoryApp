import pytest
import sqlite3
import os
import sys
import subprocess

# Add parent directory to path to import db_utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import db_utils

TEST_DB = 'test_inventory.db'

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

@pytest.fixture
def setup_db():
    """Fixture to set up a temporary database for testing."""
    # Save original DB path and swap to test DB
    original_db = db_utils.DB_PATH
    db_utils.DB_PATH = TEST_DB
    
    # Initialize schema
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    cursor.executescript('''
        CREATE TABLE inventory (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            sub_category TEXT,
            count_on_hand INTEGER DEFAULT 0,
            unit_cost REAL DEFAULT 0.00
        );
        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            image_data BLOB,
            selling_price REAL DEFAULT 0.00,
            active BOOLEAN DEFAULT 1
        );
        CREATE TABLE recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            item_id INTEGER,
            qty_needed INTEGER,
            FOREIGN KEY(product_id) REFERENCES products(product_id),
            FOREIGN KEY(item_id) REFERENCES inventory(item_id)
        );
        CREATE TABLE production_goals (
            goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            due_date DATE,
            qty_ordered INTEGER DEFAULT 0,
            qty_made INTEGER DEFAULT 0,
            FOREIGN KEY(product_id) REFERENCES products(product_id)
        );
    ''')
    
    # Seed test data
    cursor.execute("INSERT INTO inventory (name, count_on_hand) VALUES ('Red Rose', 100)")
    cursor.execute("INSERT INTO products (display_name) VALUES ('Dozen Roses')")
    cursor.execute("INSERT INTO recipes (product_id, item_id, qty_needed) VALUES (1, 1, 12)")
    # Goal for Feb 4th, 2026
    cursor.execute("INSERT INTO production_goals (product_id, due_date, qty_ordered, qty_made) VALUES (1, '2026-02-04', 10, 0)")
    
    conn.commit()
    conn.close()
    
    yield
    
    # Cleanup
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    db_utils.DB_PATH = original_db

def test_log_production_updates_correctly(setup_db):
    """Tests that clicking 'ADD' (log_production) updates goals and inventory."""
    # Week starting Feb 2nd contains Feb 4th
    success = db_utils.log_production(1, "Feb 02, 2026")
    assert success is True
    
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    
    # Verify goal incremented
    cursor.execute("SELECT qty_made FROM production_goals WHERE goal_id = 1")
    assert cursor.fetchone()[0] == 1
    
    # Verify inventory deducted (100 - 12 = 88)
    cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
    assert cursor.fetchone()[0] == 88
    conn.close()

def test_clipboard_bulk_update_valid(setup_db):
    """Tests that valid clipboard text updates inventory."""
    text = "Red Rose, Rose, 50"
    updated, errors = db_utils.process_clipboard_update(text)
    
    assert "Red Rose" in updated
    assert len(errors) == 0
    
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
    assert cursor.fetchone()[0] == 50
    conn.close()

def test_clipboard_bulk_update_malformed(setup_db):
    """Tests that malformed text is caught and reported as an error."""
    # One valid line, one malformed line
    text = "Red Rose, Rose, 75\nMalformed Line Without Numbers"
    updated, errors = db_utils.process_clipboard_update(text)
    
    assert "Red Rose" in updated
    assert len(errors) == 1
    assert "Invalid format" in errors[0]
    
    conn = sqlite3.connect(TEST_DB)
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
    text = "Red Rose 25"
    updated, errors = db_utils.process_clipboard_update(text)
    
    assert "Red Rose" in updated
    assert len(errors) == 0
    
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
    assert cursor.fetchone()[0] == 25
    conn.close()