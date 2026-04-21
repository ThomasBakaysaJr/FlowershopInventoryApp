import pytest
import sqlite3
import os
import io
import sys
from PIL import Image

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import db_utils, utils


@pytest.fixture
def raw_image_bytes():
    """A small in-memory PNG image, unprocessed."""
    img = Image.new('RGB', (200, 200), color='red')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def test_process_image_resizes_and_converts_to_jpeg(raw_image_bytes):
    """process_image compresses to JPEG and fits within the requested dimensions."""
    processed = utils.process_image(io.BytesIO(raw_image_bytes), max_size=(100, 100))

    assert isinstance(processed, bytes)
    img = Image.open(io.BytesIO(processed))
    assert img.format == 'JPEG'
    assert img.size[0] <= 100
    assert img.size[1] <= 100


def test_product_image_round_trips_through_db(setup_db, raw_image_bytes):
    """Images stored via create_new_product are retrievable unchanged from the database."""
    # Process the image the same way the UI does before storing
    processed_bytes = utils.process_image(io.BytesIO(raw_image_bytes))
    assert processed_bytes is not None

    # Look up a real item_id rather than assuming a fixed value
    conn = sqlite3.connect(setup_db)
    cursor = conn.cursor()
    cursor.execute("SELECT item_id FROM inventory WHERE name = 'Red Rose'")
    rose_id = cursor.fetchone()[0]
    conn.close()

    db_utils.create_new_product("Test Arrangement", 10.0, processed_bytes, [(rose_id, 1)])

    details = db_utils.get_product_details("Test Arrangement")
    assert details is not None
    assert details['image_data'] is not None
    assert bytes(details['image_data']) == processed_bytes
