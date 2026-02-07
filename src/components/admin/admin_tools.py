import streamlit as st
import time
from src.utils import db_utils

def render_admin_tools(raw_inventory_df):
    st.header("Inventory Management Tools")
    
    if not raw_inventory_df.empty:
        st.subheader("Download Inventory List")
        
        col_cat_select, col_download = st.columns(2)
        
        with col_cat_select:
        # Get unique categories, filtering out None/Empty
            categories = sorted([c for c in raw_inventory_df['category'].unique() if c])
            
            selected_cats = st.multiselect(
                label="Select Categories",
                label_visibility="collapsed",
                placeholder="Please select categories to include.",
                options=categories,
                default=None
            )
        
        with col_download:
            if not selected_cats:
                st.error("⚠️ Please select at least one category.")
            else:
                filtered_df = raw_inventory_df[raw_inventory_df['category'].isin(selected_cats)]
                
                lines = [f"{row['item_id']}, {row['name']}, {row['sub_category'] or ''}, {row['category']}, bundle_count={row['bundle_count']}, loss= ,count= ," for _, row in filtered_df.iterrows()]
                txt_data = "\n".join(lines)
                timestamp = time.strftime("%b%d_%H%M")
                st.download_button(
                    help="Download selected inventory items for counting",
                    label="💾 Download List for Counting (.txt)",
                    data=txt_data,
                    file_name=f"inventory_count_{timestamp}.txt",
                    mime="text/plain",
                    width="stretch"
                )
    
    st.divider()

    with st.expander("📋 Clipboard Protocol", expanded=True):
        st.write("Paste inventory lists here to update stock.")
        clipboard_text = st.text_area("Paste text here...", height=150, help="Format: Name, Sub-Cat, Qty")
        
        if st.button("Update Inventory"):
            if clipboard_text:
                updated, errors = db_utils.process_clipboard_update(clipboard_text)
                if updated:
                    st.success(f"✅ Successfully updated {len(updated)} items: {', '.join(updated)}")
                if errors:
                    for err in errors:
                        st.error(f"❌ {err}")