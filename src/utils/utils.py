import io
import logging
from typing import Optional, Tuple, Union
from PIL import Image

logger = logging.getLogger(__name__)

def process_image(
    image_input: Union[str, io.BytesIO, bytes], 
    max_size: Tuple[int, int] = (800, 800), 
    quality: int = 85
) -> Optional[bytes]:
    """Resizes and compresses an image to JPEG bytes for database storage."""
    if not image_input:
        return None
    try:
        if isinstance(image_input, bytes):
            image_input = io.BytesIO(image_input)

        # Ensure we are at the start of the stream if it's a file-like object
        if hasattr(image_input, 'seek'):
            image_input.seek(0)

        with Image.open(image_input) as image:
            # Convert to RGB if RGBA (png) or Palette to ensure JPEG compatibility
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            
            # Resize to max dimensions while maintaining aspect ratio
            image.thumbnail(max_size)
            
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG', quality=quality)
            return img_byte_arr.getvalue()
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        return None