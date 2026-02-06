import streamlit as st
import pandas as pd
from src.utils import db_utils, utils
from src.components import design_product_details
from src.components import design_recipe_builder

def render_design_tab(inventory_df):
    st.header("🌸 New Arrangement Designer")
    st.caption("Build new products by selecting items from your inventory.")

    # Initialize uploader key if not present (Fix for sticky images)
    if 'uploader_key' not in st.session_state:
        st.session_state.uploader_key = 0

    # Initialize confirm_overwrite if not present
    if 'confirm_overwrite' not in st.session_state:
        st.session_state.confirm_overwrite = False

    # --- CLEAR INPUT TRIGGER ---
    if st.session_state.get('should_clear_input'):
        st.session_state.prod_name_input = ""
        st.session_state.final_price_input = 0.0
        st.session_state.pop('editing_product_original_name', None)
        st.session_state.pop('editing_product_id', None)
        st.session_state.new_recipe = []
        
        # Clear residual state
        st.session_state.uploader_key += 1
        st.session_state.last_suggested_price = 0.0
        st.session_state.confirm_overwrite = False
        st.session_state.should_clear_input = False

    # Initialize session state for the recipe being built
    if 'new_recipe' not in st.session_state:
        st.session_state.new_recipe = [] # List of {'id': int, 'name': str, 'qty': int, 'cost': float}

    # --- PRE-LOAD LOGIC (From Recipe Display Edit) ---
    if 'design_edit_name' in st.session_state:
        target_name = st.session_state.pop('design_edit_name')
        # Clear legacy keys if they exist
        st.session_state.pop('design_edit_price', None)
        st.session_state.pop('design_edit_ingredients', None)
        
        # Fetch fresh details from DB
        details = db_utils.get_product_details(target_name)
        
        if details:
            # 1. Set Name Input
            st.session_state['prod_name_input'] = details['name']
            
            # 2. Set Price Input & Prevent auto-overwrite
            st.session_state['final_price_input'] = float(details['price'])
            st.session_state.last_suggested_price = float(details['price'])
            
            # 3. Rebuild Recipe List
            st.session_state.new_recipe = []
            for ing in details['recipe']:
                # Find cost from inventory_df
                cost = 0.0
                match = inventory_df[inventory_df['item_id'] == ing['item_id']]
                if not match.empty:
                    cost = match.iloc[0]['unit_cost']
                
                st.session_state.new_recipe.append({
                    'id': ing['item_id'],
                    'name': ing['name'],
                    'qty': ing['qty'],
                    'cost': cost
                })
            
            # Track that we are editing this specific product
            st.session_state['editing_product_original_name'] = details['name']
            st.session_state['editing_product_id'] = details['product_id']
            st.toast(f"Loaded '{details['name']}' for editing.", icon="✏️")
        else:
            st.error(f"Could not load details for {target_name}")

    # --- INPUT SECTION ---
    col_details, col_builder = st.columns([1, 1.5], gap="large")

    # 1. Render Product Details (Left Column)
    uploaded_file, save_clicked = design_product_details.render(col_details)
    
    # 2. Render Recipe Builder (Right Column)
    design_recipe_builder.render(col_builder, inventory_df)

    # 3. Handle Save Logic
    with col_details:
        if save_clicked:
            prod_name = st.session_state.get("prod_name_input", "")
            final_price = st.session_state.get("final_price_input", 0.0)
            
            if prod_name and st.session_state.new_recipe:
                original_name = st.session_state.get('editing_product_original_name')
                
                # 1. Check for Collision (Safeguard)
                collision = False
                if original_name:
                    # Edit Mode: Collision only if renaming to an existing product
                    if prod_name.lower() != original_name.lower() and db_utils.check_product_exists(prod_name):
                        collision = True
                else:
                    # Create Mode: Collision if product exists
                    if db_utils.check_product_exists(prod_name):
                        collision = True
                
                # 2. Process Inputs (Common)
                img_bytes = None
                if uploaded_file:
                    img_bytes = utils.process_image(uploaded_file)
                
                db_items = [(int(x['id']), int(x['qty'])) for x in st.session_state.new_recipe]

                # 3. Execute Update or Create
                original_id = st.session_state.get('editing_product_id')
                # Update: Must trigger overwrite safeguard if product already exists
                if original_id or collision:
                    st.session_state.confirm_overwrite = True
                    st.rerun()
                else:
                    if db_utils.create_new_product(prod_name, final_price, img_bytes, db_items):
                        st.success(f"Successfully created '{prod_name}'!")
                        st.session_state.should_clear_input = True
                        st.rerun()
                    else:
                        st.error("Failed to save product. Check database connection.")
            else:
                st.warning("Please provide a name and at least one ingredient.")

        # 4. Confirmation Dialog for Overwrite
        if st.session_state.get('confirm_overwrite'):
            prod_name = st.session_state.get("prod_name_input", "")
            final_price = st.session_state.get("final_price_input", 0.0)
            
            st.warning(f"Product '{prod_name}' already exists. Overwrite?")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("Yes, Overwrite"):
                    img_bytes = None
                    if uploaded_file:
                        img_bytes = utils.process_image(uploaded_file)
                        if img_bytes is None:
                            st.error("Error processing image. Please check the file format.")
                            st.stop()
                    
                    # Prepare list for DB: [(id, qty), ...]
                    db_items = [(int(x['id']), int(x['qty'])) for x in st.session_state.new_recipe]
                    
                    # We only reach here via the "Yes, Overwrite" button.
                    # If we are in Edit Mode, we have an ID. If Create Mode (overwrite self), we need to find the ID of the thing we are overwriting.
                    
                    target_id = st.session_state.get('editing_product_id')
                    
                    # If we don't have an editing ID (Create Mode), we need to fetch the ID of the existing product we are overwriting
                    if not target_id:
                        # Fetch ID of the product we are about to overwrite
                        details = db_utils.get_product_details(prod_name)
                        if details:
                            target_id = details['product_id']
                    
                    if target_id and db_utils.update_product_recipe(target_id, prod_name, db_items, img_bytes, final_price):
                        st.success(f"Updated '{prod_name}'!")
                        st.session_state.confirm_overwrite = False
                        st.session_state.should_clear_input = True
                        st.rerun()
            with col_no:
                if st.button("Cancel"):
                    st.session_state.confirm_overwrite = False
                    st.rerun()