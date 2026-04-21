import pytest
import sqlite3
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import db_utils


def test_check_product_exists(setup_db):
    """Existence check is case-insensitive and correctly identifies missing products."""
    assert db_utils.check_product_exists("Valentine Special") is True
    assert db_utils.check_product_exists("valentine special") is True
    assert db_utils.check_product_exists("Non Existent") is False


def test_delete_product_soft_deletes_and_preserves_history(setup_db):
    """Deleting a product marks it inactive but keeps its recipe and goals."""
    conn = sqlite3.connect(setup_db)
    cursor = conn.cursor()
    cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special'")
    p_id = cursor.fetchone()[0]
    conn.close()

    assert db_utils.delete_product(p_id) is True

    conn = sqlite3.connect(setup_db)
    cursor = conn.cursor()

    cursor.execute("SELECT active FROM products WHERE display_name = 'Valentine Special'")
    assert cursor.fetchone()[0] == 0

    cursor.execute("SELECT 1 FROM recipes WHERE product_id = ?", (p_id,))
    assert cursor.fetchone() is not None

    cursor.execute("SELECT 1 FROM production_goals WHERE product_id = ?", (p_id,))
    assert cursor.fetchone() is not None
    conn.close()


def test_update_product_recipe_changes_price_and_ingredients(setup_db):
    """Updating a recipe archives the old product and creates a new one with updated data."""
    conn = sqlite3.connect(setup_db)
    cursor = conn.cursor()
    cursor.execute("SELECT item_id FROM inventory WHERE name = 'White Lily'")
    lily_id = cursor.fetchone()[0]
    cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special' AND active = 1")
    p_id = cursor.fetchone()[0]
    conn.close()

    assert db_utils.update_product_recipe(p_id, "Valentine Special", [(lily_id, 5)], new_price=60.00) is True

    conn = sqlite3.connect(setup_db)
    cursor = conn.cursor()

    cursor.execute("SELECT product_id, selling_price FROM products WHERE display_name = 'Valentine Special' AND active = 1")
    row = cursor.fetchone()
    new_p_id, new_price = row
    assert new_price == 60.00
    assert new_p_id != p_id  # immutable update — new row created

    cursor.execute("SELECT item_id, qty_needed FROM recipes WHERE product_id = ?", (new_p_id,))
    assert cursor.fetchall() == [(lily_id, 5)]

    cursor.execute("SELECT active FROM products WHERE product_id = ?", (p_id,))
    assert cursor.fetchone()[0] == 0  # old version archived
    conn.close()


def test_update_product_recipe_goals_stay_without_migration(setup_db):
    """Goals are not migrated by default when a recipe is updated."""
    conn = sqlite3.connect(setup_db)
    cursor = conn.cursor()
    cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special' AND active = 1")
    p_id = cursor.fetchone()[0]
    conn.close()

    db_utils.update_product_recipe(p_id, "Valentine Special", [], migrate_goals=False)

    conn = sqlite3.connect(setup_db)
    cursor = conn.cursor()
    cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special' AND active = 1")
    new_p_id = cursor.fetchone()[0]

    # Goal remains attached to the old (now archived) product_id
    cursor.execute("SELECT COUNT(*) FROM production_goals WHERE product_id = ?", (new_p_id,))
    assert cursor.fetchone()[0] == 0

    cursor.execute("SELECT COUNT(*) FROM production_goals WHERE product_id = ?", (p_id,))
    assert cursor.fetchone()[0] == 1
    conn.close()


def test_update_product_recipe_migrates_unfulfilled_goals(setup_db):
    """With migrate_goals=True, unfulfilled goals are moved to the new product_id."""
    conn = sqlite3.connect(setup_db)
    cursor = conn.cursor()
    cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special' AND active = 1")
    p_id = cursor.fetchone()[0]
    conn.close()

    db_utils.update_product_recipe(p_id, "Valentine Special", [], migrate_goals=True)

    conn = sqlite3.connect(setup_db)
    cursor = conn.cursor()
    cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special' AND active = 1")
    new_p_id = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM production_goals WHERE product_id = ?", (new_p_id,))
    assert cursor.fetchone()[0] == 1  # seeded goal migrated

    cursor.execute("SELECT COUNT(*) FROM production_goals WHERE product_id = ?", (p_id,))
    assert cursor.fetchone()[0] == 0  # old product_id has no goals left
    conn.close()
