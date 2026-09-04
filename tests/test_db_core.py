import datetime
import os
import sqlite3
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import db_utils


def test_log_production_increments_goal_and_deducts_inventory(setup_db):
    """Logging production updates qty_fulfilled and deducts recipe ingredients."""
    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special'")
        p_id = cursor.fetchone()[0]
        cursor.execute("SELECT goal_id FROM production_goals WHERE product_id = ?", (p_id,))
        goal_id = cursor.fetchone()[0]
        cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
        initial_stock = cursor.fetchone()[0]
    finally:
        conn.close()

    assert db_utils.log_production(goal_id) == 1

    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT qty_fulfilled FROM production_goals WHERE product_id = ?", (p_id,))
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
        assert cursor.fetchone()[0] == initial_stock - 12

        cursor.execute("SELECT COUNT(*) FROM production_logs WHERE product_id = ?", (p_id,))
        assert cursor.fetchone()[0] == 1
    finally:
        conn.close()


def test_undo_production_reverts_goal_and_restores_inventory(setup_db):
    """Undoing production decrements qty_fulfilled and restores recipe ingredients."""
    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special'")
        p_id = cursor.fetchone()[0]
        cursor.execute("SELECT goal_id FROM production_goals WHERE product_id = ?", (p_id,))
        goal_id = cursor.fetchone()[0]
    finally:
        conn.close()

    db_utils.log_production(goal_id)
    assert db_utils.undo_production(goal_id) is True

    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT qty_fulfilled FROM production_goals WHERE product_id = ?", (p_id,))
        assert cursor.fetchone()[0] == 0

        cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
        assert cursor.fetchone()[0] == 100

        cursor.execute("SELECT COUNT(*) FROM production_logs WHERE product_id = ?", (p_id,))
        assert cursor.fetchone()[0] == 0
    finally:
        conn.close()


def test_get_production_goals_range_includes_and_excludes_correctly(setup_db):
    """Goals within the date range are returned; goals outside are not."""
    # Seeded goal is 2023-10-30
    in_range = db_utils.get_production_goals_range(
        datetime.date(2023, 10, 1),
        datetime.date(2023, 11, 1),
    )
    assert not in_range.empty
    assert in_range.iloc[0]['qty_ordered'] == 10

    # Range that does not contain the seeded date
    out_of_range = db_utils.get_production_goals_range(
        datetime.date(2024, 1, 1),
        datetime.date(2024, 1, 31),
    )
    assert out_of_range.empty


def test_log_production_targets_specific_goal_id(setup_db):
    """log_production updates only the explicitly provided goal_id, ignoring others."""
    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special'")
        p_id = cursor.fetchone()[0]
        cursor.execute("DELETE FROM production_goals WHERE product_id = ?", (p_id,))

        cursor.execute(
            "INSERT INTO production_goals (product_id, qty_ordered, qty_fulfilled, due_date) VALUES (?, 10, 0, '2026-02-20')",
            (p_id,)
        )
        g_id_late = cursor.lastrowid
        cursor.execute(
            "INSERT INTO production_goals (product_id, qty_ordered, qty_fulfilled, due_date) VALUES (?, 10, 0, '2026-02-10')",
            (p_id,)
        )
        g_id_early = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    db_utils.log_production(g_id_late)

    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT qty_fulfilled FROM production_goals WHERE goal_id = ?", (g_id_late,))
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT qty_fulfilled FROM production_goals WHERE goal_id = ?", (g_id_early,))
        assert cursor.fetchone()[0] == 0
    finally:
        conn.close()


def test_foreign_keys_enforced(setup_db):
    """PRAGMA foreign_keys is per-connection and off by default in SQLite.

    get_connection() turns it on for every connection; this pins that it
    actually takes effect at runtime.
    """
    conn = db_utils.get_connection()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO recipes (product_id, item_id, qty_needed) VALUES (?, ?, ?)",
                (99999, 1, 1),
            )
            conn.commit()
    finally:
        conn.close()
