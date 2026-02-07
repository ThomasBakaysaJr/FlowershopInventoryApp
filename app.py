import streamlit as st
import pandas as pd
import os
import time
import logging
from src.utils import db_utils
from src.components import designer_dashboard, admin, recipe_display


st.set_page_config(page_title="University Flowers Dashboard", layout="wide")

# --- Logging Configuration ---
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

st.title("University Flowers Production Dashboard")

if not os.path.exists(db_utils.DB_PATH):
    st.error("Database not found! Please run `python init_db.py` first.")
else:
    # Handle pending navigation changes (Fix for StreamlitAPIException)
    # We update the state BEFORE the widgets are instantiated in the new run
    if "pending_nav_main" in st.session_state:
        st.session_state.nav_main = st.session_state.pop("pending_nav_main")
    
    if "pending_nav_admin" in st.session_state:
        st.session_state.nav_admin = st.session_state.pop("pending_nav_admin")

    # Auto-navigate to Design Studio if an edit is triggered
    if "design_edit_name" in st.session_state:
        st.session_state.nav_main = "⚙️ Admin Space"
        st.session_state.nav_admin = "✏️ Design Studio"

    # Initialize navigation state
    if "nav_main" not in st.session_state:
        st.session_state.nav_main = "🎨 Designer Space"

    st.segmented_control(
        "Main Navigation",
        options=["🎨 Designer Space", "⚙️ Admin Space"],
        key="nav_main",
        label_visibility="collapsed"
    )

    if st.session_state.nav_main == "🎨 Designer Space":
        designer_dashboard.dashboard.render_designer_dashboard()

    elif st.session_state.nav_main == "⚙️ Admin Space":
        raw_inventory_df = db_utils.get_inventory()
        
        if "nav_admin" not in st.session_state:
            st.session_state.nav_admin = "📊 Stock Levels"

        st.segmented_control(
            "Admin Navigation",
            options=["📊 Stock Levels", "📖 Recipe Book", "✏️ Design Studio", "🛠️ Admin Tools"],
            key="nav_admin",
            label_visibility="collapsed"
        )
        
        if st.session_state.nav_admin == "📊 Stock Levels":
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
                    width="stretch",
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
                        logger.info(f"Inventory updated via Admin: {changes} items changed.")
                        st.toast(f"Updated {changes} items.")
                        time.sleep(0.25)
                        st.rerun()
                    else:
                        st.info("No changes detected.")
            else:
                st.info("Inventory is currently empty.")
        
        elif st.session_state.nav_admin == "📖 Recipe Book":
            recipe_display.render_recipe_display(allow_edit=True)

        elif st.session_state.nav_admin == "✏️ Design Studio":
            admin.admin_design.render_design_tab(raw_inventory_df)

        elif st.session_state.nav_admin == "🛠️ Admin Tools":
            admin.admin_tools.render_admin_tools(raw_inventory_df)