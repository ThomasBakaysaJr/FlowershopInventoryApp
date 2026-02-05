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

    assert db_utils.delete_product("Valentine Special") is True
    
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
    # New Recipe: 5 Lilies instead of 12 Roses
    new_ingredients = pd.DataFrame([
        {'Ingredient': 'White Lily', 'Qty': 5}
    ])
    
    success = db_utils.update_product_recipe("Valentine Special", new_ingredients, new_price=60.00)
    assert success is True
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get 'White Lily' ID dynamically
    cursor.execute("SELECT item_id FROM inventory WHERE name = 'White Lily'")
    lily_id = cursor.fetchone()[0]

    # Verify Price Update
    cursor.execute("SELECT selling_price FROM products WHERE display_name = 'Valentine Special' AND active = 1")
    new_price = cursor.fetchone()[0]
    
    # Verify Recipe Update
    cursor.execute("SELECT item_id, qty_needed FROM recipes WHERE product_id = (SELECT product_id FROM products WHERE display_name = 'Valentine Special' AND active = 1)")
    rows = cursor.fetchall()
    
    conn.close()

    assert new_price == 60.00
    assert len(rows) == 1
    assert rows[0] == (lily_id, 5) # (item_id, qty)