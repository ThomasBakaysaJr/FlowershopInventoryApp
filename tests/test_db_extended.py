import sqlite3
import os
import sys
import datetime

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


# -------------------------------------------------------------------
# track_inventory behavior (introduced with the retail-refactor series)
# -------------------------------------------------------------------

def test_get_inventory_includes_untracked_items(setup_db):
    """get_inventory does not filter by track_inventory — the column is exposed raw."""
    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO inventory (name, category, count_on_hand, unit_cost, bundle_count, track_inventory) "
            "VALUES ('Untracked Stem', 'Stem', 50, 0.10, 1, 0)"
        )
        conn.commit()
    finally:
        conn.close()

    df = db_utils.get_inventory()
    names = set(df['name'].tolist())
    assert 'Untracked Stem' in names
    assert 'Red Rose' in names  # seeded, default tracked
    assert set(df['track_inventory'].astype(int).unique()) == {0, 1}


def test_export_inventory_csv_includes_untracked_and_column(setup_db):
    """CSV export carries every item (tracked or not) and the track_inventory column."""
    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE inventory SET track_inventory = 0 WHERE name = 'Red Rose'")
        conn.commit()
    finally:
        conn.close()

    csv = db_utils.export_inventory_csv()
    header = csv.splitlines()[0]
    assert 'track_inventory' in header
    assert 'Red Rose' in csv
    assert 'White Lily' in csv


def test_add_inventory_item_threads_track_flag(setup_db):
    """add_inventory_item persists the provided track_inventory value; default is tracked."""
    assert db_utils.add_inventory_item('Special Vase', 'Hardgood', None, 10, 5.00, 1, track_inventory=1)
    assert db_utils.add_inventory_item('Random Filler', 'Greenery', None, 50, 0.25, 1, track_inventory=0)
    assert db_utils.add_inventory_item('Default Item', 'Misc', None, 5, 1.00, 1)

    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, track_inventory FROM inventory WHERE name IN (?, ?, ?)",
            ('Special Vase', 'Random Filler', 'Default Item'),
        )
        got = dict(cursor.fetchall())
    finally:
        conn.close()

    assert got == {'Special Vase': 1, 'Random Filler': 0, 'Default Item': 1}


def test_update_item_details_preserves_track_when_not_passed(setup_db):
    """Calling update_item_details without the track_inventory kwarg leaves the flag alone."""
    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE inventory SET track_inventory = 0 WHERE name = 'Red Rose'")
        cursor.execute("SELECT item_id FROM inventory WHERE name = 'Red Rose'")
        rose_id = cursor.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    assert db_utils.update_item_details(rose_id, 50, 2.00, 2) is True

    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT count_on_hand, unit_cost, bundle_count, track_inventory FROM inventory WHERE item_id = ?",
            (rose_id,),
        )
        assert cursor.fetchone() == (50, 2.00, 2, 0)
    finally:
        conn.close()


def test_recipe_requirements_suppress_category_when_all_candidates_untracked(setup_db):
    """If every candidate item for a Category line is untracked, the category is excluded
    from get_recipe_requirements — modal never surfaces for flower-only recipes."""
    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        # Two untracked roses in the Rose category.
        cursor.execute(
            "INSERT INTO inventory (name, category, sub_category, count_on_hand, unit_cost, bundle_count, track_inventory) "
            "VALUES ('Pink Rose', 'Stem', 'Rose', 50, 0.5, 25, 0)"
        )
        cursor.execute(
            "INSERT INTO inventory (name, category, sub_category, count_on_hand, unit_cost, bundle_count, track_inventory) "
            "VALUES ('Ivory Rose', 'Stem', 'Rose', 40, 0.5, 25, 0)"
        )
        cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special' AND active = 1")
        p_id = cursor.fetchone()[0]
        # Category requirement that resolves only to untracked items.
        cursor.execute(
            "INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type, requirement_value) "
            "VALUES (?, NULL, 6, 'Category', 'Rose')",
            (p_id,),
        )
        conn.commit()
    finally:
        conn.close()

    reqs = db_utils.get_recipe_requirements(p_id)
    assert reqs['has_generics'] is False
    assert reqs['generic_items'] == []


def test_recipe_requirements_keep_category_when_any_candidate_tracked(setup_db):
    """If a Category line has at least one tracked candidate, it remains modal-relevant."""
    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        # Mix: two untracked roses + one tracked rose → modal should still show.
        cursor.execute(
            "INSERT INTO inventory (name, category, sub_category, count_on_hand, unit_cost, bundle_count, track_inventory) "
            "VALUES ('Pink Rose', 'Stem', 'Rose', 50, 0.5, 25, 0)"
        )
        cursor.execute(
            "INSERT INTO inventory (name, category, sub_category, count_on_hand, unit_cost, bundle_count, track_inventory) "
            "VALUES ('Premium Ecuadorian Rose', 'Stem', 'Rose', 30, 2.5, 10, 1)"
        )
        cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special' AND active = 1")
        p_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type, requirement_value) "
            "VALUES (?, NULL, 6, 'Category', 'Rose')",
            (p_id,),
        )
        conn.commit()
    finally:
        conn.close()

    reqs = db_utils.get_recipe_requirements(p_id)
    assert reqs['has_generics'] is True
    cats = [g['category'] for g in reqs['generic_items']]
    assert 'Rose' in cats

    # And the modal's candidate picker gets tracked items only.
    tracked = db_utils.get_items_by_category('Rose', tracked_only=True)
    assert len(tracked) == 1
    assert tracked.iloc[0]['name'] == 'Premium Ecuadorian Rose'

    all_candidates = db_utils.get_items_by_category('Rose', tracked_only=False)
    assert len(all_candidates) == 2


def test_forecast_generic_requirements_aggregates_category_demand(setup_db):
    """Forecaster's generic-category aggregation reflects Category recipes regardless of whether
    candidate items are tracked. Critical for the flower shop, whose flowers are untracked yet
    still need to appear on the purchasing-forecast view."""
    conn = sqlite3.connect(setup_db)
    try:
        cursor = conn.cursor()
        # An untracked rose in the catalog (category Rose)
        cursor.execute(
            "INSERT INTO inventory (name, category, sub_category, count_on_hand, unit_cost, bundle_count, track_inventory) "
            "VALUES ('Pink Rose', 'Stem', 'Rose', 50, 0.50, 25, 0)"
        )
        # Add a Category recipe line for the seeded product: "6 of any Rose"
        cursor.execute("SELECT product_id FROM products WHERE display_name = 'Valentine Special' AND active = 1")
        p_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO recipes (product_id, item_id, qty_needed, requirement_type, requirement_value) "
            "VALUES (?, NULL, 6, 'Category', 'Rose')",
            (p_id,),
        )
        conn.commit()
    finally:
        conn.close()

    # Seeded goal: qty_ordered=10, qty_fulfilled=0, due_date=2023-10-30.
    result = db_utils.get_forecast_generic_requirements(
        datetime.date(2023, 10, 1),
        datetime.date(2023, 11, 1),
    )
    assert not result.empty
    rose_rows = result[result['Category'] == 'Rose']
    assert not rose_rows.empty
    # 10 outstanding × 6 roses each = 60
    assert int(rose_rows.iloc[0]['Needed']) == 60
