import streamlit as st
from src.utils import db_utils
from . import design_product_details

def render_design_dashboard():
    st.title("🎨 Designer Studio")
    
    # Fetch active options once at the top to use for validation and display
    options_df = db_utils.get_active_product_options()
    active_names = options_df['display_name'].tolist() if not options_df.empty else []
    
    # --- State Restoration (Shadow Keys) ---
    # Restore widget state if it was lost during navigation (e.g. visiting Recipe Book)
    if "design_mode_radio" not in st.session_state and "shadow_design_mode" in st.session_state:
        st.session_state["design_mode_radio"] = st.session_state["shadow_design_mode"]
    
    # Only restore product selection if we are actually in Edit mode
    if st.session_state.get("shadow_design_mode") == "Edit Existing":
        if "design_product_select" not in st.session_state and "shadow_design_product" in st.session_state:
            if st.session_state["shadow_design_product"] in active_names:
                st.session_state["design_product_select"] = st.session_state["shadow_design_product"]

    # Handle incoming edit requests (from Recipe Book or Create New)
    # We transfer the intent into the widget state keys to persist across reruns
    if "design_edit_name" in st.session_state:
        target_product = st.session_state.pop("design_edit_name")
        
        # Safety: Only switch mode if the product is actually active/available
        if target_product in active_names:
            st.session_state["design_mode_radio"] = "Edit Existing"
            st.session_state["design_product_select"] = target_product
            # Update shadows immediately
            st.session_state["shadow_design_mode"] = "Edit Existing"
            st.session_state["shadow_design_product"] = target_product
        else:
            st.warning(f"Could not load '{target_product}' for editing. It may be archived.")

    # Mode Selection
    # We use a key so Streamlit manages the state persistence for us
    mode = st.radio("Mode", ["Create New", "Edit Existing"], horizontal=True, label_visibility="collapsed", key="design_mode_radio")
    
    st.session_state["shadow_design_mode"] = mode # Persist to shadow
    selected_product_name = None

    if mode == "Edit Existing":
        if not active_names:
            st.warning("No active products found. Please create one.")
        else:
            # Search Bar
            c_search, c_clear = st.columns([6, 1], vertical_alignment="bottom")
            with c_search:
                search_term = st.text_input("Filter Products", placeholder="Search by name...", label_visibility="collapsed", key="design_search")
            with c_clear:
                if st.button("Clear", key="clear_design_search", help="Clear Filter", width="stretch"):
                    st.session_state.design_search = ""
                    st.rerun()

            # Filter options
            filtered_names = active_names
            if search_term:
                filtered_df = db_utils.filter_dataframe_by_terms(options_df, 'display_name', search_term)
                filtered_names = filtered_df['display_name'].tolist()

            # Handle selection persistence safety: Ensure current selection is in options to avoid Streamlit error
            current_selection = st.session_state.get("design_product_select")
            
            # Logic Update: If searching and current selection doesn't match, auto-select the first result
            if search_term and current_selection and current_selection not in filtered_names:
                if filtered_names:
                    st.session_state["design_product_select"] = filtered_names[0]
                    st.session_state["shadow_design_product"] = filtered_names[0]
                elif current_selection in active_names:
                    # No matches found, keep current to avoid crash
                    filtered_names.append(current_selection)
            elif current_selection and current_selection not in filtered_names and current_selection in active_names:
                # Fallback for non-search cases (e.g. underlying data changed)
                filtered_names.append(current_selection)

            # The key 'design_product_select' will pre-select the item if set in session_state above
            selected_product_name = st.selectbox("Select Product", filtered_names, key="design_product_select")
            st.session_state["shadow_design_product"] = selected_product_name # Persist to shadow
            
            if selected_product_name:
                # Fetch details for the selected specific product first
                details = db_utils.get_product_details(selected_product_name)
                
                if not details:
                    st.error("Product not found.")
                else:
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

    elif mode == "Create New":
        # Proactive Cleanup: Ensure no recipe state lingers when entering Create Mode
        for k in list(st.session_state.keys()):
            if k.startswith("recipe_state_"):
                del st.session_state[k]

        st.subheader("✨ Create New Product Family")
        with st.form("create_product_form"):
            new_name = st.text_input("Product Name", placeholder="e.g., Summer Breeze")
            new_price = st.number_input("Selling Price ($)", min_value=0.0, step=0.5)
            new_cat = st.selectbox("Category", ["Standard", "Wedding", "Sympathy", "Event", "One-Off"])
            
            if st.form_submit_button("Create Product"):
                if not new_name:
                    st.error("Please enter a product name.")
                elif db_utils.check_product_exists(new_name):
                    st.error("A product with this name already exists.")
                else:
                    # Create the new product (Standard variant by default)
                    success = db_utils.create_new_product(
                        name=new_name,
                        selling_price=new_price,
                        image_bytes=None,
                        recipe_items=[],
                        category=new_cat,
                        variant_type="STD"
                    )
                    if success:
                        st.success(f"Created '{new_name}'!")
                        # Trigger edit mode for the new product
                        st.session_state['design_edit_name'] = new_name
                        st.rerun()
                    else:
                        st.error("Failed to create product.")
        
        st.info("Create a base product here. You can add Deluxe/Premium versions later in the editor.")