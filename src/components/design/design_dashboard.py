import streamlit as st
from src.utils import db_utils
from . import design_product_details

def render_design_dashboard():
    st.title("🎨 Designer Studio")
    
    # Sidebar Selection
    options_df = db_utils.get_active_product_options()
    if options_df.empty:
        st.warning("No active products found. Please seed the database or add a product.")
        return

    product_names = options_df['display_name'].tolist()
    selected_product_name = st.sidebar.selectbox("Select Product to Edit", product_names)

    if selected_product_name:
        # Fetch details for the selected specific product first
        details = db_utils.get_product_details(selected_product_name)
        
        if not details:
            st.error("Product not found.")
            return

        # Group Info
        group_id = details.get('variant_group_id')
        variants = details.get('variants', [])
        variant_map = {v['type']: v for v in variants}

        st.subheader(f"Product Family: {details['name']}")
        
        tab_std, tab_dlx, tab_prm = st.tabs(["Standard", "Deluxe", "Premium"])

        with tab_std:
            design_product_details.render_variant_tab('STD', "Standard", variant_map, group_id, details['name'], details['category'])
        with tab_dlx:
            design_product_details.render_variant_tab('DLX', "Deluxe", variant_map, group_id, details['name'], details['category'])
        with tab_prm:
            design_product_details.render_variant_tab('PRM', "Premium", variant_map, group_id, details['name'], details['category'])