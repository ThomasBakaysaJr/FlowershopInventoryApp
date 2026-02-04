import streamlit as st
import pandas as pd
import os
from src.utils import db_utils
import time
import src.components.admin_design as admin_design
import src.components.designer_dashboard as designer_dashboard
import src.components.admin_tools as admin_tools
import src.components.recipe_display as recipe_display

st.set_page_config(page_title="University Flowers Dashboard", layout="wide")

st.title("University Flowers Production Dashboard")

if not os.path.exists(db_utils.DB_PATH):
    st.error("Database not found! Please run `python init_db.py` first.")
else:
    # Create tabs for different views
    tab_designer, tab_admin = st.tabs(["🎨 Designer Space", "⚙️ Admin Space"])

    with tab_designer:
        designer_dashboard.render_designer_dashboard()

    with tab_admin:
        raw_inventory_df = db_utils.get_inventory()
        admin_sub_tabs = st.tabs(["📊 Stock Levels", "🎨 Recipes & Design", "🛠️ Admin Tools"])
        
        with admin_sub_tabs[0]:
            st.header("Current Stock Levels")
            if not raw_inventory_df.empty:
                display_df = raw_inventory_df.copy()
                display_df.columns = ["ID", "Item Name", "Category", "Sub-Category", "Stock", "Cost"]
                st.dataframe(display_df, width='stretch', hide_index=True)
            else:
                st.info("Inventory is currently empty.")
        
        with admin_sub_tabs[1]:
            design_tabs = st.tabs(["📖 Current Recipes", "✏️ Design Studio"])
            with design_tabs[0]:
                recipe_display.render_recipe_display()
            with design_tabs[1]:
                admin_design.render_design_tab(raw_inventory_df)

        with admin_sub_tabs[2]:
            admin_tools.render_admin_tools(raw_inventory_df)