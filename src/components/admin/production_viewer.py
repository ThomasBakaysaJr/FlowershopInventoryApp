import streamlit as st
import pandas as pd
import datetime
from src.utils import db_utils
from src.components import date_selector

@st.fragment(run_every=10)
def render_production_viewer():
    st.header("📅 Production Manager")
    
    # 1. Date Selection
    start_date, end_date = date_selector.render("prod_view")
    
    if start_date > end_date:
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

    # Search Bar
    c_search, c_clear = st.columns([6, 1], vertical_alignment="bottom")
    with c_search:
        search_term = st.text_input("Search Goals", placeholder="Filter by product name...", label_visibility="collapsed", key="prod_view_search")
    with c_clear:
        if st.button("Clear", key="clear_prod_view_search", help="Clear Search", width="stretch"):
            st.session_state.prod_view_search = ""
            st.rerun()

    # 4. Filter & Display Table
    if not goals_df.empty:
        # Filter if specific product selected
        if selected_product != "All":
            goals_df = goals_df[goals_df['Product'] == selected_product]

        # Apply Search Filter
        if search_term:
            goals_df = db_utils.filter_dataframe_by_terms(goals_df, 'Product', search_term)

        # Create a working copy to avoid SettingWithCopyWarning
        goals_df = goals_df.copy()
        
        # Indicate archived status
        if 'active' in goals_df.columns:
            goals_df['Product'] = goals_df.apply(
                lambda x: f"⚠️{x['Product']}" if x['active'] == 0 else x['Product'], 
                axis=1
            )
        
        # Interactive Goal Management Table
        with st.container(border=True):
            # Header Row
            h1, h2, h3, h4, h5 = st.columns([1, 2, 1, 1, 0.5])
            h1.markdown("**Due Date**")
            h2.markdown("**Product**")
            h3.markdown("**Progress**")
            h4.markdown("**Edit Target**")
            h5.markdown("**Del**")
            
            for _, row in goals_df.iterrows():
                c1, c2, c3, c4, c5 = st.columns([1, 2, 1, 1, 0.5], vertical_alignment="center")
                
                with c1:
                    # Handle string dates if they come back as strings from the range query
                    d_val = pd.to_datetime(row['due_date'])
                    st.write(d_val.strftime('%b %d'))
                with c2:
                    # Product Name + Badge
                    p_name = row['Product']
                    v_type = row.get('variant_type', 'STD')
                    if v_type == 'DLX':
                        st.markdown(f"{p_name} :blue[**[DLX]**]")
                    elif v_type == 'PRM':
                        st.markdown(f"{p_name} :red[**[PRM]**]")
                    else:
                        st.markdown(f"{p_name} :green[**[STD]**]")
                with c3:
                    st.write(f"{row['qty_fulfilled']} / {row['qty_ordered']}")
                
                with c4:
                    # EDIT QUANTITY Logic
                    new_val = st.number_input(
                        "Qty", 
                        min_value=1, 
                        value=int(row['qty_ordered']), 
                        label_visibility="collapsed",
                        key=f"edit_qty_{row['goal_id']}"
                    )
                    
                    if new_val != row['qty_ordered']:
                        if st.button("💾", key=f"save_qty_{row['goal_id']}", help="Save new quantity", width="stretch"):
                            result = db_utils.update_goal_quantity(row['goal_id'], new_val)
                            if result["success"]:
                                if result["overage"] > 0:
                                    st.session_state[f"overage_goal_{row['goal_id']}"] = result["overage"]
                                    st.toast(f"Updated target. {result['overage']} items are now excess.")
                                else:
                                    st.toast(f"Updated goal to {new_val}!")
                                st.rerun()
                    
                    # Check for pending overage resolution
                    overage_key = f"overage_goal_{row['goal_id']}"
                    if overage_key in st.session_state:
                        overage_amt = st.session_state[overage_key]
                        st.warning(f"⚠️ Excess: {overage_amt}")
                        if st.button(f"Move {overage_amt} to Stock", key=f"rel_{row['goal_id']}", width="stretch"):
                            db_utils.release_overage_to_stock(row['goal_id'], overage_amt)
                            del st.session_state[overage_key]
                            st.success("Moved to stock!")
                            st.rerun()
        
                with c5:
                    if st.button("❌", key=f"del_goal_{row['goal_id']}", help="Delete Goal (Returns items to Stock)", width="stretch"):
                        if db_utils.delete_production_goal(row['goal_id']):
                            st.toast("Goal deleted. Completed items returned to Cooler.")
                            st.rerun()
    else:
        st.info("No production goals found for this period.")