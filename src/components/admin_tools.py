import streamlit as st
import time
from src.utils import db_utils

def render_admin_tools(raw_inventory_df):
    st.header("Inventory Management Tools")
    
    if not raw_inventory_df.empty:
        stems_df = raw_inventory_df[raw_inventory_df['category'] == 'Stem']
        if not stems_df.empty:
            csv_text = "\n".join([f"{row['name']}, {row['sub_category'] or ''}, {row['count_on_hand']}" for _, row in stems_df.iterrows()])
            timestamp = time.strftime("%b%d_%H%M")
            st.download_button(
                label="💾 Download Stem List for Counting (.txt)",
                data=csv_text,
                file_name=f"stem_inventory_{timestamp}.txt",
                mime="text/plain",
                width="stretch"
            )
    
    st.divider()

    with st.expander("📋 Clipboard Protocol", expanded=True):
        st.write("Paste inventory lists from your phone notes here to update stock.")
        clipboard_text = st.text_area("Paste text here...", height=150, help="Format: Name, Sub-Cat, Qty")
        
        if st.button("Update Inventory"):
            if clipboard_text:
                updated, errors = db_utils.process_clipboard_update(clipboard_text)
                if updated:
                    st.success(f"✅ Successfully updated {len(updated)} items: {', '.join(updated)}")
                if errors:
                    for err in errors:
                        st.error(f"❌ {err}")