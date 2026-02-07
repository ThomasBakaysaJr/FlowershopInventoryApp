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

    st.divider()
    
    st.subheader("🗑️ Goal Management")
    st.caption("Edit quantities or cancel production goals.")

    # Reuse the existing getter since it grabs everything
    goals_df = db_utils.get_weekly_production_goals()
    
    if not goals_df.empty:
        # Sort by ID descending (show newest created first usually helps find mistakes)
        goals_df = goals_df.sort_values('goal_id', ascending=False)
        
        with st.container(border=True):
            # Header Row
            h1, h2, h3, h4, h5 = st.columns([1, 2, 1, 1, 0.5])
            h1.markdown("**Due Date**")
            h2.markdown("**Product**")
            h3.markdown("**Progress**")
            h4.markdown("**Edit Target**")
            h5.markdown("**Del**")
            
            for _, row in goals_df.iterrows():
                c1, c2, c3, c4, c5 = st.columns([1, 2, 1, 1, 0.5], vertical_alignment="center")
                
                with c1:
                    st.write(row['due_date'].strftime('%b %d'))
                with c2:
                    st.write(row['Product'])
                with c3:
                    st.write(f"{row['qty_fulfilled']} / {row['qty_ordered']}")
                
                with c4:
                    # EDIT QUANTITY Logic
                    new_val = st.number_input(
                        "Qty", 
                        min_value=1, 
                        value=int(row['qty_ordered']), 
                        label_visibility="collapsed",
                        key=f"edit_qty_{row['goal_id']}"
                    )
                    
                    if new_val != row['qty_ordered']:
                        if st.button("💾", key=f"save_qty_{row['goal_id']}", help="Save new quantity"):
                            if db_utils.update_goal_quantity(row['goal_id'], new_val):
                                st.toast(f"Updated goal to {new_val}!")
                                st.rerun()

                with c5:
                    if st.button("❌", key=f"del_goal_{row['goal_id']}", help="Delete Goal (Returns items to Stock)"):
                        if db_utils.delete_production_goal(row['goal_id']):
                            st.toast("Goal deleted. Completed items returned to Cooler.")
                            st.rerun()
    else:
        st.info("No active goals found.")