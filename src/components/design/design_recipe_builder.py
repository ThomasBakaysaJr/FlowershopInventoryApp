import streamlit as st
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def add_ingredient_callback(id_to_item):
    # Retrieve current widget states directly from session state
    item_mode = st.session_state.get("recipe_builder_mode")
    qty = st.session_state.get("recipe_builder_qty", 1)
    note = st.session_state.get("recipe_builder_note", "").strip()

    # Ensure recipe list exists
    if 'new_recipe' not in st.session_state:
        st.session_state.new_recipe = []

    if item_mode == "Specific Item":
        selected_item_id = st.session_state.get("recipe_builder_item_select")
        
        if selected_item_id is None or selected_item_id not in id_to_item:
            st.toast("Please select an item.", icon="⚠️")
            return

        # Use selected_item_id as the source of truth for the ID
        try:
            target_id = int(float(selected_item_id))
        except (ValueError, TypeError):
            st.toast("Invalid Item ID.", icon="⚠️")
            return
            
        # Retrieve metadata (Name, Cost)
        item_data = id_to_item.get(selected_item_id)
        if item_data is None:
            st.toast("Item details not found.", icon="⚠️")
            return
        
        # Check if item already exists to update quantity instead of duplicating
        existing_item = None
        for item in st.session_state.new_recipe:
            # We only care about items that HAVE an ID (Specific)
            stored_id = item.get('id')
            
            if stored_id is not None:
                try:
                    check_id = int(float(stored_id))
                    if check_id == target_id:
                        existing_item = item
                        break
                except (ValueError, TypeError):
                    continue
        
        if existing_item:
            existing_item['qty'] += qty
            if note: # Update note if provided
                existing_item['note'] = note
            st.toast(f"Updated {item_data['name']} quantity to {existing_item['qty']}", icon="🔄")
        else:
            st.session_state.new_recipe.append({
                'id': target_id, # Store as int
                'name': item_data['name'],
                'qty': qty,
                'cost': float(item_data['unit_cost']),
                'type': 'Specific',
                'val': None,
                'note': note
            })
    else:
        selected_cat_name = st.session_state.get("recipe_builder_cat_select")
        
        if not selected_cat_name:
            st.toast("Please select a category.", icon="⚠️")
            return

        # Add Generic to session state
        # Check if generic category already exists
        existing_generic = None
        for item in st.session_state.new_recipe:
            # Match by type/val
            if item.get('type') == 'Category' and item.get('val') == selected_cat_name:
                existing_generic = item
                break
            # Fallback: Match by name pattern (legacy items)
            if item.get('id') is None and item.get('name') == f"Any {selected_cat_name}":
                existing_generic = item
                break
        
        if existing_generic:
            existing_generic['qty'] += qty
            # Normalize structure if it was a legacy item
            if 'type' not in existing_generic:
                existing_generic['type'] = 'Category'
                existing_generic['val'] = selected_cat_name
            if note:
                existing_generic['note'] = note
            st.toast(f"Updated Any {selected_cat_name} quantity to {existing_generic['qty']}", icon="🔄")
        else:
            st.session_state.new_recipe.append({
                "name": f"Any {selected_cat_name}",
                "qty": qty,
                "type": "Category",
                "val": selected_cat_name,
                "id": None,
                "cost": 0.0,
                "note": note
            })
    
    # Reset quantity to 1 for next add
    st.session_state.recipe_builder_note = ""
    st.session_state.recipe_builder_qty = 1

