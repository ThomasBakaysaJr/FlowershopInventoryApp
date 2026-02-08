import sqlite3
import logging

def migrate():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    try:
        # 1. Add columns to support Generic Ingredients
        # requirement_type: 'Specific' (default) or 'Category'
        # requirement_value: The name of the category (e.g., 'Rose') if type is 'Category'
        
        print("Migrating 'recipes' table...")
        cursor.execute("ALTER TABLE recipes ADD COLUMN requirement_type TEXT DEFAULT 'Specific'")
        cursor.execute("ALTER TABLE recipes ADD COLUMN requirement_value TEXT")
        
        print("Migration successful! Your database now supports generic recipes.")
        conn.commit()
    except sqlite3.OperationalError as e:
        print(f"Migration note: {e} (Columns might already exist, which is fine).")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()