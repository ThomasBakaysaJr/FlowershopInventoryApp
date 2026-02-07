import sqlite3

def initialize_database(db_path='inventory.db'):
    # Creates the database at the specified path (default: inventory.db)
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
            category TEXT DEFAULT 'Standard'
        )
    ''')

    # Create Recipes Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            item_id INTEGER,
            qty_needed INTEGER,
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
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(goal_id) REFERENCES production_goals(goal_id),
            FOREIGN KEY(product_id) REFERENCES products(product_id)
        )
    ''')

    connection.commit()
    connection.close()
    print(f"Database initialized successfully at '{db_path}'.")

if __name__ == "__main__":
    initialize_database()