def render(container, inventory_df):
    """Renders the Recipe Builder (Ingredient selection, Table) in the provided container."""
    with container:
        st.subheader("2. Build Recipe")
        
        if not inventory_df.empty:
            # Filter by Category
            categories = ["All"] + sorted(list(inventory_df['category'].dropna().unique()))
            
            c1, c2, c3, c4, c5 = st.columns([1.5, 2, 1.5, 0.8, 0.8])
            
            with c1:
                # TOGGLE: Specific Item vs Generic Category
                item_mode = st.radio("Type", ["Specific Item", "Generic Sub-Category"], horizontal=True, label_visibility="collapsed", key="recipe_builder_mode")
            
            # Initialize variables to ensure scope availability for callback args
            id_to_item = {}
            selected_item_id = None
            selected_cat_name = None

            # Filter Items
            with c2:
                if item_mode == "Specific Item":
                    selected_cat = st.selectbox("Filter Category", categories, label_visibility="collapsed")
                    if selected_cat != "All":
                        filtered_items = inventory_df[inventory_df['category'] == selected_cat]
                    else:
                        filtered_items = inventory_df
                    
                    # Create lookup: ID -> Row Data
                    id_to_item = {row['item_id']: row for _, row in filtered_items.iterrows()}
                    
                    def format_item_label(item_id):
                        item = id_to_item[item_id]
                        try:
                            cost = float(item['unit_cost'])
                        except (ValueError, TypeError):
                            cost = 0.0
                        return f"{item['name']} (${cost:.2f})"
                    
                    selected_item_id = st.selectbox("Select Ingredient", options=id_to_item.keys(), format_func=format_item_label, label_visibility="collapsed", key="recipe_builder_item_select")
                else:
                    # NEW: Category Logic
                    # Get unique sub_categories (e.g., 'Rose', 'Lily')
                    cat_options = [x for x in inventory_df['sub_category'].unique() if x]
                    selected_cat_name = st.selectbox("Select Sub-Category", sorted(cat_options), label_visibility="collapsed", key="recipe_builder_cat_select")

            with c3:
                st.text_input("Note", placeholder="e.g. 'Short stems'", label_visibility="collapsed", key="recipe_builder_note")

            with c4:
                qty = st.number_input("Quantity", min_value=1, value=1, label_visibility="collapsed", key="recipe_builder_qty")
            
            with c5:
                st.button("Add", type="primary", width='stretch', on_click=add_ingredient_callback, args=(id_to_item,))
        
        # Display Current Recipe Table
        if st.session_state.new_recipe:
            st.write("---")
            recipe_df = pd.DataFrame(st.session_state.new_recipe)
            recipe_df['Subtotal'] = recipe_df['qty'] * recipe_df['cost']
            
            st.dataframe(
                recipe_df[['name', 'note', 'qty', 'Subtotal']], 
                width="stretch",
                hide_index=True,
                column_config={"Subtotal": st.column_config.NumberColumn(format="$%.2f")}
            )
            
            # Remove Item Controls
            st.caption("Remove Ingredients")
            col_rem_sel, col_rem_qty, col_rem_btn = st.columns([2, 1, 1], vertical_alignment="bottom")
            
            # Re-implementing removal logic to use index
            recipe_items = st.session_state.new_recipe
            idx_map = {i: f"{item['name']} (Qty: {item['qty']})" for i, item in enumerate(recipe_items)}

            with col_rem_sel:
                item_to_remove_idx = st.selectbox("Item", options=idx_map.keys(), format_func=lambda x: idx_map[x], label_visibility="collapsed", key="rem_item_select")
            with col_rem_qty:
                qty_to_remove = st.number_input("Qty", min_value=1, value=1, step=1, key="rem_qty_input")
            with col_rem_btn:
                if st.button("Remove", width="stretch"):
                    target = st.session_state.new_recipe[item_to_remove_idx]
                    if target:
                        if qty_to_remove >= target['qty']:
                            # Remove completely if count goes to 0 or negative
                            st.session_state.new_recipe.pop(item_to_remove_idx)
                            st.toast(f"Removed {target['name']}", icon="🗑️")
                        else:
                            # Just decrease count
                            target['qty'] -= qty_to_remove
                            st.toast(f"Removed {qty_to_remove} {target['name']}", icon="➖")
                    st.rerun()
            
            if st.button("Clear Entire Recipe", type="secondary", width="stretch"):
                st.session_state.new_recipe = []
                st.rerun()