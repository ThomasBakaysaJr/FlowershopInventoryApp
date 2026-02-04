import streamlit as st
import pandas as pd
from src.utils import db_utils, utils

def render_design_tab(inventory_df):
    st.header("🌸 New Arrangement Designer")
    st.caption("Build new products by selecting items from your inventory.")

    # Initialize session state for the recipe being built
    if 'new_recipe' not in st.session_state:
        st.session_state.new_recipe = [] # List of {'id': int, 'name': str, 'qty': int, 'cost': float}

    # --- INPUT SECTION ---
    col_details, col_builder = st.columns([1, 1.5], gap="large")

    with col_details:
        st.subheader("1. Product Details")
        prod_name = st.text_input("Product Name", placeholder="e.g., Summer Breeze")
        uploaded_file = st.file_uploader("Upload Thumbnail", type=['png', 'jpg', 'jpeg'])
        
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

        if st.button("💾 Save New Product", type="primary", width="stretch"):
            if prod_name and st.session_state.new_recipe:
                img_bytes = None
                if uploaded_file:
                    img_bytes = utils.process_image(uploaded_file)
                    if not img_bytes:
                        st.error("Error processing image. Please check the file format.")
                        st.stop()

                # Prepare list for DB: [(id, qty), ...]
                db_items = [(x['id'], x['qty']) for x in st.session_state.new_recipe]
                
                if db_utils.create_new_product(prod_name, final_price, img_bytes, db_items):
                    st.success(f"Successfully created '{prod_name}'!")
                    st.session_state.new_recipe = [] # Reset
                    st.rerun()
                else:
                    st.error("Failed to save product. Check database connection.")
            else:
                st.warning("Please provide a name and at least one ingredient.")

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