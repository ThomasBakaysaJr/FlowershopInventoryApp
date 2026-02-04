import sqlite3
import pandas as pd
import os

DB_PATH = 'inventory.db'

def get_connection():
    return sqlite3.connect(DB_PATH)

def get_weekly_production_goals():
    """Groups production goals by the start of the week for easier planning."""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    
    conn = get_connection()
    query = """
    SELECT p.display_name as Product, pg.due_date as Due, pg.qty_ordered, pg.qty_made
    FROM production_goals pg
    JOIN products p ON pg.product_id = p.product_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        return df

    # Convert to datetime and group by week (starting Monday)
    df['Due'] = pd.to_datetime(df['Due'])
    df['Week Starting'] = df['Due'].dt.to_period('W').apply(lambda r: r.start_time.strftime('%b %d, %Y'))
    
    summary = df.groupby(['Week Starting', 'Product']).agg({
        'qty_ordered': 'sum',
        'qty_made': 'sum'
    }).reset_index()
    
    return summary

def get_inventory():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM inventory", conn)
    conn.close()
    return df

def log_production(product_name):
    """Increments production count and deducts inventory (BOM)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Get product_id
        cursor.execute("SELECT product_id FROM products WHERE display_name = ?", (product_name,))
        res = cursor.fetchone()
        if not res: return False
        p_id = res[0]

        # 2. Find earliest incomplete goal for this product
        cursor.execute("""
            SELECT goal_id FROM production_goals 
            WHERE product_id = ? AND qty_made < qty_ordered 
            ORDER BY due_date ASC LIMIT 1
        """, (p_id,))
        goal_res = cursor.fetchone()
        
        if goal_res:
            g_id = goal_res[0]
            cursor.execute("UPDATE production_goals SET qty_made = qty_made + 1 WHERE goal_id = ?", (g_id,))
            
            # 3. Deduct Inventory (Bill of Materials)
            cursor.execute("SELECT item_id, qty_needed FROM recipes WHERE product_id = ?", (p_id,))
            for i_id, qty in cursor.fetchall():
                cursor.execute("UPDATE inventory SET count_on_hand = count_on_hand - ? WHERE item_id = ?", (qty, i_id))
            
            conn.commit()
            return True
        return False
    finally:
        conn.close()

def get_all_recipes():
    """Fetches all active product recipes with ingredient details."""
    conn = get_connection()
    query = """
    SELECT p.display_name as Product, p.selling_price as Price, i.name as Ingredient, r.qty_needed as Qty
    FROM products p
    JOIN recipes r ON p.product_id = r.product_id
    JOIN inventory i ON r.item_id = i.item_id
    WHERE p.active = 1
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df
