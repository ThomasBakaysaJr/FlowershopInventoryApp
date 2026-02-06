import streamlit as st
import pandas as pd

def render(container, inventory_df):
    """Renders the Recipe Builder (Ingredient selection, Table) in the provided container."""
    with container:
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