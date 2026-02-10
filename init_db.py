import sqlite3
import logging
import os
import sys

# Configure logging to match GEMINI.md standards
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def initialize_database(db_path='inventory.db', reset=False):
    """Creates the database schema using the Safe Pattern."""
    if reset and os.path.exists(db_path):
        try:
            os.remove(db_path)
            logger.info(f"Deleted existing database at '{db_path}'")
            print(f"🗑️  Deleted existing database: {db_path}")
        except OSError as e:
            logger.error(f"Error deleting database: {e}")
            print(f"❌ Error deleting database: {e}")
            return

    connection = None
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()

        # Create Inventory Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                sub_category TEXT,
                count_on_hand INTEGER DEFAULT 0,
                unit_cost REAL DEFAULT 0.00,
                bundle_count INTEGER DEFAULT 1
            )
        ''')

        # Create Products Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                image_data BLOB,
                selling_price REAL DEFAULT 0.00,
                active BOOLEAN DEFAULT 1,
                stock_on_hand INTEGER DEFAULT 0,
                category TEXT DEFAULT 'Standard',
                note TEXT,
                variant_group_id TEXT,
                variant_type TEXT DEFAULT 'STD'
            )
        ''')

        # Create Recipes Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                item_id INTEGER,
                qty_needed INTEGER,
                requirement_type TEXT DEFAULT 'Specific',
                requirement_value TEXT,
                note TEXT,
                FOREIGN KEY(product_id) REFERENCES products(product_id),
                FOREIGN KEY(item_id) REFERENCES inventory(item_id)
            )
        ''')

        # Create Production Goals Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS production_goals (
                goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                due_date DATE,
                qty_ordered INTEGER DEFAULT 0,
                qty_fulfilled INTEGER DEFAULT 0,
                FOREIGN KEY(product_id) REFERENCES products(product_id)
            )
        ''')

        # Create Production Logs Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS production_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER,
                product_id INTEGER,
                action_type TEXT DEFAULT 'MAKE',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(goal_id) REFERENCES production_goals(goal_id),
                FOREIGN KEY(product_id) REFERENCES products(product_id)
            )
        ''')

        connection.commit()
        logger.info(f"Database initialized successfully at '{db_path}'.")
    except sqlite3.Error as e:
        logger.error(f"init_db: Database error: {e}")
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    reset_db = "--reset" in sys.argv
    initialize_database(reset=reset_db)