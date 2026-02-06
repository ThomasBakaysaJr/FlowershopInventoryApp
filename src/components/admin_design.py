import streamlit as st
import pandas as pd
from src.utils import db_utils, utils

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

    with col_details:
        st.subheader("1. Product Details")
        prod_name = st.text_input("Product Name", placeholder="e.g., Summer Breeze", key="prod_name_input")
        
        # Show existing image if it exists so user knows they don't need to re-upload
        if prod_name:
            current_img = db_utils.get_product_image(prod_name)
            if current_img:
                st.image(current_img, caption="Current Image (Will be kept if no new upload)", width=150)

        uploaded_file = st.file_uploader("Upload Thumbnail", type=['png', 'jpg', 'jpeg'], key=f"uploader_{st.session_state.uploader_key}")
        
        st.divider()
        
        # --- COSTING FORMULA (HIGHLIGHTED FOR ADJUSTMENT) ---
        st.subheader("3. Pricing")
        
        # >>> FORMULA VARIABLES <<<
        LABOR_RATE = 0.20  # 20% of COGS
        MARKUP = 3.5       # 3.5x Markup on Total Cost
        # >>> END FORMULA <<<

        # Calculate Costs
        cogs = sum(item['cost'] * item['qty'] for item in st.session_state.new_recipe)
        labor_cost = cogs * LABOR_RATE
        total_cost = cogs + labor_cost
        suggested_price = total_cost * MARKUP

        # Auto-update input when recipe changes
        if 'last_suggested_price' not in st.session_state:
            st.session_state.last_suggested_price = 0.0
            
        if abs(suggested_price - st.session_state.last_suggested_price) > 0.001:
            st.session_state.final_price_input = float(f"{suggested_price:.2f}")
            st.session_state.last_suggested_price = suggested_price

        st.markdown(f"**Cost of Goods (COGS):** `${cogs:.2f}`")
        st.markdown(f"**Labor ({int(LABOR_RATE*100)}%):** `${labor_cost:.2f}`")
        st.markdown(f"**Total Cost:** `${total_cost:.2f}`")
        
        st.markdown(f"### **Formula Suggested:** `${suggested_price:.2f}`")
        st.caption(f"(Based on {MARKUP}x markup)")
        
        final_price = st.number_input("Final Selling Price ($)", min_value=0.0, step=1.0, key="final_price_input")

        if st.button("💾 Save / Update Product", type="primary", width="stretch"):
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
                
                # testing: shouldn't be needed, overwrite should be triggered
                # elsewhere  
                # if collision:
                #     st.session_state.confirm_overwrite = True
                #     st.rerun()

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

        # Confirmation Dialog for Overwrite
        if st.session_state.get('confirm_overwrite'):
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

    with col_builder:
        st.subheader("2. Build Recipe")
        
        if not inventory_df.empty:
            # Filter by Category
            categories = ["All"] + sorted(list(inventory_df['category'].dropna().unique()))
            selected_cat = st.selectbox("Filter Category", categories)
            
            # Filter Items
            if selected_cat != "All":
                filtered_items = inventory_df[inventory_df['category'] == selected_cat]
            else:
                filtered_items = inventory_df
            
            # Create lookup: ID -> Row Data
            id_to_item = {row['item_id']: row for _, row in filtered_items.iterrows()}
            
            def format_item_label(item_id):
                item = id_to_item[item_id]
                return f"{item['name']} (${item['unit_cost']:.2f})"
            
            selected_item_id = st.selectbox("Select Ingredient", options=id_to_item.keys(), format_func=format_item_label)
            qty = st.number_input("Quantity", min_value=1, value=1)
            
            if st.button("Add to Recipe"):
                item_data = id_to_item[selected_item_id]
                
                # Check if item already exists to update quantity instead of duplicating
                existing_item = next((x for x in st.session_state.new_recipe if x['id'] == item_data['item_id']), None)
                
                if existing_item:
                    existing_item['qty'] += qty
                    st.toast(f"Updated {item_data['name']} quantity to {existing_item['qty']}", icon="🔄")
                else:
                    st.session_state.new_recipe.append({
                        'id': item_data['item_id'],
                        'name': item_data['name'],
                        'qty': qty,
                        'cost': item_data['unit_cost']
                    })
                st.rerun()
        
        # Display Current Recipe Table
        if st.session_state.new_recipe:
            st.write("---")
            recipe_df = pd.DataFrame(st.session_state.new_recipe)
            recipe_df['Subtotal'] = recipe_df['qty'] * recipe_df['cost']
            
            st.dataframe(
                recipe_df[['name', 'qty', 'Subtotal']], 
                width="stretch",
                hide_index=True,
                column_config={"Subtotal": st.column_config.NumberColumn(format="$%.2f")}
            )
            
            # Remove Item Controls
            st.caption("Remove Ingredients")
            col_rem_sel, col_rem_qty, col_rem_btn = st.columns([2, 1, 1], vertical_alignment="bottom")
            
            recipe_items = st.session_state.new_recipe
            id_map = {i['id']: i['name'] for i in recipe_items}

            with col_rem_sel:
                item_to_remove_id = st.selectbox("Item", options=id_map.keys(), format_func=lambda x: id_map[x], label_visibility="collapsed", key="rem_item_select")
            with col_rem_qty:
                qty_to_remove = st.number_input("Qty", min_value=1, value=1, step=1, key="rem_qty_input")
            with col_rem_btn:
                if st.button("Remove", width="stretch"):
                    # Find the item in the list
                    target = next((i for i in st.session_state.new_recipe if i['id'] == item_to_remove_id), None)
                    if target:
                        if qty_to_remove >= target['qty']:
                            # Remove completely if count goes to 0 or negative
                            st.session_state.new_recipe = [i for i in st.session_state.new_recipe if i['id'] != item_to_remove_id]
                            st.toast(f"Removed {target['name']}", icon="🗑️")
                        else:
                            # Just decrease count
                            target['qty'] -= qty_to_remove
                            st.toast(f"Removed {qty_to_remove} {target['name']}", icon="➖")
                    st.rerun()
            
            if st.button("Clear Entire Recipe", type="secondary", width="stretch"):
                st.session_state.new_recipe = []
                st.rerun()