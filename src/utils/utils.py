import io
import logging
from typing import Optional, Tuple, Union

import pandas as pd
from PIL import Image

from src.utils.constants import time_slot_rank

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
        logger.error(f"process_image: Error processing image: {e}")
        return None


def safe_date_string(d, fmt: str = "%Y-%m-%d") -> str:
    """Coerces a date/datetime/str to an ISO-style string for SQL parameters."""
    return d.strftime(fmt) if hasattr(d, "strftime") else str(d)


def normalize_time_slots(df: pd.DataFrame, col: str = "time_slot", rank_col: str = "time_rank") -> pd.DataFrame:
    """Normalizes a time-slot column (fillna, uppercase, trim) and adds a sort-rank column.

    Mutates the passed DataFrame in place (to match the existing call-site style)
    and returns it for chaining.
    """
    if col in df.columns:
        df[col] = df[col].fillna("Any").astype(str).str.strip().str.upper()
        df[rank_col] = df[col].map(time_slot_rank)
    return df