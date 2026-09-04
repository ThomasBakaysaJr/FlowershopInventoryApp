import os
import sqlite3
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import db_utils


def test_update_inventory_cost(setup_db):
    """Admin cost update writes the new value and leaves other fields unchanged."""
    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, unit_cost FROM inventory WHERE name = 'Red Rose'")
        item_id, old_cost = cursor.fetchone()
        assert old_cost == 1.00
    finally:
        conn.close()

    assert db_utils.update_inventory_cost(item_id, 1.55) is True

    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT unit_cost FROM inventory WHERE item_id = ?", (item_id,))
        assert cursor.fetchone()[0] == 1.55
    finally:
        conn.close()


def test_get_product_details_returns_correct_data(setup_db):
    """get_product_details returns price and full recipe for an active product."""
    details = db_utils.get_product_details("Valentine Special")

    assert details is not None
    assert details['price'] == 50.00
    assert len(details['recipe']) == 1
    assert details['recipe'][0]['name'] == 'Red Rose'
    assert details['recipe'][0]['qty'] == 12


def test_update_product_recipe_rename_and_price(setup_db):
    """Renaming a product and changing its price archives the old entry and creates a new one."""
    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        # Look up the item_id dynamically rather than assuming it's always 1
        cursor.execute("SELECT item_id FROM inventory WHERE name = 'Red Rose'")
        rose_id = cursor.fetchone()[0]
        details = db_utils.get_product_details("Valentine Special")
    finally:
        conn.close()

    assert db_utils.update_product_recipe(
        current_product_id=details['product_id'],
        new_name="Valentine Deluxe",
        recipe_items=[(rose_id, 6)],
        new_price=55.00,
    ) is True

    # Old name no longer active
    assert db_utils.get_product_details("Valentine Special") is None

    new_details = db_utils.get_product_details("Valentine Deluxe")
    assert new_details is not None
    assert new_details['price'] == 55.00
    assert new_details['recipe'][0]['qty'] == 6
