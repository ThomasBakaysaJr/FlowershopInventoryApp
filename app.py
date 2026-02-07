import streamlit as st
import pandas as pd
import os
import time
import logging
from src.utils import db_utils
from src.components import workspace_dashboard, admin, recipe_display
from src.components.workspace_dashboard import production_dashboard
from src.components.admin import admin_inventory_view, production_viewer, forecaster


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

    if st.session_state.nav_main == "🛠️ Workspace":
        if "nav_workspace" not in st.session_state:
            st.session_state.nav_workspace = "📦 Production Dashboard"

        st.segmented_control(
            "Workspace Navigation",
            options=["📦 Production Dashboard", "📅 Upcoming Work", "🖩 Calculator"],
            key="nav_workspace",
            label_visibility="collapsed"
        )

        if st.session_state.nav_workspace == "📦 Production Dashboard":
            production_dashboard.render()

        elif st.session_state.nav_workspace == "📅 Upcoming Work":
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
            admin.design_dashboard.render_design_tab(raw_inventory_df)

    elif st.session_state.nav_main == "⚙️ Admin Space":
        raw_inventory_df = db_utils.get_inventory()
        
        valid_admin = ["📊 Stock Levels", "📅 Production Viewer", "🔮 Forecaster", "📃 Inventory Management"]
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
        
        elif st.session_state.nav_admin == "📅 Production Viewer":
            production_viewer.render_production_viewer()

        elif st.session_state.nav_admin == "🔮 Forecaster":
            forecaster.render_forecaster()

        elif st.session_state.nav_admin == "📃 Inventory Management":
            admin.admin_tools.render_admin_tools(raw_inventory_df)