import streamlit as st
import pandas as pd
import time
from src.utils import db_utils

def render_single_recipe(prod_row, full_df, allow_edit):
    """Helper to render a single recipe card."""
    product_name = prod_row['Product']
    p_id = prod_row['product_id']
    is_active = prod_row['active']
    
    display_name = product_name
    if is_active == 0:
        display_name = f"⚠️{product_name}"
    
    with st.expander(f"📖 [{p_id}] {display_name}"):
        recipe = full_df[full_df['product_id'] == p_id]

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
                    if st.button("✏️ Edit", key=f"edit_btn_{p_id}"):
                        # Load data into session state for the Design Studio
                        st.session_state['design_edit_name'] = product_name
                        st.session_state['design_edit_price'] = recipe['Price'].iloc[0]
                        st.session_state['design_edit_ingredients'] = recipe[['Ingredient', 'Qty']].to_dict('records')
                        st.toast(f"Loading '{product_name}' in Design Studio...", icon="🎨")
                        time.sleep(0.25)
                        st.rerun()
                        
                    with st.popover("🗑️", help="Delete Product"):
                        st.write(f"Delete **{product_name}**?")
                        if st.button("Confirm", key=f"confirm_del_{p_id}", type="primary"):
                            db_utils.delete_product(p_id)
                            st.toast(f"Deleted {product_name}")
                            st.rerun()

def render_recipe_display(allow_edit=False):
    st.header("Recipe Reference")
    
    # Fetch recipes and group them by product for a cleaner UI
    products_df = db_utils.get_all_recipes()

    if not products_df.empty:
        unique_products = products_df[['Product', 'product_id', 'active']].drop_duplicates()
        
        if not allow_edit:
            # WORKSPACE VIEW: Show Active + Archived (ONLY if currently in production goals)
            goals_df = db_utils.get_weekly_production_goals()
            active_goal_ids = []
            if not goals_df.empty:
                active_goal_ids = goals_df['product_id'].unique().tolist()
            
            # Filter: Active OR in current goals
            mask = (unique_products['active'] == 1) | (unique_products['product_id'].isin(active_goal_ids))
            visible_products = unique_products[mask]
            
            if visible_products.empty:
                st.info("No active recipes found.")
            else:
                for _, row in visible_products.iterrows():
                    render_single_recipe(row, products_df, allow_edit)
                    
        else:
            # DESIGNER VIEW: Active separated from Archived
            active_prods = unique_products[unique_products['active'] == 1]
            archived_prods = unique_products[unique_products['active'] == 0]
            
            for _, row in active_prods.iterrows():
                render_single_recipe(row, products_df, allow_edit)

            if not archived_prods.empty:
                st.divider()
                st.caption("Archived Recipes")
                with st.expander("📂 View Archived Recipes"):
                    for _, row in archived_prods.iterrows():
                        render_single_recipe(row, products_df, allow_edit)
    else:
        st.info("No products or recipes defined.")