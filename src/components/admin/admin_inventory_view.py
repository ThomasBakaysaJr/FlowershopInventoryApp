import streamlit as st
import time
import logging
import pandas as pd
from src.utils import db_utils

logger = logging.getLogger(__name__)

@st.fragment(run_every=10)
def render_stock_levels(raw_inventory_df):
    # Fetch fresh data to ensure auto-updates work within the fragment
    raw_inventory_df = db_utils.get_inventory()

    # Ensure numeric columns are actually numeric to avoid TypeErrors during subtraction
    if not raw_inventory_df.empty:
        raw_inventory_df['unit_cost'] = pd.to_numeric(raw_inventory_df['unit_cost'], errors='coerce').fillna(0.0)
        raw_inventory_df['count_on_hand'] = pd.to_numeric(raw_inventory_df['count_on_hand'], errors='coerce').fillna(0).astype(int)
        raw_inventory_df['bundle_count'] = pd.to_numeric(raw_inventory_df['bundle_count'], errors='coerce').fillna(1).astype(int)

    st.header("Current Stock Levels")
    st.text("Please review any changes before saving.")    

    if not raw_inventory_df.empty:
        # --- Filter UI ---
        col_cat, col_sub = st.columns(2)
        
        with col_cat:
            categories = sorted([str(c) for c in raw_inventory_df['category'].unique() if c])
            selected_cats = st.multiselect("Category", options=categories, placeholder="Filter by Category")
            
        # Filter for sub-cats based on category selection
        if selected_cats:
            temp_df = raw_inventory_df[raw_inventory_df['category'].isin(selected_cats)]
        else:
            temp_df = raw_inventory_df
            
        with col_sub:
            sub_categories = sorted([str(c) for c in temp_df['sub_category'].unique() if c])
            selected_subs = st.multiselect("Sub-Category", options=sub_categories, placeholder="Filter by Sub-Category")
            
        # Apply Filters
        filtered_df = raw_inventory_df.copy()
        if selected_cats:
            filtered_df = filtered_df[filtered_df['category'].isin(selected_cats)]
        if selected_subs:
            filtered_df = filtered_df[filtered_df['sub_category'].isin(selected_subs)]

        # Calculate height to show all rows (35px per row + 38px header + buffer)
        data_height = (len(filtered_df) * 35) + 38

        edited_df = st.data_editor(
            filtered_df,
            column_config={
                "item_id": st.column_config.NumberColumn("ID", disabled=True),
                "name": st.column_config.TextColumn("Item Name", disabled=True),
                "category": st.column_config.TextColumn("Category", disabled=True),
                "sub_category": st.column_config.TextColumn("Sub-Category", disabled=True),
                "count_on_hand": st.column_config.NumberColumn("Stock", min_value=0, step=1, required=True),
                "bundle_count": st.column_config.NumberColumn("Bundle Qty", min_value=1, step=1, required=True, help="Items per bundle/pack"),
                "unit_cost": st.column_config.NumberColumn("Cost ($)", min_value=0.0, step=0.01, format="$%.2f", required=True)
            },
            hide_index=True,
            height=data_height,
            width="stretch",
            key="inventory_editor"
        )

        # Detect Changes
        changes_count = 0
        changed_rows = []
        diff_data = []
        
        for index, row in edited_df.iterrows():
            original = raw_inventory_df[raw_inventory_df['item_id'] == row['item_id']]
            if not original.empty:
                orig_row = original.iloc[0]
                
                cost_changed = abs(row['unit_cost'] - orig_row['unit_cost']) > 0.001
                count_changed = row['count_on_hand'] != orig_row['count_on_hand']
                bundle_changed = row['bundle_count'] != orig_row['bundle_count']
                
                if cost_changed or count_changed or bundle_changed:
                    changes_count += 1
                    changed_rows.append(row)
                    diff_data.append({
                        "Item": row['name'],
                        "Old Stock": orig_row['count_on_hand'],
                        "New Stock": row['count_on_hand'],
                        "Old Bundle": orig_row['bundle_count'],
                        "New Bundle": row['bundle_count'],
                        "Old Cost": orig_row['unit_cost'],
                        "New Cost": row['unit_cost']
                    })

        def perform_save():
            if changes_count > 0:
                success_count = 0
                for row in changed_rows:
                    if db_utils.update_item_details(row['item_id'], row['count_on_hand'], row['unit_cost'], row['bundle_count']):
                        success_count += 1
                
                if success_count > 0:
                    logger.info(f"Inventory updated via Admin: {success_count} items changed.")
                    st.toast(f"Updated {success_count} items.")
                    time.sleep(0.25)
                    st.rerun()
            else:
                st.info("No changes detected.")

        if changes_count > 0:
            st.divider()
            st.caption("Review Changes:")
            
            diff_df = pd.DataFrame(diff_data)
            # Ensure column order for consistent indexing in the styler
            diff_df = diff_df[["Item", "Old Stock", "New Stock", "Old Bundle", "New Bundle", "Old Cost", "New Cost"]]
            
            def highlight_cells(x):
                c = [''] * len(x)
                # Highlight New Stock (Index 2) if changed
                if x['New Stock'] != x['Old Stock']:
                    c[2] = 'background-color: rgba(255, 235, 59, 0.3); color: black;'
                # Highlight New Bundle (Index 4) if changed
                if x['New Bundle'] != x['Old Bundle']:
                    c[4] = 'background-color: rgba(255, 235, 59, 0.3); color: black;'
                # Highlight New Cost (Index 6) if changed
                if abs(x['New Cost'] - x['Old Cost']) > 0.001:
                    c[6] = 'background-color: rgba(255, 235, 59, 0.3); color: black;'
                return c

            st.dataframe(
                diff_df.style.apply(highlight_cells, axis=1).format({"Old Cost": "${:.2f}", "New Cost": "${:.2f}"}),
                hide_index=True,
                width="stretch"
            )
            st.warning(f"You have unsaved changes.", icon="⚠️")

        if st.button("💾 Save Changes", key="save_inventory_changes", type="primary" if changes_count > 0 else "secondary"):
            perform_save()
    else:
        st.info("Inventory is currently empty.")