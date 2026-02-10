import streamlit as st
import pandas as pd
import os
import time
import logging
from src.utils import db_utils
from src.components import workspace_dashboard, admin, recipe_display, design
from src.components.workspace_dashboard import production_dashboard
from src.components.admin import admin_inventory_view, production_viewer, forecaster, admin_settings


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

    if "pending_nav_design" in st.session_state:
        st.session_state.nav_design = st.session_state.pop("pending_nav_design")

    # Auto-navigate to Design Studio if an edit is triggered
    if "design_edit_name" in st.session_state:
        st.session_state.nav_main = "🎨 Designer Space"
        st.session_state.nav_design = "✏️ Design Studio"

    # Initialize navigation state
    if "nav_main" not in st.session_state:
        st.session_state.nav_main = "🛠️ Workspace"

    st.segmented_control(
        "Main Navigation",
        options=["🛠️ Workspace", "🎨 Designer Space", "⚙️ Admin Space"],
        key="nav_main",
        label_visibility="collapsed"
    )

    # --- State Cleanup ---
    # Reset recipe editor state if we are not in the Design Studio
    # This ensures that navigating away (e.g. to Recipe Book) clears unsaved edits.
    is_in_design_studio = (st.session_state.nav_main == "🎨 Designer Space" and st.session_state.get("nav_design") == "✏️ Design Studio")
    
    if not is_in_design_studio:
        # Use list() to create a copy of keys to avoid runtime errors during deletion
        for k in list(st.session_state.keys()):
            if k.startswith("recipe_state_"):
                del st.session_state[k]
            
    # Reset Designer Studio selection shadows if we leave the Designer Space entirely OR switch to Recipe Book
    # This ensures that returning to the Design Studio manually defaults to 'Create New'
    if st.session_state.nav_main != "🎨 Designer Space" or st.session_state.get("nav_design") == "📖 Recipe Book":
        for k in ["shadow_design_mode", "shadow_design_product", "design_mode_radio", "design_product_select", "design_search"]:
            if k in st.session_state:
                del st.session_state[k]

    if st.session_state.nav_main == "🛠️ Workspace":
        if "nav_workspace" not in st.session_state:
            st.session_state.nav_workspace = "📦 Production Dashboard"

        st.segmented_control(
            "Workspace Navigation",
            options=["📦 Production Dashboard", "📅 Upcoming Orders", "🖩 Calculator"],
            key="nav_workspace",
            label_visibility="collapsed"
        )

        if st.session_state.nav_workspace == "📦 Production Dashboard":
            production_dashboard.render()

        elif st.session_state.nav_workspace == "📅 Upcoming Orders":
            workspace_dashboard.dashboard.render_designer_dashboard()
            
        elif st.session_state.nav_workspace == "🖩 Calculator":
            pass

    elif st.session_state.nav_main == "🎨 Designer Space":
        raw_inventory_df = db_utils.get_inventory()
        
        if "nav_design" not in st.session_state:
            st.session_state.nav_design = "📖 Recipe Book"

        st.segmented_control(
            "Design Navigation",
            options=["📖 Recipe Book", "✏️ Design Studio"],
            key="nav_design",
            label_visibility="collapsed"
        )
        
        if st.session_state.nav_design == "📖 Recipe Book":
            recipe_display.render_recipe_display(allow_edit=True)

        elif st.session_state.nav_design == "✏️ Design Studio":
            design.design_dashboard.render_design_dashboard()

    elif st.session_state.nav_main == "⚙️ Admin Space":
        raw_inventory_df = db_utils.get_inventory()
        
        valid_admin = ["📊 Stock Levels", "📅 Production Manager", "🔮 Forecaster", "📋 EOD Inventory Count", "📦 Bulk Operations", "⚙️ Settings"]
        if "nav_admin" not in st.session_state or st.session_state.nav_admin not in valid_admin:
            st.session_state.nav_admin = "📊 Stock Levels"

        st.segmented_control(
            "Admin Navigation",
            options=valid_admin,
            key="nav_admin",
            label_visibility="collapsed"
        )
        
        if st.session_state.nav_admin == "📊 Stock Levels":
            admin_inventory_view.render_stock_levels(raw_inventory_df)
        
        elif st.session_state.nav_admin == "📅 Production Manager":
            production_viewer.render_production_viewer()

        elif st.session_state.nav_admin == "🔮 Forecaster":
            forecaster.render_forecaster()

        elif st.session_state.nav_admin == "📋 EOD Inventory Count":
            admin.admin_tools.render_eod_tools(raw_inventory_df)
            
        elif st.session_state.nav_admin == "📦 Bulk Operations":
            admin.admin_tools.render_bulk_operations(raw_inventory_df)
            
        elif st.session_state.nav_admin == "⚙️ Settings":
            admin_settings.render_settings_panel()