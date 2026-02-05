import pytest
import sqlite3
import os
import sys
import pandas as pd

# Add parent directory to path to import db_utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import db_utils

def test_check_product_exists(setup_db):
    """Verifies the existence check logic."""
    assert db_utils.check_product_exists("Valentine Special") is True
    assert db_utils.check_product_exists("valentine special") is True # Case insensitive
    assert db_utils.check_product_exists("Non Existent") is False

def test_delete_product_cascade(setup_db):
    """Ensures deleting a product marks it as inactive but keeps history."""
    db_path = setup_db
    # Get ID dynamically to avoid hardcoding '1'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special'")
    p_id = cursor.fetchone()[0]
    conn.close()

    assert db_utils.delete_product(p_id) is True
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check Product is NOT gone, but active is 0
    cursor.execute("SELECT active FROM products WHERE display_name = 'Valentine Special'")
    active_status = cursor.fetchone()[0]
    
    # Check Recipe still exists (for history)
    cursor.execute("SELECT 1 FROM recipes WHERE product_id = ?", (p_id,))
    recipe_exists = cursor.fetchone()
    
    # Check Goals still exist (for history)
    cursor.execute("SELECT 1 FROM production_goals WHERE product_id = ?", (p_id,))
    goal_exists = cursor.fetchone()
    
    conn.close()
    
    assert active_status == 0
    assert recipe_exists is not None
    assert goal_exists is not None

def test_update_product_recipe(setup_db):
    """Tests updating price and ingredients."""
    db_path = setup_db
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get 'White Lily' ID dynamically
    cursor.execute("SELECT item_id FROM inventory WHERE name = 'White Lily'")
    lily_id = cursor.fetchone()[0]
    
    # Create a dummy goal for the old product to verify migration
    cursor.execute("INSERT INTO production_goals (product_id, qty_ordered) VALUES ((SELECT product_id FROM products WHERE display_name = 'Valentine Special' AND active = 1), 10)")
    
    conn.close()

    # New Recipe: 5 Lilies instead of 12 Roses
    new_recipe_items = [(lily_id, 5)]
    
    success = db_utils.update_product_recipe("Valentine Special", new_recipe_items, new_price=60.00)
    assert success is True
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Verify Price Update
    cursor.execute("SELECT product_id, selling_price FROM products WHERE display_name = 'Valentine Special' AND active = 1")
    row = cursor.fetchone()
    new_p_id = row[0]
    new_price = row[1]
    
    # Verify Recipe Update
    cursor.execute("SELECT item_id, qty_needed FROM recipes WHERE product_id = ?", (new_p_id,))
    rows = cursor.fetchall()
    
    # Verify Goal Migration
    cursor.execute("SELECT count(*) FROM production_goals WHERE product_id = ?", (new_p_id,))
    goal_count = cursor.fetchone()[0]
    
    conn.close()

    assert new_price == 60.00
    assert len(rows) == 1
    assert rows[0] == (lily_id, 5) # (item_id, qty)
    assert goal_count == 0 # The goal should NOT move to the new ID