import streamlit as st
import pandas as pd
from src.utils import db_utils

def render_recipe_display(allow_edit=False):
    st.header("Recipe Reference")
    
    # Fetch recipes and group them by product for a cleaner UI
    products_df = db_utils.get_all_recipes()

    if not products_df.empty:
        # Get unique products with their IDs
        unique_products = products_df[['Product', 'product_id', 'active']].drop_duplicates()
        
        for _, prod_row in unique_products.iterrows():
            product_name = prod_row['Product']
            p_id = prod_row['product_id']
            is_active = prod_row['active']
            
            display_name = product_name
            if is_active == 0:
                display_name = f"{product_name} ⚠️ (Archived)"
            
            with st.expander(f"📖 {display_name}"):
                recipe = products_df[products_df['product_id'] == p_id]

                # --- VIEW MODE ---
                with st.container(border=True):
                    if allow_edit:
                        col_image, col_recipe, col_actions = st.columns([1, 2, 0.5], vertical_alignment="top", gap="small")
                    else:
                        col_image, col_recipe = st.columns([1, 2], vertical_alignment="top", gap="small")

                    with col_image:
                        if pd.notna(recipe['image_data'].iloc[0]):
                            st.image(recipe['image_data'].iloc[0], width=200)
                    with col_recipe:
                        st.write(f"**Target Price:** ${recipe['Price'].iloc[0]:.2f}")
                        for _, row in recipe.iterrows():
                            if pd.notna(row['Ingredient']):
                                st.write(f"- {row['Qty']}x {row['Ingredient']}")
                    
                    if allow_edit:
                        with col_actions:
                            if st.button("✏️ Edit in Studio", key=f"edit_btn_{p_id}"):
                                # Load data into session state for the Design Studio
                                st.session_state['design_edit_name'] = product_name
                                st.session_state['design_edit_price'] = recipe['Price'].iloc[0]
                                st.session_state['design_edit_ingredients'] = recipe[['Ingredient', 'Qty']].to_dict('records')
                                st.toast(f"Loaded '{product_name}'! Switch to 'Design Studio' tab to edit.", icon="🎨")
                                
                            with st.popover("🗑️", help="Delete Product"):
                                st.write(f"Delete **{product_name}**?")
                                if st.button("Confirm", key=f"confirm_del_{p_id}", type="primary"):
                                    db_utils.delete_product(p_id)
                                    st.toast(f"Deleted {product_name}")
                                    st.rerun()
    else:
        st.info("No products or recipes defined.")