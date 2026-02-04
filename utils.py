from PIL import Image
import io

def process_image(image_input, max_size=(800, 800), quality=85):
    """Resizes and compresses an image to JPEG bytes for database storage."""
    if not image_input:
        return None
    try:
        image = Image.open(image_input)
        # Convert to RGB if RGBA (png) to ensure JPEG compatibility
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        # Resize to max dimensions while maintaining aspect ratio
        image.thumbnail(max_size)
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG', quality=quality)
        return img_byte_arr.getvalue()
    except Exception as e:
        print(f"Error processing image: {e}")
        return None