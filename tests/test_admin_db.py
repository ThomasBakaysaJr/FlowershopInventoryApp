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