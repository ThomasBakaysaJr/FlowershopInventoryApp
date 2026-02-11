import pytest
import sqlite3
import os
import sys
from unittest.mock import patch

# Add parent directory to path to import init_db
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import init_db
from src.utils import db_utils

@pytest.fixture
def mock_db(tmp_path):
    """Sets up a temporary database with the schema and patches db_utils to use it."""
    db_file = tmp_path / "test_inventory.db"
    
    # Use the single source of truth for schema
    init_db.initialize_database(str(db_file))
    
    # Patch the DB_PATH in db_utils to point to our temp file
    with patch("src.utils.db_utils.DB_PATH", str(db_file)):
        yield str(db_file)

def test_produce_stock(mock_db):
    """Test that producing stock increases product stock and decreases inventory."""
    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()
    
    # Setup: 1 Product (Stock 0), 1 Ingredient (Stock 100), Recipe needs 10
    cursor.execute("INSERT INTO inventory (name, count_on_hand) VALUES ('Rose', 100)")
    item_id = cursor.lastrowid
    cursor.execute("INSERT INTO products (display_name, stock_on_hand) VALUES ('Bouquet', 0)")
    p_id = cursor.lastrowid
    cursor.execute("INSERT INTO recipes (product_id, item_id, qty_needed) VALUES (?, ?, 10)", (p_id, item_id))
    conn.commit()
    conn.close()
    
    # Action
    assert db_utils.produce_stock(p_id) is True
    
    # Verify
    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()
    
    # Check Stock increased
    cursor.execute("SELECT stock_on_hand FROM products WHERE product_id = ?", (p_id,))
    assert cursor.fetchone()[0] == 1
    
    # Check Inventory deducted
    cursor.execute("SELECT count_on_hand FROM inventory WHERE item_id = ?", (item_id,))
    assert cursor.fetchone()[0] == 90
    
    # Check Log created (goal_id should be NULL for stock production)
    cursor.execute("SELECT count(*) FROM production_logs WHERE product_id = ? AND goal_id IS NULL", (p_id,))
    assert cursor.fetchone()[0] == 1
    conn.close()

def test_fulfill_goal_logic(mock_db):
    """Test fulfillment constraints: Cannot fulfill if stock is 0."""
    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()
    
    # Setup: Product with 0 Stock, Goal for 5
    cursor.execute("INSERT INTO products (display_name, stock_on_hand) VALUES ('Bouquet', 0)")
    p_id = cursor.lastrowid
    cursor.execute("INSERT INTO production_goals (product_id, qty_ordered, qty_fulfilled) VALUES (?, 5, 0)", (p_id,))
    g_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Action 1: Try to fulfill with 0 stock -> Should Fail
    assert db_utils.fulfill_goal(g_id) == 0
    
    # Action 2: Manually add stock
    conn = sqlite3.connect(mock_db)
    conn.execute("UPDATE products SET stock_on_hand = 1 WHERE product_id = ?", (p_id,))
    conn.commit()
    conn.close()
    
    # Action 3: Try to fulfill again -> Should Succeed
    assert db_utils.fulfill_goal(g_id) == 1
    
    # Verify
    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()
    cursor.execute("SELECT stock_on_hand FROM products WHERE product_id = ?", (p_id,))
    assert cursor.fetchone()[0] == 0 # Consumed
    
    cursor.execute("SELECT qty_fulfilled FROM production_goals WHERE goal_id = ?", (g_id,))
    assert cursor.fetchone()[0] == 1 # Fulfilled
    conn.close()

def test_undo_fulfillment(mock_db):
    """Test that undoing fulfillment returns item to stock."""
    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()
    
    # Setup: Product (Stock 0), Goal (Fulfilled 1)
    cursor.execute("INSERT INTO products (display_name, stock_on_hand) VALUES ('Bouquet', 0)")
    p_id = cursor.lastrowid
    cursor.execute("INSERT INTO production_goals (product_id, qty_ordered, qty_fulfilled) VALUES (?, 5, 1)", (p_id,))
    g_id = cursor.lastrowid
    # Must have a log to undo
    cursor.execute("INSERT INTO production_logs (goal_id, product_id) VALUES (?, ?)", (g_id, p_id))
    conn.commit()
    conn.close()
    
    # Action
    assert db_utils.undo_fulfillment(g_id) is True
    
    # Verify
    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()
    cursor.execute("SELECT stock_on_hand FROM products WHERE product_id = ?", (p_id,))
    assert cursor.fetchone()[0] == 1 # Returned to cooler
    
    cursor.execute("SELECT qty_fulfilled FROM production_goals WHERE goal_id = ?", (g_id,))
    assert cursor.fetchone()[0] == 0 # Reversed
    conn.close()

def test_stock_rollover(mock_db):
    """Test that updating a recipe carries over the stock count."""
    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()
    
    # Setup: Old Product with Stock = 5
    cursor.execute("INSERT INTO products (display_name, stock_on_hand, active) VALUES ('Old Ver', 5, 1)")
    p_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Action: Update Recipe with Rollover=True
    # Note: recipe_items is empty list for simplicity
    db_utils.update_product_recipe(p_id, "New Ver", [], rollover_stock=True)
    
    # Verify
    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()
    
    # Check Old is archived
    cursor.execute("SELECT active FROM products WHERE product_id = ?", (p_id,))
    assert cursor.fetchone()[0] == 0
    
    # Check New has stock 5
    cursor.execute("SELECT stock_on_hand, display_name FROM products WHERE active = 1")
    row = cursor.fetchone()
    assert row[1] == "New Ver"
    assert row[0] == 5
    conn.close()