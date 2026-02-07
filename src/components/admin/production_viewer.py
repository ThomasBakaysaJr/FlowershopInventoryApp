import streamlit as st
import pandas as pd
import datetime
from src.utils import db_utils

def render_production_viewer():
    st.header("📅 Production Viewer")
    
    # 1. Date Controls
    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input("Start Date", value=datetime.date.today())
    with col_end:
        end_date = st.date_input("End Date", value=datetime.date.today() + datetime.timedelta(days=7))

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    # 2. Fetch Data
    # Get list of products that are either active OR have goals in this range
    product_options_df = db_utils.get_active_and_scheduled_products(start_date, end_date)
    
    # Get the actual goals
    goals_df = db_utils.get_production_goals_range(start_date, end_date)

    # 3. Dropdown Filter
    # Create a list of options: "All" + Product Names
    options = ["All"]
    if not product_options_df.empty:
        options += product_options_df['display_name'].tolist()

    selected_product = st.selectbox("Expected Production", options=options, help="Lists active recipes and archived ones with goals in the selected timeframe.")

    # 4. Filter & Display Table
    if not goals_df.empty:
        # Filter if specific product selected
        if selected_product != "All":
            goals_df = goals_df[goals_df['Product'] == selected_product]

        # Create a working copy to avoid SettingWithCopyWarning
        goals_df = goals_df.copy()
        
        # Indicate archived status
        if 'active' in goals_df.columns:
            goals_df['Product'] = goals_df.apply(
                lambda x: f"⚠️{x['Product']}" if x['active'] == 0 else x['Product'], 
                axis=1
            )
        
        # Rename columns to match request: recipe_id | recipe name | expected
        # We also keep Due Date as it is critical for a viewer
        display_df = goals_df[['product_id', 'Product', 'due_date', 'qty_ordered']].copy()
        display_df.columns = ["Recipe ID", "Recipe Name", "Due Date", "Expected"]
        
        st.dataframe(
            display_df,
            hide_index=True,
            width="stretch"
        )
    else:
        st.info("No production goals found for this period.")