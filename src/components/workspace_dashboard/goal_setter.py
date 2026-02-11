import streamlit as st
import datetime
from src.utils import db_utils

def render_goal_setter():
    # Only show the expander if there are actually products to schedule
    products_df = db_utils.get_active_product_options()
    
    if products_df.empty:
        return

    with st.expander("📅 Schedule New Order", expanded=False):
        with st.form("add_goal_form"):
            col_prod, col_date, col_time, col_qty = st.columns([2, 1, 0.7, 0.7])
            
            with col_prod:
                # Map names to IDs
                prod_map = dict(zip(products_df['display_name'], products_df['product_id']))
                selected_name = st.selectbox("Product", options=products_df['display_name'])
                selected_id = prod_map[selected_name]
            
            with col_date:
                # Default to tomorrow for realistic planning
                default_date = datetime.date.today() + datetime.timedelta(days=1)
                due_date = st.date_input("Due Date", value=default_date, min_value=datetime.date.today())
            
            with col_time:
                time_slot = st.selectbox("Time", options=["Any", "AM", "PM"])
            
            with col_qty:
                qty = st.number_input("Quantity", min_value=1, value=10, step=1)
            
            submitted = st.form_submit_button("Add to Schedule", type="primary", width="stretch")
            
            if submitted:
                if db_utils.add_production_goal(selected_id, str(due_date), qty, time_slot):
                    st.toast(f"Scheduled {qty}x {selected_name}!", icon="📅")
                    st.rerun()
                else:
                    st.error("Failed to add goal.")