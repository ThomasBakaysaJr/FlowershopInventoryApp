import streamlit as st
import time
from src.utils import db_utils

def render_eod_tools(raw_inventory_df):
    st.header("EOD Inventory Count")
    
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
        
        if st.button("Update Inventory", width="stretch"):
            if clipboard_text:
                updated, errors = db_utils.process_clipboard_update(clipboard_text)
                if updated:
                    st.success(f"✅ Successfully updated {len(updated)} items: {', '.join(updated)}")
                if errors:
                    for err in errors:
                        st.error(f"❌ {err}")

def render_bulk_operations(raw_inventory_df):
    # ==========================
    # 📦 BULK OPERATIONS SECTION
    # ==========================
    st.header("📦 Bulk Operations")
    
    # 1. INVENTORY MASS UPDATE
    st.subheader("1. Inventory Mass Update")
    st.caption("Download current inventory, update counts/costs in Excel, and re-upload.")
    
    col_dl_inv, col_up_inv = st.columns(2)
    
    with col_dl_inv:
        csv_data = db_utils.export_inventory_csv()
        st.download_button(
            label="⬇️ Download Inventory CSV",
            data=csv_data,
            file_name=f"inventory_export_{time.strftime('%Y%m%d')}.csv",
            mime="text/csv",
            help="Includes ID to ensure exact matching.",
            width="stretch"
        )
        
    with col_up_inv:
        inv_file = st.file_uploader("Upload Inventory (.csv)", type=["csv"], key="inv_upload")
        if inv_file:
            if st.button("Process Inventory Update", type="primary", width="stretch"):
                count, errors = db_utils.process_bulk_inventory_upload(inv_file)
                if count > 0:
                    st.success(f"✅ Successfully updated {count} items!")
                    time.sleep(1) # Give user time to see success
                    st.rerun()
                if errors:
                    with st.expander("⚠️ Import Errors", expanded=True):
                        for e in errors:
                            st.error(e)
                            
    st.divider()
    
    # 2. PRODUCT & RECIPE IMPORT
    st.subheader("2. Recipe & Product Import")
    st.caption("Mass import products. Required Columns: **Product, Price, Type, Ingredient, Qty**")
    
    col_dl_prod, col_up_prod = st.columns(2)
    
    with col_dl_prod:
        prod_csv = db_utils.export_products_csv()
        st.download_button(
            label="⬇️ Download Catalog CSV",
            data=prod_csv,
            file_name=f"catalog_export_{time.strftime('%Y%m%d')}.csv",
            mime="text/csv",
            help="Use this to back up recipes or add new ones.",
            width="stretch"
        )
        
    with col_up_prod:
        prod_file = st.file_uploader("Upload Recipes (.csv)", type=["csv"], key="prod_upload")
        if prod_file:
            if st.button("Process Recipe Import", type="primary", width="stretch"):
                count, errors = db_utils.process_bulk_recipe_upload(prod_file)
                if count > 0:
                    st.success(f"✅ Processed {count} products!")
                    time.sleep(1)
                    st.rerun()
                if errors:
                    with st.expander("⚠️ Import Errors", expanded=True):
                        for e in errors:
                            st.error(e)