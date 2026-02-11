import os
from PIL import Image, ImageOps

# =================CONFIGURATION=================
# CHANGE THIS to the folder where your big images are
SOURCE_DIR = 'images/test' 

# CHANGE THIS to where you want the small ones to go
DEST_DIR = 'images/recipes'      

# Target size (Width, Height)
TARGET_SIZE = (400, 400)

# If True, adds white bars to make image exactly 400x400. 
# If False, just shrinks it so the longest side is 400.
MAKE_SQUARE = False 
# ===============================================

def resize_images():
    # Create destination directory if it doesn't exist
    if not os.path.exists(DEST_DIR):
        os.makedirs(DEST_DIR)
        print(f"Created directory: {DEST_DIR}")

    # Get list of images
    try:
        files = [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
    except FileNotFoundError:
        print(f"❌ Error: Source directory '{SOURCE_DIR}' not found.")
        return

    print(f"Found {len(files)} images. Starting resize...")

    count = 0
    for filename in files:
        src_path = os.path.join(SOURCE_DIR, filename)
        dest_path = os.path.join(DEST_DIR, filename)

        try:
            with Image.open(src_path) as img:
                # Convert to RGB (fixes issues with transparent PNGs saving as JPEGs)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')

                # Resize logic: Contain within TARGET_SIZE while keeping aspect ratio
                img.thumbnail(TARGET_SIZE, Image.Resampling.LANCZOS)

                # Optional: Paste onto a white square background
                if MAKE_SQUARE:
                    new_img = Image.new("RGB", TARGET_SIZE, (255, 255, 255))
                    # Center the resized image
                    offset = ((TARGET_SIZE[0] - img.size[0]) // 2, (TARGET_SIZE[1] - img.size[1]) // 2)
                    new_img.paste(img, offset)
                    img = new_img

                # Save optimized JPEG
                img.save(dest_path, "JPEG", quality=85, optimize=True)
                count += 1
                
        except Exception as e:
            print(f"⚠️ Could not process {filename}: {e}")

    print(f"✅ Success! Resized {count} images to {DEST_DIR}")

if __name__ == "__main__":
    resize_images()