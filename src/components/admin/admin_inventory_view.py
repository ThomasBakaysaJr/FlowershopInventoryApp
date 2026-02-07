import streamlit as st
import time
import logging
from src.utils import db_utils

logger = logging.getLogger(__name__)

def render_stock_levels(raw_inventory_df):
    st.header("Current Stock Levels")
    if not raw_inventory_df.empty:
        edited_df = st.data_editor(
            raw_inventory_df,
            column_config={
                "item_id": st.column_config.NumberColumn("ID", disabled=True),
                "name": st.column_config.TextColumn("Item Name", disabled=True),
                "category": st.column_config.TextColumn("Category", disabled=True),
                "sub_category": st.column_config.TextColumn("Sub-Category", disabled=True),
                "count_on_hand": st.column_config.NumberColumn("Stock", disabled=True),
                "unit_cost": st.column_config.NumberColumn("Cost ($)", min_value=0.0, step=0.01, format="$%.2f", required=True)
            },
            hide_index=True,
            width="stretch",
            key="inventory_editor"
        )

        if st.button("💾 Save Changes", key="save_inventory_changes"):
            changes = 0
            for index, row in edited_df.iterrows():
                original = raw_inventory_df[raw_inventory_df['item_id'] == row['item_id']]
                if not original.empty:
                    old_cost = original.iloc[0]['unit_cost']
                    new_cost = row['unit_cost']
                    if abs(new_cost - old_cost) > 0.001:
                        db_utils.update_inventory_cost(row['item_id'], new_cost)
                        changes += 1
            
            if changes > 0:
                logger.info(f"Inventory updated via Admin: {changes} items changed.")
                st.toast(f"Updated {changes} items.")
                time.sleep(0.25)
                st.rerun()
            else:
                st.info("No changes detected.")
    else:
        st.info("Inventory is currently empty.")