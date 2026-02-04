import streamlit as st
import pandas as pd
from src.utils import db_utils

def render_recipe_display():
    st.header("Recipe Reference")
    
    # Fetch recipes and group them by product for a cleaner UI
    products_df = db_utils.get_all_recipes()

    if not products_df.empty:
        for product in products_df['Product'].unique():
            with st.expander(f"📖 {product}"):
                recipe = products_df[products_df['Product'] == product]
                with st.container(border=True):
                    col_image, col_recipe = st.columns([1, 2], vertical_alignment="center", gap="small")

                    with col_image:
                        if pd.notna(recipe['image_data'].iloc[0]):
                            st.image(recipe['image_data'].iloc[0], width=200)
                    with col_recipe:
                        st.write(f"**Target Price:** ${recipe['Price'].iloc[0]:.2f}")
                        for _, row in recipe.iterrows():
                            st.write(f"- {row['Qty']}x {row['Ingredient']}")
    else:
        st.info("No products or recipes defined.")