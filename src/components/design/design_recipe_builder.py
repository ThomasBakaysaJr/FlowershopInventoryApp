import streamlit as st
import pandas as pd
import copy
from src.utils import db_utils

def render_recipe_editor(p_id, v_details, group_id, v_type, variant_map):
    st.markdown("### 🌿 Recipe")
    
    # Initialize session state for this product's recipe if not exists
    if f"recipe_state_{p_id}" not in st.session_state:
        st.session_state[f"recipe_state_{p_id}"] = v_details['recipe']
    
    current_recipe = st.session_state[f"recipe_state_{p_id}"]
    if current_recipe:
        recipe_df = pd.DataFrame(current_recipe)
        
        # Ensure required columns exist to prevent KeyError
        for col in ['name', 'qty', 'type', 'val', 'note']:
            if col not in recipe_df.columns:
                recipe_df[col] = None

        # Add a 'remove' column for the editor
        recipe_df['remove'] = False

        # Configure columns for the editor
        column_config = {
            "remove": st.column_config.CheckboxColumn("🗑️", width="small", help="Check to remove item"),
            "name": st.column_config.TextColumn("Ingredient", disabled=True),
            "qty": st.column_config.NumberColumn("Qty", min_value=1, step=1, width="small"),
            "type": st.column_config.TextColumn("Type", disabled=True),
            "val": st.column_config.TextColumn("Value", disabled=True),
            "note": st.column_config.TextColumn("Note")
        }

        edited_df = st.data_editor(
            recipe_df[['remove', 'name', 'qty', 'type', 'val', 'note']],
            width="stretch",
            hide_index=True,
            column_config=column_config,
            key=f"recipe_editor_{p_id}"
        )

        # Process updates (Removals or Edits)
        if not edited_df.equals(recipe_df[['remove', 'name', 'qty', 'type', 'val', 'note']]):
            new_recipe_list = []
            for idx, row in edited_df.iterrows():
                if not row['remove']:
                    # Preserve original item_id and other hidden fields by copying from source
                    updated_item = current_recipe[idx].copy()
                    updated_item['qty'] = row['qty']
                    updated_item['note'] = row['note']
                    new_recipe_list.append(updated_item)
            
            st.session_state[f"recipe_state_{p_id}"] = new_recipe_list
            st.rerun()
    else:
        st.info("No ingredients yet.")

    with st.expander("✏️ Edit Recipe", expanded=True):
        # Toggle for Specific Item vs Generic Category
        ing_type = st.radio("Ingredient Type", ["Specific Item", "Generic Category"], horizontal=True, label_visibility="collapsed", key=f"ing_type_{p_id}")
        
        c1, c2, c3 = st.columns([3, 1, 1], vertical_alignment="bottom")
        
        selected_item_id = None
        selected_item_name = None
        selected_cat = None
        custom_note = None
        
        with c1:
            if ing_type == "Specific Item":
                inv_df = db_utils.get_inventory()
                inv_options = inv_df['name'].tolist() if not inv_df.empty else []
                selected_ing = st.selectbox("Select Item", inv_options, key=f"sel_ing_{p_id}")
                
                if selected_ing and not inv_df.empty:
                    item_row = inv_df[inv_df['name'] == selected_ing].iloc[0]
                    selected_item_id = int(item_row['item_id'])
                    selected_item_name = selected_ing
            else:
                # Generic Category Selection (Mapped to Big Categories)
                cats = db_utils.get_inventory_categories()
                selected_cat = st.selectbox("Inventory Category", options=cats, key=f"cat_sel_{p_id}", help="Restricts fulfillment to items in this category.")
                # Custom Note for the "Name" preference
                custom_note = st.text_input("Description / Preference", placeholder="e.g. Any Rose", key=f"cat_note_{p_id}")

        with c2:
            qty_add = st.number_input("Qty", min_value=1, value=1, key=f"qty_{p_id}")
        with c3:
            add_btn = st.button("Add", key=f"add_btn_{p_id}")
        
        if add_btn:
            new_recipe = current_recipe.copy()
            found = False
            
            if ing_type == "Specific Item" and selected_item_id:
                # Check if item already exists in recipe to aggregate
                for r in new_recipe:
                    if r.get('item_id') == selected_item_id and r.get('type', 'Specific') == 'Specific':
                        r['qty'] += qty_add
                        found = True
                        break
                if not found:
                    new_recipe.append({'item_id': selected_item_id, 'qty': qty_add, 'type': 'Specific', 'val': None, 'name': selected_item_name, 'note': None})
            
            elif ing_type == "Generic Category" and selected_cat:
                # Always add generics as new rows (or you could aggregate if names match exactly)
                # We use the Category for the logic ('val') and the Custom Note for the user's description ('note')
                new_recipe.append({'item_id': None, 'qty': qty_add, 'type': 'Category', 'val': selected_cat, 'name': f"Any {selected_cat}", 'note': custom_note})
            
            st.session_state[f"recipe_state_{p_id}"] = new_recipe
            st.rerun()

        if st.button("🗑️ Clear Recipe", key=f"clear_{p_id}"):
            st.session_state[f"recipe_state_{p_id}"] = []
            st.rerun()
        
        # Copy Logic
        if v_type in ['DLX', 'PRM'] and 'STD' in variant_map:
            if st.button(f"📋 Copy from Standard", key=f"copy_{p_id}"):
                std_info = variant_map['STD']
                std_p_id = std_info['product_id']
                
                # Check for unsaved changes in session state first
                if f"recipe_state_{std_p_id}" in st.session_state:
                    st.session_state[f"recipe_state_{p_id}"] = copy.deepcopy(st.session_state[f"recipe_state_{std_p_id}"])
                    st.toast("Copied recipe from Standard (Unsaved)!")
                    st.rerun()
                else:
                    std_details = db_utils.get_product_details(std_info['name'])
                    if std_details and std_details['recipe']:
                        st.session_state[f"recipe_state_{p_id}"] = std_details['recipe']
                        st.toast("Copied recipe from Standard!")
                        st.rerun()
                    else:
                        st.warning("Standard version has no recipe to copy.")