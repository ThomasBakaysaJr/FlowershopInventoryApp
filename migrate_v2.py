import sqlite3
import logging
import os

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')
logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def migrate():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    try:
        # 1. Add columns to support Generic Ingredients
        # requirement_type: 'Specific' (default) or 'Category'
        # requirement_value: The name of the category (e.g., 'Rose') if type is 'Category'
        
        logger.info("Migrating 'recipes' table...")
        cursor.execute("ALTER TABLE recipes ADD COLUMN requirement_type TEXT DEFAULT 'Specific'")
        cursor.execute("ALTER TABLE recipes ADD COLUMN requirement_value TEXT")
        
        logger.info("Migrating 'production_logs' table...")
        # Add action_type to track if a log was a MAKE (BOM deduction) or PACK (Cooler deduction)
        cursor.execute("ALTER TABLE production_logs ADD COLUMN action_type TEXT DEFAULT 'MAKE'")
        
        logger.info("Migration successful! Your database now supports generic recipes.")
        conn.commit()
    except sqlite3.OperationalError as e:
        logger.warning(f"Migration note: {e} (Columns might already exist, which is fine).")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()