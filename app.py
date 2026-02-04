import streamlit as st
import pandas as pd
import os
import db_utils
import time

st.set_page_config(page_title="University Flowers Dashboard", layout="wide")

st.title("University Flowers Production Dashboard")

if not os.path.exists(db_utils.DB_PATH):
    st.error("Database not found! Please run `python init_db.py` first.")
else:
    # Create tabs for different views
    tab_designer, tab_admin = st.tabs(["🎨 Designer Space", "⚙️ Admin Space"])

    with tab_designer:
        st.header("This Week's Work")
        goals_df = db_utils.get_weekly_production_goals()
        
        if not goals_df.empty:
            for week in goals_df['Week Starting'].unique():
                st.subheader(f"📅 Week of {week}")
                week_data = goals_df[goals_df['Week Starting'] == week].reset_index(drop=True)
                
                # Create a grid: 2 columns on desktop, stacks on mobile
                for i in range(0, len(week_data), 2):
                    grid_cols = st.columns(2)
                    for j in range(2):
                        if i + j < len(week_data):
                            row = week_data.iloc[i + j]
                            needed = row['qty_ordered'] - row['qty_made']
                            
                            with grid_cols[j]:
                                with st.container(border=True):
                                    # Balanced ratios for better text wrapping
                                    col_btn, col_name, col_qty = st.columns([0.5, 2, 1], vertical_alignment="center", gap="small")
                                    
                                    with col_btn:
                                        btn_label = "✅" if needed <= 0 else "ADD"
                                        if st.button(btn_label, key=f"btn_{row['product_id']}_{week}", disabled=(needed <= 0), use_container_width=True):
                                            if db_utils.log_production(int(row['product_id']), week):
                                                st.toast(f"Logged 1 {row['Product']}!", icon="🌸")                                                
                                                time.sleep(0.25)
                                                st.rerun()
                                    
                                    with col_name:
                                        st.markdown(f"### **{row['Product']}**" if needed > 0 else f"~~{row['Product']}~~")
                                    
                                    with col_qty:
                                        st.markdown(f"### **{needed}** left" if needed > 0 else "Done")
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
                    st.write(f"**Target Price:** ${recipe['Price'].iloc[0]:.2f}")
                    for _, row in recipe.iterrows():
                        st.write(f"- {row['Qty']}x {row['Ingredient']}")
        else:
            st.info("No products or recipes defined.")

    with tab_admin:
        # Fetch inventory once to use for both Display and Export tools
        raw_inventory_df = db_utils.get_inventory()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.header("Current Stock Levels")
            if not raw_inventory_df.empty:
                # Renaming columns for better UI display
                display_df = raw_inventory_df.copy()
                display_df.columns = ["ID", "Item Name", "Category", "Sub-Category", "Stock", "Cost"]
                st.dataframe(display_df, width='stretch', hide_index=True)
            else:
                st.info("Inventory is currently empty.")
        
        with col2:
            st.header("Tools")
            
            with st.expander("📤 Export Stem List", expanded=False):
                st.write("Download a text file to copy-paste into your notes app.")
                if not raw_inventory_df.empty:
                    # Filter for Stems only as requested
                    stems_df = raw_inventory_df[raw_inventory_df['category'] == 'Stem']
                    # Format: Name, Sub-Category, Count
                    csv_text = "\n".join([f"{row['name']}, {row['sub_category'] or ''}, {row['count_on_hand']}" for _, row in stems_df.iterrows()])
                    timestamp = time.strftime("%b%d_%H%M")
                    st.download_button(
                        label="📋 Download Stem List (.txt)",
                        data=csv_text,
                        file_name=f"stem_inventory_{timestamp}.txt",
                        mime="text/plain"
                    )
                else:
                    st.info("No stems found.")

            with st.expander("📋 Clipboard Protocol", expanded=True):
                st.write("Paste inventory lists from your phone notes here to update stock.")
                clipboard_text = st.text_area("Paste text here...", height=150, help="Format: Name, Sub-Cat, Qty")
                
                if st.button("Update Inventory"):
                    if clipboard_text:
                        updated, errors = db_utils.process_clipboard_update(clipboard_text)
                        if updated:
                            st.success(f"Updated {len(updated)} items: {', '.join(updated)}")
                            time.sleep(0.25)
                            st.rerun()
                        if errors:
                            st.error(f"Issues found: {'; '.join(errors)}")