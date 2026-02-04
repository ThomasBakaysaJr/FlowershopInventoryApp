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
        st.header("This Week's Work")
        goals_df = db_utils.get_weekly_production_goals()
        
        if not goals_df.empty:
            for week in goals_df['Week Starting'].unique():
                st.subheader(f"📅 Week of {week}")
                week_data = goals_df[goals_df['Week Starting'] == week].reset_index(drop=True)
                
                # Create a grid: 2 columns on desktop, stacks on mobile
                for i in range(0, len(week_data), 2):
                    grid_cols = st.columns(2)
                    for j in range(2):
                        if i + j < len(week_data):
                            row = week_data.iloc[i + j]
                            needed = row['qty_ordered'] - row['qty_made']
                            
                            with grid_cols[j]:
                                with st.container(border=True):
                                    # Balanced ratios for better text wrapping
                                    col_btn, col_name, col_qty = st.columns([0.5, 2, 1], vertical_alignment="center", gap="small")
                                    
                                    with col_btn:
                                        btn_label = "✅" if needed <= 0 else "ADD"
                                        if st.button(btn_label, key=f"btn_{row['product_id']}_{week}", disabled=(needed <= 0), use_container_width=True):
                                            if db_utils.log_production(row['product_id']):
                                                st.toast(f"Logged 1 {row['Product']}!", icon="🌸")
                                                st.rerun()
                                    
                                    with col_name:
                                        st.markdown(f"### **{row['Product']}**" if needed > 0 else f"~~{row['Product']}~~")
                                    
                                    with col_qty:
                                        st.markdown(f"### **{needed}** left" if needed > 0 else "Done")
        else:
            st.info("No production goals set for the coming weeks.")

        st.divider()
        st.header("Recipe Reference")
        
        # Fetch recipes and group them by product for a cleaner UI
        products_df = db_utils.get_all_recipes()

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
        st.header("Current Stock Levels")
        inventory_df = db_utils.get_inventory()
        if not inventory_df.empty:
            # Renaming columns for better UI display
            inventory_df.columns = ["ID", "Item Name", "Category", "Sub-Category", "Stock", "Cost"]
            st.dataframe(inventory_df, width='stretch', hide_index=True)
        else:
            st.info("Inventory is currently empty.")