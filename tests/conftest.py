import pytest
import sqlite3
import os
import sys

# Add parent directory to path to import db_utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import db_utils

TEST_DB = 'test_suite.db'

@pytest.fixture
def setup_db():
    """
    Shared fixture to set up a temporary database.
    Yields the path to the temporary database.
    """
    original_db = db_utils.DB_PATH
    db_utils.DB_PATH = TEST_DB
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

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
        CREATE TABLE production_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER,
            product_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(goal_id) REFERENCES production_goals(goal_id),
            FOREIGN KEY(product_id) REFERENCES products(product_id)
        );
    ''')
    
    # Seed initial data
    # Give initial stock of 100 to allow testing deductions
    cursor.execute("INSERT INTO inventory (name, unit_cost, count_on_hand) VALUES ('Red Rose', 1.00, 100)")
    cursor.execute("INSERT INTO inventory (name, unit_cost, count_on_hand) VALUES ('White Lily', 2.00, 100)")
    cursor.execute("INSERT INTO products (display_name, selling_price) VALUES ('Valentine Special', 50.00)")
    
    # Link Rose to Product (Initial Recipe: 12 Roses)
    cursor.execute("INSERT INTO recipes (product_id, item_id, qty_needed) VALUES (1, 1, 12)")
    
    # Add a production goal (Due next Monday for consistent testing)
    cursor.execute("INSERT INTO production_goals (product_id, qty_ordered, due_date) VALUES (1, 10, '2023-10-30')")
    
    conn.commit()
    conn.close()
    
    yield TEST_DB
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    db_utils.DB_PATH = original_db