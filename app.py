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
                edited_df = st.data_editor(
                    raw_inventory_df,
                    column_config={
                        "item_id": st.column_config.NumberColumn("ID", disabled=True),
                        "name": st.column_config.TextColumn("Item Name", disabled=True),
                        "category": st.column_config.TextColumn("Category", disabled=True),
                        "sub_category": st.column_config.TextColumn("Sub-Category", disabled=True),
                        "count_on_hand": st.column_config.NumberColumn("Stock", disabled=True),
                        "unit_cost": st.column_config.NumberColumn("Cost ($)", min_value=0.0, step=0.01, format="$%.2f", required=True)
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="inventory_editor"
                )

                if st.button("💾 Save Changes", key="save_inventory_changes"):
                    changes = 0
                    for index, row in edited_df.iterrows():
                        original = raw_inventory_df[raw_inventory_df['item_id'] == row['item_id']]
                        if not original.empty:
                            old_cost = original.iloc[0]['unit_cost']
                            new_cost = row['unit_cost']
                            if abs(new_cost - old_cost) > 0.001:
                                db_utils.update_inventory_cost(row['item_id'], new_cost)
                                changes += 1
                    
                    if changes > 0:
                        st.success(f"Updated {changes} items.")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.info("No changes detected.")
            else:
                st.info("Inventory is currently empty.")
        
        with admin_sub_tabs[1]:
            design_tabs = st.tabs(["📖 Current Recipes", "✏️ Design Studio"])
            with design_tabs[0]:
                recipe_display.render_recipe_display(allow_edit=True)
            with design_tabs[1]:
                admin_design.render_design_tab(raw_inventory_df)

        with admin_sub_tabs[2]:
            admin_tools.render_admin_tools(raw_inventory_df)