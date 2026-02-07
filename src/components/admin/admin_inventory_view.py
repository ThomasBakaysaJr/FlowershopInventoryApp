import streamlit as st
import time
import logging
import pandas as pd
from src.utils import db_utils

logger = logging.getLogger(__name__)

def render_stock_levels(raw_inventory_df):
    st.header("Current Stock Levels")
    st.text("Please review any changes before saving.")    

    if not raw_inventory_df.empty:
        edited_df = st.data_editor(
            raw_inventory_df,
            column_config={
                "item_id": st.column_config.NumberColumn("ID", disabled=True),
                "name": st.column_config.TextColumn("Item Name", disabled=True),
                "category": st.column_config.TextColumn("Category", disabled=True),
                "sub_category": st.column_config.TextColumn("Sub-Category", disabled=True),
                "count_on_hand": st.column_config.NumberColumn("Stock", min_value=0, step=1, required=True),
                "unit_cost": st.column_config.NumberColumn("Cost ($)", min_value=0.0, step=0.01, format="$%.2f", required=True)
            },
            hide_index=True,
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
                
                if cost_changed or count_changed:
                    changes_count += 1
                    changed_rows.append(row)
                    diff_data.append({
                        "Item": row['name'],
                        "Old Stock": orig_row['count_on_hand'],
                        "New Stock": row['count_on_hand'],
                        "Old Cost": orig_row['unit_cost'],
                        "New Cost": row['unit_cost']
                    })

        def perform_save():
            if changes_count > 0:
                success_count = 0
                for row in changed_rows:
                    if db_utils.update_item_details(row['item_id'], row['count_on_hand'], row['unit_cost']):
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
            diff_df = diff_df[["Item", "Old Stock", "New Stock", "Old Cost", "New Cost"]]
            
            def highlight_cells(x):
                c = [''] * len(x)
                # Highlight New Stock (Index 2) if changed
                if x['New Stock'] != x['Old Stock']:
                    c[2] = 'background-color: rgba(255, 235, 59, 0.3); color: black;'
                # Highlight New Cost (Index 4) if changed
                if abs(x['New Cost'] - x['Old Cost']) > 0.001:
                    c[4] = 'background-color: rgba(255, 235, 59, 0.3); color: black;'
                return c

            st.dataframe(
                diff_df.style.apply(highlight_cells, axis=1).format({"Old Cost": "${:.2f}", "New Cost": "${:.2f}"}),
                hide_index=True,
                use_container_width=True
            )
            st.warning(f"You have unsaved changes.", icon="⚠️")

        if st.button("💾 Save Changes", key="save_inventory_changes", type="primary" if changes_count > 0 else "secondary"):
            perform_save()
    else:
        st.info("Inventory is currently empty.")