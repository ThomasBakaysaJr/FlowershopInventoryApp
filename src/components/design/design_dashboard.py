import streamlit as st
import pandas as pd
from src.utils import db_utils, utils
from src.components import design

def render_design_tab(inventory_df):
    st.header("🌸 New Arrangement Designer")
    st.caption("Build new products by selecting items from your inventory.")
    
    if st.button("⚠️ Reset Form", help="Clear all fields and start over", type="secondary", width="stretch"):
        st.session_state.should_clear_input = True
        st.rerun()

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
        st.session_state.prod_note_input = ""
        
        # Reset Product Type and Goal inputs
        st.session_state.prod_type_input = "Standard"
        st.session_state.create_goal_input = True
        st.session_state.pop('goal_date_input', None)
        st.session_state.pop('goal_qty_input', None)
        
        # Clear residual state
        st.session_state.uploader_key += 1
        st.session_state.last_suggested_price = 0.0
        st.session_state.confirm_overwrite = False
        st.session_state.should_clear_input = False
        st.session_state.last_loaded_prod_name = ""

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
            
            # 1b. Set Note Input
            st.session_state['prod_note_input'] = details.get('note', "")
            
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
                    'cost': cost,
                    'type': ing.get('type', 'Specific'),
                    'val': ing.get('val'),
                    'note': ing.get('note')
                })
            
            # Track that we are editing this specific product
            st.session_state['editing_product_original_name'] = details['name']
            st.session_state['editing_product_id'] = details['product_id']
            st.session_state['last_loaded_prod_name'] = details['name']
            st.toast(f"Loaded '{details['name']}' for editing.", icon="✏️")
        else:
            st.error(f"Could not load details for {target_name}")

    # --- INPUT SECTION ---
    col_details, col_builder = st.columns([1, 1.5], gap="large")

    # 1. Render Product Details (Left Column)
    uploaded_file, save_clicked, prod_type, goal_date, goal_qty, prod_note = design.design_product_details.render(col_details, inventory_df)
    
    # 2. Render Recipe Builder (Right Column)
    design.design_recipe_builder.render(col_builder, inventory_df)

    # 3. Handle Save Logic
    with col_details:
        if save_clicked:
            prod_name = st.session_state.get("prod_name_input", "")
            final_price = st.session_state.get("final_price_input", 0.0)
            recipe_items = st.session_state.new_recipe
            rollover_stock = st.session_state.get("rollover_stock_input", True)
            migrate_goals = st.session_state.get("migrate_goals_input", True)
            
            design.design_save_logic.handle_save_click(prod_name, final_price, uploaded_file, recipe_items, rollover_stock, prod_type, migrate_goals, goal_date, goal_qty, prod_note)

        # 4. Confirmation Dialog for Overwrite
        design.design_save_logic.render_overwrite_dialog(
            st.session_state.get("prod_name_input", ""),
            st.session_state.get("final_price_input", 0.0),
            uploaded_file,
            st.session_state.new_recipe,
            st.session_state.get("rollover_stock_input", True),
            prod_type,
            st.session_state.get("migrate_goals_input", True),
            goal_date,
            goal_qty,
            prod_note
        )