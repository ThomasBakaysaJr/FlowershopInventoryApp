import pytest
import io
import sys
import os
from PIL import Image

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.utils import process_image

def create_dummy_image(format='PNG', size=(1000, 1000), color='red'):
    """Helper to create a byte stream image."""
    img = Image.new('RGB', size, color=color)
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format=format)
    return img_byte_arr.getvalue()

def test_process_image_resize():
    """Tests that large images are resized to max dimensions."""
    large_img_bytes = create_dummy_image(size=(1000, 1000))
    
    processed_bytes = process_image(large_img_bytes, max_size=(800, 800))
    assert processed_bytes is not None
    
    with Image.open(io.BytesIO(processed_bytes)) as img:
        assert img.format == 'JPEG'
        assert img.size[0] <= 800
        assert img.size[1] <= 800

def test_process_image_invalid_input():
    """Tests that invalid input returns None gracefully."""
    assert process_image(None) is None
    assert process_image(b"not an image") is None

def test_process_image_rgba_conversion():
    """Tests that RGBA images are converted to RGB (JPEG doesn't support Alpha)."""
    # Create RGBA image
    img = Image.new('RGBA', (100, 100), color=(255, 0, 0, 128))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    
    processed_bytes = process_image(img_byte_arr.getvalue())
    assert processed_bytes is not None
    
    with Image.open(io.BytesIO(processed_bytes)) as img:
        assert img.mode == 'RGB'