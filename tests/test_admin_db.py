import pytest
import sqlite3
import os
import sys

# Add parent directory to path to import db_utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import db_utils

def test_update_inventory_cost(setup_db):
    """Tests that the admin tool can update unit costs correctly."""
    db_path = setup_db
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # Get initial cost for Red Rose (seeded in conftest as 1.00)
        cursor.execute("SELECT item_id, unit_cost FROM inventory WHERE name = 'Red Rose'")
        item_id, old_cost = cursor.fetchone()
        assert old_cost == 1.00
        
        # --- ACTION: Update Cost ---
        new_cost = 1.55
        success = db_utils.update_inventory_cost(item_id, new_cost)
        assert success is True
        
        # --- VERIFY ---
        cursor.execute("SELECT unit_cost FROM inventory WHERE item_id = ?", (item_id,))
        assert cursor.fetchone()[0] == 1.55
        
    finally:
        conn.close()

def test_get_product_details_and_update(setup_db):
    """Tests fetching full product details and updating with a rename."""
    db_path = setup_db
    
    # 1. Verify initial state (Valentine Special created in conftest)
    details = db_utils.get_product_details("Valentine Special")
    assert details is not None
    assert details['price'] == 50.00
    assert len(details['recipe']) == 1
    assert details['recipe'][0]['name'] == 'Red Rose'
    
    # 2. Update Product (Rename + Price Change)
    # Recipe: Change from 12 Roses to 6 Roses
    new_recipe = [(1, 6)] # 1 is Red Rose item_id
    
    success = db_utils.update_product_recipe(
        current_product_id=details['product_id'],
        new_name="Valentine Deluxe",
        recipe_items=new_recipe,
        new_price=55.00
    )
    assert success is True
    
    # 3. Verify Old is Gone/Archived (get_product_details checks active=1)
    assert db_utils.get_product_details("Valentine Special") is None
    
    # 4. Verify New Details
    new_details = db_utils.get_product_details("Valentine Deluxe")
    assert new_details is not None
    assert new_details['price'] == 55.00
    assert new_details['recipe'][0]['qty'] == 6