import streamlit as st
import pandas as pd
from src.utils import db_utils

def render_recipe_editor(p_id, v_details, group_id, v_type, variant_map):
    st.markdown("### 🌿 Recipe")
    
    current_recipe = v_details['recipe']
    if current_recipe:
        recipe_df = pd.DataFrame(current_recipe)
        display_df = recipe_df[['name', 'qty', 'type', 'val', 'note']].copy()
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No ingredients yet.")

    with st.expander("✏️ Edit Recipe", expanded=True):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            inv_df = db_utils.get_inventory()
            inv_options = inv_df['name'].tolist() if not inv_df.empty else []
            selected_ing = st.selectbox("Add Ingredient", inv_options, key=f"sel_ing_{p_id}")
        with c2:
            qty_add = st.number_input("Qty", min_value=1, value=1, key=f"qty_{p_id}")
        with c3:
            add_btn = st.button("Add", key=f"add_btn_{p_id}")
        
        if add_btn and selected_ing:
            item_row = inv_df[inv_df['name'] == selected_ing].iloc[0]
            item_id = int(item_row['item_id'])
            
            new_recipe = current_recipe.copy()
            found = False
            for r in new_recipe:
                if r['item_id'] == item_id:
                    r['qty'] += qty_add
                    found = True
                    break
            if not found:
                new_recipe.append({'item_id': item_id, 'qty': qty_add})
            
            db_utils.update_product_recipe(
                current_product_id=p_id,
                new_name=v_details['name'],
                recipe_items=new_recipe,
                variant_group_id=group_id
            )
            st.rerun()

        if st.button("🗑️ Clear Recipe", key=f"clear_{p_id}"):
             db_utils.update_product_recipe(
                current_product_id=p_id,
                new_name=v_details['name'],
                recipe_items=[],
                variant_group_id=group_id
            )
             st.rerun()
        
        # Copy Logic
        if v_type in ['DLX', 'PRM'] and 'STD' in variant_map:
            if st.button(f"📋 Copy from Standard", key=f"copy_{p_id}"):
                std_details = db_utils.get_product_details(variant_map['STD']['name'])
                if std_details and std_details['recipe']:
                    db_utils.update_product_recipe(
                        current_product_id=p_id,
                        new_name=v_details['name'],
                        recipe_items=std_details['recipe'],
                        variant_group_id=group_id
                    )
                    st.success("Copied recipe from Standard!")
                    st.rerun()
                else:
                    st.warning("Standard version has no recipe to copy.")