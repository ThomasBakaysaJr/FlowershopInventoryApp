import pytest
import sqlite3
import os
import io
from PIL import Image
import sys
import pandas as pd

# Add parent directory to path to import local modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import db_utils, utils
import seed_db as seed_db

@pytest.fixture
def dummy_image_bytes():
    """Creates a small 10x10 red square image in memory."""
    img = Image.new('RGB', (10, 10), color='red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    return img_byte_arr.getvalue()

def test_process_image_utility(dummy_image_bytes):
    """Verifies that utils.process_image correctly handles resizing and format."""
    processed = utils.process_image(io.BytesIO(dummy_image_bytes), max_size=(5, 5))
    assert isinstance(processed, bytes)
    
    img = Image.open(io.BytesIO(processed))
    assert img.size == (5, 5)
    assert img.format == 'JPEG'

def test_product_image_persistence(setup_db, dummy_image_bytes):
    """Tests that images are correctly saved to and retrieved from the database."""
    db_path = setup_db
    product_name = "Test Arrangement"
    # Create a dummy inventory item for the recipe
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO inventory (name) VALUES ('Test Stem')")
    conn.commit()
    conn.close()
    
    db_utils.create_new_product(product_name, 10.0, dummy_image_bytes, [(1, 1)])
    
    # Retrieve via get_all_recipes (which is used in the UI)
    df = db_utils.get_all_recipes()
    product_row = df[df['Product'] == product_name].iloc[0]
    
    assert pd.notna(product_row['image_data'])
    assert product_row['image_data'] == dummy_image_bytes

def test_load_image_search_logic(monkeypatch):
    """Tests that seed_db.load_image correctly tries different filename variations."""
    searched_paths = []
    def mock_exists(path):
        searched_paths.append(path)
        return "spring mix.jpeg" in path

    monkeypatch.setattr(os.path, "exists", mock_exists)
    monkeypatch.setattr(utils, "process_image", lambda x: b"fake_image_data")
    
    result = seed_db.load_image("Spring Mix")
    assert result == b"fake_image_data"
    assert any("spring mix.jpeg" in p for p in searched_paths)

def test_load_image_returns_none_on_failure(monkeypatch):
    """Verifies that load_image returns None if no file matches, ensuring UI safety."""
    # Mock os.path.exists to always return False so no image is ever found
    monkeypatch.setattr(os.path, "exists", lambda path: False)
    
    # Attempt to load an image that doesn't exist
    result = seed_db.load_image("Invisible Rose")
    
    # Assert we get None back (which translates to NULL in DB and is handled safely by UI)
    assert result is None