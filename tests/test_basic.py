import sqlite3
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import db_utils


def test_clipboard_valid_comma_separated(setup_db):
    """Valid comma-separated input updates inventory."""
    text = "Red Rose, Rose, 50"
    updated, errors = db_utils.process_clipboard_update(text)

    assert "Red Rose" in updated
    assert len(errors) == 0

    conn = sqlite3.connect(setup_db)
    cursor = conn.cursor()
    cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
    assert cursor.fetchone()[0] == 50
    conn.close()


def test_clipboard_valid_whitespace_separated(setup_db):
    """Legacy whitespace-separated format updates inventory."""
    text = "Red Rose 25"
    updated, errors = db_utils.process_clipboard_update(text)

    assert "Red Rose" in updated
    assert len(errors) == 0

    conn = sqlite3.connect(setup_db)
    cursor = conn.cursor()
    cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
    assert cursor.fetchone()[0] == 25
    conn.close()


def test_clipboard_mixed_valid_and_malformed(setup_db):
    """Valid lines are processed; malformed lines are reported without aborting the batch."""
    text = "Red Rose, Rose, 75\nMalformed Line Without Numbers"
    updated, errors = db_utils.process_clipboard_update(text)

    assert "Red Rose" in updated
    assert len(errors) == 1
    assert "Invalid format" in errors[0]

    conn = sqlite3.connect(setup_db)
    cursor = conn.cursor()
    cursor.execute("SELECT count_on_hand FROM inventory WHERE name = 'Red Rose'")
    assert cursor.fetchone()[0] == 75
    conn.close()


def test_clipboard_unknown_item_is_reported(setup_db):
    """Items not in the database are reported as errors and nothing is updated."""
    updated, errors = db_utils.process_clipboard_update("Blue Orchid, 10")

    assert len(updated) == 0
    assert len(errors) == 1
    assert "Unknown: Blue Orchid" in errors[0]
