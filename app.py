import streamlit as st
import pandas as pd
import os
import db_utils

st.set_page_config(page_title="University Flowers Dashboard", layout="wide")

st.title("University Flowers Production Dashboard")

if not os.path.exists(db_utils.DB_PATH):
    st.error("Database not found! Please run `python init_db.py` first.")
else:
    # Create tabs for different views
    tab_designer, tab_admin = st.tabs(["🎨 Designer Space", "⚙️ Admin Space"])

    with tab_designer:
        st.header("Weekly Production Totals")
        st.caption("Everything needed by the end of the week")
        goals_df = db_utils.get_weekly_production_goals()
        
        if not goals_df.empty:
            st.dataframe(goals_df, width='stretch', hide_index=True)
        else:
            st.info("No production goals set for the coming weeks.")

        st.divider()
        st.header("Recipe Reference")
        
        # Fetch recipes and group them by product for a cleaner UI
        conn = db_utils.get_connection()
        query = """
        SELECT p.display_name as Product, p.selling_price as Price, i.name as Ingredient, r.qty_needed as Qty
        FROM products p
        JOIN recipes r ON p.product_id = r.product_id
        JOIN inventory i ON r.item_id = i.item_id
        WHERE p.active = 1
        """
        products_df = pd.read_sql_query(query, conn)
        conn.close()

        if not products_df.empty:
            for product in products_df['Product'].unique():
                with st.expander(f"📖 {product}"):
                    recipe = products_df[products_df['Product'] == product]
                    st.write(f"**Target Price:** ${recipe['Price'].iloc[0]:.2f}")
                    for _, row in recipe.iterrows():
                        st.write(f"- {row['Qty']}x {row['Ingredient']}")
        else:
            st.info("No products or recipes defined.")

    with tab_admin:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.header("Current Stock Levels")
            inventory_df = db_utils.get_inventory()
            if not inventory_df.empty:
                # Renaming columns for better UI display
                inventory_df.columns = ["ID", "Item Name", "Category", "Sub-Category", "Stock", "Cost"]
                st.dataframe(inventory_df, width='stretch', hide_index=True)
            else:
                st.info("Inventory is currently empty.")
        
        with col2:
            st.header("Tools")
            with st.expander("📋 Clipboard Protocol", expanded=True):
                st.write("Paste inventory lists from your phone notes here to update stock.")
                st.text_area("Paste text here...", height=150, help="Format: Item Name, Quantity")
                st.button("Update Inventory")