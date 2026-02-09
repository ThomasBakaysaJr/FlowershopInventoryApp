import streamlit as st
import pandas as pd
from src.utils import db_utils

def render_recipe_display(allow_edit=False):
    st.header("📖 Recipe Book")
    st.caption("Browse product recipes.")

    # Fetch all recipes (denormalized)
    df = db_utils.get_all_recipes()

    if df.empty:
        st.info("No recipes found.")
        return

    # Search Bar
    search_term = st.text_input("Search Recipes", placeholder="Search by product name...", label_visibility="collapsed")
    
    if search_term:
        df = df[df['Product'].str.contains(search_term, case=False, na=False)]

    # Split Active vs Archived
    active_df = df[df['active'] == 1]
    archived_df = df[df['active'] == 0]

    def render_recipe_list(product_df):
        unique_products = product_df[['product_id', 'Product', 'Price', 'image_data', 'active', 'category', 'ProductNote']].drop_duplicates()

        for _, prod in unique_products.iterrows():
            display_name = f"{prod['Product']} - ${prod['Price']:.2f}"
            if prod['active'] == 0:
                display_name = f"⚠️ [Archived] {display_name}"

            with st.expander(display_name, expanded=False):
                c1, c2 = st.columns([1, 3])
                
                with c1:
                    if pd.notna(prod['image_data']):
                        st.image(prod['image_data'], use_container_width=True)
                    else:
                        st.text("No Image")
                    
                    if pd.notna(prod['ProductNote']) and prod['ProductNote']:
                        st.info(f"📝 {prod['ProductNote']}")
                    
                    if allow_edit:
                        if st.button("✏️ Edit Recipe", key=f"edit_rec_{prod['product_id']}", width="stretch"):
                            st.session_state['design_edit_name'] = prod['Product']
                            st.rerun()
                        
                        # Only show delete for active products
                        if prod['active'] == 1:
                            with st.popover("🗑️ Delete", use_container_width=True):
                                st.write("Are you sure?")
                                if st.button("Confirm", key=f"del_{prod['product_id']}", type="primary", width="stretch"):
                                    if db_utils.delete_product(prod['product_id']):
                                        st.toast(f"Deleted {prod['Product']}", icon="🗑️")
                                        st.rerun()

                with c2:
                    # Filter ingredients for this product
                    ingredients = product_df[product_df['product_id'] == prod['product_id']].copy()
                    
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

    # Render Active
    if not active_df.empty:
        render_recipe_list(active_df)
    elif archived_df.empty:
        st.info("No recipes found matching criteria.")

    # Render Archived
    if not archived_df.empty:
        st.divider()
        st.subheader("🗄️ Archived Recipes")
        render_recipe_list(archived_df)

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