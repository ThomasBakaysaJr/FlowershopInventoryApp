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