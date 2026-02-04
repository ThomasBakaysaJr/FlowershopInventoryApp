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