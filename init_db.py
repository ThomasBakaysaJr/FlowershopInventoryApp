import sqlite3

def initialize_database():
    # This creates the file 'inventory.db' in the current directory
    connection = sqlite3.connect('inventory.db')
    cursor = connection.cursor()

    # Create Inventory Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            sub_category TEXT,
            count_on_hand INTEGER DEFAULT 0,
            unit_cost REAL DEFAULT 0.00
        )
    ''')

    # Create Products Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            image_data BLOB,
            selling_price REAL DEFAULT 0.00,
            active BOOLEAN DEFAULT 1
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
            qty_made INTEGER DEFAULT 0,
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
    print("Database initialized successfully as 'inventory.db'.")

if __name__ == "__main__":
    initialize_database()