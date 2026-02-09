import streamlit as st
import pandas as pd
from src.utils import db_utils

def render_recipe_display(allow_edit=False):
    st.header("📖 Recipe Book")
    st.caption("Browse all active product recipes.")

    # Fetch all recipes (denormalized)
    df = db_utils.get_all_recipes()

    if df.empty:
        st.info("No recipes found.")
        return

    # Search Bar
    search_term = st.text_input("Search Recipes", placeholder="Search by product name...", label_visibility="collapsed")
    
    if search_term:
        df = df[df['Product'].str.contains(search_term, case=False, na=False)]

    # Group by Product
    # We get multiple rows per product (one per ingredient)
    # We need to iterate over unique products
    unique_products = df[['product_id', 'Product', 'Price', 'image_data', 'active', 'category']].drop_duplicates()

    for _, prod in unique_products.iterrows():
        with st.expander(f"{prod['Product']} - ${prod['Price']:.2f}", expanded=False):
            c1, c2 = st.columns([1, 3])
            
            with c1:
                if pd.notna(prod['image_data']):
                    st.image(prod['image_data'], use_container_width=True)
                else:
                    st.text("No Image")
                
                if allow_edit:
                    if st.button("✏️ Edit Recipe", key=f"edit_rec_{prod['product_id']}", width="stretch"):
                        st.session_state['design_edit_name'] = prod['Product']
                        st.rerun()

            with c2:
                # Filter ingredients for this product
                ingredients = df[df['product_id'] == prod['product_id']].copy()
                
                if ingredients.empty or pd.isna(ingredients.iloc[0]['Ingredient']):
                    st.info("No ingredients defined.")
                else:
                    # Display Ingredients Table
                    st.dataframe(
                        ingredients[['Ingredient', 'Qty', 'Note']],
                        hide_index=True,
                        width="stretch",
                        column_config={
                            "Ingredient": st.column_config.TextColumn("Item"),
                            "Qty": st.column_config.NumberColumn("Qty"),
                            "Note": st.column_config.TextColumn("Note")
                        }
                    )

def render_recipe_expander(product_id, recipes_df):
    """Reusable component to show a recipe expander inside other cards/grids."""
    with st.expander("Recipe Details"):
        if not recipes_df.empty:
            prod_recipe = recipes_df[recipes_df['product_id'] == product_id]
            if not prod_recipe.empty:
                st.dataframe(
                    prod_recipe[['Ingredient', 'Qty', 'Note']],
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Ingredient": st.column_config.TextColumn("Item"),
                        "Qty": st.column_config.NumberColumn("Qty"),
                        "Note": st.column_config.TextColumn("Note")
                    }
                )
            else:
                st.caption("No recipe defined.")