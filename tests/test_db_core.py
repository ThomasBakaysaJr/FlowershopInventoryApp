import pytest
import sqlite3
import os
import sys
import pandas as pd
import datetime

# Add parent directory to path to import db_utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import db_utils

def test_log_production_logic(setup_db):
    """Tests that logging production updates goals and deducts inventory."""
    db_path = setup_db
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # Get Product ID
        cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special'")
        p_id = cursor.fetchone()[0]

        # Get Goal ID (seeded in conftest)
        cursor.execute("SELECT goal_id FROM production_goals WHERE product_id = ?", (p_id,))
        goal_id = cursor.fetchone()[0]
        
        # Get Initial Inventory for Red Rose (Item ID 1)
        cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
        initial_stock = cursor.fetchone()[0] # Should be 100
    finally:
        conn.close()

    # --- ACTION: Log Production ---
    assert db_utils.log_production(goal_id) is True

    # --- VERIFY ---
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # Check Goal Progress (Should be 1 made)
        cursor.execute("SELECT qty_fulfilled FROM production_goals WHERE product_id = ?", (p_id,))
        assert cursor.fetchone()[0] == 1
        
        # Check Inventory Deduction (Recipe is 12 Roses)
        cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
        new_stock = cursor.fetchone()[0]
        assert new_stock == initial_stock - 12
        
        # Check Log Entry Created
        cursor.execute("SELECT COUNT(*) FROM production_logs WHERE product_id = ?", (p_id,))
        assert cursor.fetchone()[0] == 1
    finally:
        conn.close()

def test_undo_production_logic(setup_db):
    """Tests that undoing production reverts goals and returns inventory."""
    db_path = setup_db
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special'")
        p_id = cursor.fetchone()[0]
        cursor.execute("SELECT goal_id FROM production_goals WHERE product_id = ?", (p_id,))
        goal_id = cursor.fetchone()[0]
    finally:
        conn.close()

    # Setup: Log one first
    db_utils.log_production(goal_id)

    # --- ACTION: Undo Production ---
    assert db_utils.undo_production(goal_id) is True

    # --- VERIFY ---
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # Check Goal Progress (Should be back to 0)
        cursor.execute("SELECT qty_fulfilled FROM production_goals WHERE product_id = ?", (p_id,))
        assert cursor.fetchone()[0] == 0
        
        # Check Inventory Return (Should be back to 100)
        cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
        assert cursor.fetchone()[0] == 100
        
        # Check Log Entry Removed
        cursor.execute("SELECT COUNT(*) FROM production_logs WHERE product_id = ?", (p_id,))
        assert cursor.fetchone()[0] == 0
    finally:
        conn.close()

def test_get_production_goals_range(setup_db):
    """Tests fetching goals within a date range."""
    # Seeded goal is 2023-10-30
    start_date = datetime.date(2023, 10, 1)
    end_date = datetime.date(2023, 11, 1)
    
    df = db_utils.get_production_goals_range(start_date, end_date)
    
    assert not df.empty
    assert 'qty_ordered' in df.columns
    # Check for the seeded goal
    assert len(df) >= 1
    assert df.iloc[0]['qty_ordered'] == 10

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

def test_log_production_targets_specific_goal(setup_db):
    """Tests that production logs to the EXACT goal ID provided, ignoring dates."""
    db_path = setup_db
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # Get Product ID
        cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special'")
        p_id = cursor.fetchone()[0]
        
        # CLEANUP: Remove the default goal seeded by conftest (dated 2023) 
        # so it doesn't get picked up as the "earliest" goal.
        cursor.execute("DELETE FROM production_goals WHERE product_id = ?", (p_id,))
        
        # Create two goals for the same product
        # Goal 1: Due later (Feb 20)
        cursor.execute("INSERT INTO production_goals (product_id, qty_ordered, qty_fulfilled, due_date) VALUES (?, 10, 0, '2026-02-20')", (p_id,))
        g_id_late = cursor.lastrowid
        
        # Goal 2: Due earlier (Feb 10)
        cursor.execute("INSERT INTO production_goals (product_id, qty_ordered, qty_fulfilled, due_date) VALUES (?, 10, 0, '2026-02-10')", (p_id,))
        g_id_early = cursor.lastrowid
        conn.commit()
        
        # --- ACTION: Log Production ---
        # We explicitly target the LATE goal (Feb 20), ignoring the early one (Feb 10)
        db_utils.log_production(g_id_late)
        
        # --- VERIFY ---
        cursor.execute("SELECT qty_fulfilled FROM production_goals WHERE goal_id = ?", (g_id_late,))
        assert cursor.fetchone()[0] == 1
        
        cursor.execute("SELECT qty_fulfilled FROM production_goals WHERE goal_id = ?", (g_id_early,))
        assert cursor.fetchone()[0] == 0
    finally:
        conn.close()