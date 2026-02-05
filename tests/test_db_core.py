import pytest
import sqlite3
import os
import sys
import pandas as pd

# Add parent directory to path to import db_utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import db_utils

def test_log_production_logic(setup_db):
    """Tests that logging production updates goals and deducts inventory."""
    db_path = setup_db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get Product ID
    cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special'")
    p_id = cursor.fetchone()[0]
    
    # Get Initial Inventory for Red Rose (Item ID 1)
    cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
    initial_stock = cursor.fetchone()[0] # Should be 100
    conn.close()

    # --- ACTION: Log Production ---
    assert db_utils.log_production(p_id) is True

    # --- VERIFY ---
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check Goal Progress (Should be 1 made)
    cursor.execute("SELECT qty_made FROM production_goals WHERE product_id = ?", (p_id,))
    assert cursor.fetchone()[0] == 1
    
    # Check Inventory Deduction (Recipe is 12 Roses)
    cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
    new_stock = cursor.fetchone()[0]
    assert new_stock == initial_stock - 12
    
    # Check Log Entry Created
    cursor.execute("SELECT COUNT(*) FROM production_logs WHERE product_id = ?", (p_id,))
    assert cursor.fetchone()[0] == 1
    
    conn.close()

def test_undo_production_logic(setup_db):
    """Tests that undoing production reverts goals and returns inventory."""
    db_path = setup_db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special'")
    p_id = cursor.fetchone()[0]
    conn.close()

    # Setup: Log one first
    db_utils.log_production(p_id)

    # --- ACTION: Undo Production ---
    assert db_utils.undo_production(p_id) is True

    # --- VERIFY ---
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check Goal Progress (Should be back to 0)
    cursor.execute("SELECT qty_made FROM production_goals WHERE product_id = ?", (p_id,))
    assert cursor.fetchone()[0] == 0
    
    # Check Inventory Return (Should be back to 100)
    cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
    assert cursor.fetchone()[0] == 100
    
    # Check Log Entry Removed
    cursor.execute("SELECT COUNT(*) FROM production_logs WHERE product_id = ?", (p_id,))
    assert cursor.fetchone()[0] == 0
    
    conn.close()

def test_get_weekly_production_goals(setup_db):
    """Tests that goals are correctly grouped by week."""
    df = db_utils.get_weekly_production_goals()
    
    assert not df.empty
    assert 'Week Starting' in df.columns
    assert 'qty_ordered' in df.columns
    
    # Check that our seeded goal (2023-10-30) is present
    # 2023-10-30 is a Monday, so it should be the start of that week
    target_row = df[df['week_start_iso'] == '2023-10-30']
    assert not target_row.empty
    assert target_row.iloc[0]['qty_ordered'] == 10

def test_clipboard_update(setup_db):
    """Tests the clipboard parsing utility (Comma Separated)."""
    db_path = setup_db
    text = "Red Rose, 50\nWhite Lily, 20"
    updated, errors = db_utils.process_clipboard_update(text)
    
    assert len(updated) == 2
    assert len(errors) == 0

    # Verify DB update
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
    assert cursor.fetchone()[0] == 50
    conn.close()

def test_clipboard_update_whitespace(setup_db):
    """Tests the clipboard parsing utility (Whitespace Separated)."""
    db_path = setup_db
    text = "Red Rose 75"
    updated, errors = db_utils.process_clipboard_update(text)
    
    assert "Red Rose" in updated
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
    assert cursor.fetchone()[0] == 75
    conn.close()