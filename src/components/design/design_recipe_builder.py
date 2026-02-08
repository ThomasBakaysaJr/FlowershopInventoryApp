import streamlit as st
import pandas as pd

def render(container, inventory_df):
    """Renders the Recipe Builder (Ingredient selection, Table) in the provided container."""
    with container:
        st.subheader("2. Build Recipe")
        
        if not inventory_df.empty:
            # Filter by Category
            categories = ["All"] + sorted(list(inventory_df['category'].dropna().unique()))
            
            c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
            
            with c1:
                # TOGGLE: Specific Item vs Generic Category
                item_mode = st.radio("Type", ["Specific Item", "Generic Sub-Category"], horizontal=True, label_visibility="collapsed")
            
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
                    
                    selected_item_id = st.selectbox("Select Ingredient", options=id_to_item.keys(), format_func=format_item_label, label_visibility="collapsed")
                else:
                    # NEW: Category Logic
                    # Get unique sub_categories (e.g., 'Rose', 'Lily')
                    cat_options = [x for x in inventory_df['sub_category'].unique() if x]
                    selected_cat_name = st.selectbox("Select Sub-Category", sorted(cat_options), label_visibility="collapsed")

            with c3:
                qty = st.number_input("Quantity", min_value=1, value=1, label_visibility="collapsed")
            
            with c4:
                if st.button("Add", type="primary", width='stretch'):
                    if item_mode == "Specific Item":
                        item_data = id_to_item[selected_item_id]
                        
                        # Check if item already exists to update quantity instead of duplicating
                        existing_item = next((x for x in st.session_state.new_recipe if x.get('id') == item_data['item_id']), None)
                        
                        if existing_item:
                            existing_item['qty'] += qty
                            st.toast(f"Updated {item_data['name']} quantity to {existing_item['qty']}", icon="🔄")
                        else:
                            st.session_state.new_recipe.append({
                                'id': item_data['item_id'],
                                'name': item_data['name'],
                                'qty': qty,
                                'cost': item_data['unit_cost'],
                                'type': 'Specific',
                                'val': None
                            })
                    else:
                        # Add Generic to session state
                        st.session_state.new_recipe.append({
                            "name": f"Any {selected_cat_name}",
                            "qty": qty,
                            "type": "Category",
                            "val": selected_cat_name,
                            "id": None,
                            "cost": 0.0
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