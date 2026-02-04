import streamlit as st
import pandas as pd
import time
from src.utils import db_utils

def render_designer_dashboard():
    st.header("This Week's Work")
    goals_df = db_utils.get_weekly_production_goals()
    
    if not goals_df.empty:
        # Get unique weeks with both ISO and Display format, sorted by ISO
        weeks = goals_df[['week_start_iso', 'Week Starting']].drop_duplicates().sort_values('week_start_iso')
        
        for _, week_row in weeks.iterrows():
            week_iso = week_row['week_start_iso']
            week_display = week_row['Week Starting']
            st.subheader(f"📅 Week of {week_display}")
            week_data = goals_df[goals_df['week_start_iso'] == week_iso].reset_index(drop=True)
            
            # Create a grid: 2 columns on desktop, stacks on mobile
            for i in range(0, len(week_data), 2):
                grid_cols = st.columns(2)
                for j in range(2):
                    if i + j < len(week_data):
                        row = week_data.iloc[i + j]
                        needed = row['qty_ordered'] - row['qty_made']
                        
                        with grid_cols[j]:
                            with st.container(border=True):
                                # Added col_img to the layout
                                col_img, col_add, col_name, col_qty, col_undo = st.columns([1.5, 0.6, 2, 1, 0.6], vertical_alignment="center", gap="small")
                                
                                with col_img:
                                    if pd.notna(row['image_data']):
                                        st.image(row['image_data'], width="stretch")
                                
                                with col_add:
                                    btn_label = "✅" if needed <= 0 else "➕"
                                    if st.button(btn_label, key=f"btn_{row['product_id']}_{week_iso}", disabled=(needed <= 0), width="stretch"):
                                        if db_utils.log_production(int(row['product_id']), week_iso):
                                            st.toast(f"Logged 1 {row['Product']}!", icon="🌸")                                                
                                            time.sleep(0.25)
                                            st.rerun()
                                
                                with col_name:
                                    st.markdown(f"### **{row['Product']}**" if needed > 0 else f"~~{row['Product']}~~")
                                
                                with col_qty:
                                    st.markdown(f"### **{needed}** left" if needed > 0 else "Done")

                                with col_undo:
                                    # Only allow undo if something has been made this week
                                    can_undo = row['qty_made'] > 0
                                    with st.popover("➖", disabled=not can_undo, width="stretch", help="Undo last production"):
                                        st.write("⚠️ **Confirm Undo?**")
                                        if st.button("Confirm", key=f"undo_{row['product_id']}_{week_iso}", width="stretch"):
                                            if db_utils.undo_production(int(row['product_id']), week_iso):
                                                st.toast(f"Undid 1 {row['Product']}", icon="↩️")
                                                time.sleep(0.25)
                                                st.rerun()
    else:
        st.info("No production goals set for the coming weeks.")

    st.divider()
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