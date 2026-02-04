import streamlit as st
import sqlite3
import pandas as pd
import os

st.set_page_config(page_title="University Flowers Dashboard", layout="wide")

DB_PATH = 'inventory.db'

def get_connection():
    return sqlite3.connect(DB_PATH)

st.title("University Flowers Production Dashboard")

if not os.path.exists(DB_PATH):
    st.error("Database not found! Please run `python init_db.py` first.")
else:
    conn = get_connection()

    # Create tabs for different views
    tab_tracker, tab_products, tab_admin = st.tabs(["📊 Production Tracker", "🌸 Product Catalog", "⚙️ Inventory Admin"])

    with tab_tracker:
        st.header("Today's Production Goals")
        query = """
        SELECT p.display_name as Product, pg.due_date as Due, pg.qty_ordered as Ordered, pg.qty_made as Made
        FROM production_goals pg
        JOIN products p ON pg.product_id = p.product_id
        """
        goals_df = pd.read_sql_query(query, conn)
        if not goals_df.empty:
            st.dataframe(goals_df, width='stretch', hide_index=True)
        else:
            st.info("No production goals set for today.")

    with tab_products:
        st.header("Products & Recipes")
        query = """
        SELECT p.display_name as Product, p.selling_price as Price, i.name as Ingredient, r.qty_needed as Qty
        FROM products p
        JOIN recipes r ON p.product_id = r.product_id
        JOIN inventory i ON r.item_id = i.item_id
        WHERE p.active = 1
        """
        products_df = pd.read_sql_query(query, conn)
        if not products_df.empty:
            st.dataframe(products_df, width='stretch', hide_index=True)
        else:
            st.info("No products or recipes defined.")

    with tab_admin:
        st.header("Inventory Management")
        inventory_df = pd.read_sql_query("SELECT * FROM inventory", conn)
        if not inventory_df.empty:
            # Renaming columns for better UI display
            inventory_df.columns = ["ID", "Item Name", "Category", "Sub-Category", "Stock", "Cost"]
            st.dataframe(inventory_df, width='stretch', hide_index=True)
        else:
            st.info("Inventory is currently empty.")

    conn.close()