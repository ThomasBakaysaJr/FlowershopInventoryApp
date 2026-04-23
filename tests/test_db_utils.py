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
    init_db.initialize_database(str(db_file))

    with patch("src.utils.db_utils.DB_PATH", str(db_file)):
        yield str(db_file)


def test_log_production_skips_untracked_items(mock_db):
    """Production deducts tracked recipe items but leaves untracked ones alone."""
    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()

    # Tracked hardgood + untracked flower
    cursor.execute(
        "INSERT INTO inventory (name, count_on_hand, track_inventory) VALUES ('Vase', 50, 1)"
    )
    vase_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO inventory (name, count_on_hand, track_inventory) VALUES ('Rose', 100, 0)"
    )
    rose_id = cursor.lastrowid

    cursor.execute("INSERT INTO products (display_name) VALUES ('Bouquet')")
    p_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type) VALUES (?, ?, ?, 'Specific')",
        (p_id, vase_id, 1),
    )
    cursor.execute(
        "INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type) VALUES (?, ?, ?, 'Specific')",
        (p_id, rose_id, 12),
    )
    cursor.execute(
        "INSERT INTO production_goals (product_id, qty_ordered, qty_fulfilled, due_date) VALUES (?, 5, 0, '2026-02-14')",
        (p_id,),
    )
    g_id = cursor.lastrowid
    conn.commit()
    conn.close()

    assert db_utils.log_production(g_id) == 1

    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()
    cursor.execute("SELECT count_on_hand FROM inventory WHERE item_id = ?", (vase_id,))
    assert cursor.fetchone()[0] == 49  # tracked item deducted
    cursor.execute("SELECT count_on_hand FROM inventory WHERE item_id = ?", (rose_id,))
    assert cursor.fetchone()[0] == 100  # untracked item untouched
    cursor.execute("SELECT qty_fulfilled FROM production_goals WHERE goal_id = ?", (g_id,))
    assert cursor.fetchone()[0] == 1
    conn.close()


def test_log_production_batch_qty(mock_db):
    """log_production with qty=N deducts N×per_unit from tracked items and writes N log rows."""
    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO inventory (name, count_on_hand, track_inventory) VALUES ('Vase', 50, 1)"
    )
    vase_id = cursor.lastrowid

    cursor.execute("INSERT INTO products (display_name) VALUES ('Bouquet')")
    p_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type) VALUES (?, ?, ?, 'Specific')",
        (p_id, vase_id, 2),
    )
    cursor.execute(
        "INSERT INTO production_goals (product_id, qty_ordered, qty_fulfilled, due_date) VALUES (?, 10, 0, '2026-02-14')",
        (p_id,),
    )
    g_id = cursor.lastrowid
    conn.commit()
    conn.close()

    assert db_utils.log_production(g_id, qty=3) == 3

    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()
    cursor.execute("SELECT count_on_hand FROM inventory WHERE item_id = ?", (vase_id,))
    assert cursor.fetchone()[0] == 44  # 50 - (3 units × 2 per unit)
    cursor.execute("SELECT qty_fulfilled FROM production_goals WHERE goal_id = ?", (g_id,))
    assert cursor.fetchone()[0] == 3
    cursor.execute("SELECT COUNT(*) FROM production_logs WHERE goal_id = ?", (g_id,))
    assert cursor.fetchone()[0] == 3  # one row per unit — preserves unit-granular undo
    conn.close()


def test_undo_production_restores_tracked_only(mock_db):
    """Undoing production restores tracked items but leaves untracked items alone."""
    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO inventory (name, count_on_hand, track_inventory) VALUES ('Vase', 50, 1)"
    )
    vase_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO inventory (name, count_on_hand, track_inventory) VALUES ('Rose', 100, 0)"
    )
    rose_id = cursor.lastrowid

    cursor.execute("INSERT INTO products (display_name) VALUES ('Bouquet')")
    p_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type) VALUES (?, ?, ?, 'Specific')",
        (p_id, vase_id, 1),
    )
    cursor.execute(
        "INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type) VALUES (?, ?, ?, 'Specific')",
        (p_id, rose_id, 12),
    )
    cursor.execute(
        "INSERT INTO production_goals (product_id, qty_ordered, qty_fulfilled, due_date) VALUES (?, 5, 0, '2026-02-14')",
        (p_id,),
    )
    g_id = cursor.lastrowid
    conn.commit()
    conn.close()

    db_utils.log_production(g_id)  # Deducts 1 vase, not the rose
    assert db_utils.undo_production(g_id) is True

    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()
    cursor.execute("SELECT count_on_hand FROM inventory WHERE item_id = ?", (vase_id,))
    assert cursor.fetchone()[0] == 50  # tracked item restored
    cursor.execute("SELECT count_on_hand FROM inventory WHERE item_id = ?", (rose_id,))
    assert cursor.fetchone()[0] == 100  # untracked item untouched on both sides
    cursor.execute("SELECT qty_fulfilled FROM production_goals WHERE goal_id = ?", (g_id,))
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT COUNT(*) FROM production_logs WHERE goal_id = ?", (g_id,))
    assert cursor.fetchone()[0] == 0
    conn.close()


