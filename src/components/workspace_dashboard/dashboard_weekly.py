import streamlit as st
import pandas as pd
from src.utils import db_utils

def handle_log_production(goal_id, product_name):
    # Changed to Fulfill from Stock logic
    if db_utils.fulfill_goal(int(goal_id)):
        st.toast(f"Packed 1 {product_name}!", icon="📦")

def handle_undo_production(goal_id, product_name):
    # Changed to Undo Fulfillment logic
    if db_utils.undo_fulfillment(int(goal_id)):
        st.toast(f"Returned 1 {product_name} to Cooler", icon="↩️")

def render():
    st.subheader("Production Goals")
    goals_df = db_utils.get_weekly_production_goals()

    if not goals_df.empty:
        # Get unique weeks with both ISO and Display format, sorted by ISO
        weeks = goals_df[['week_start_iso', 'Week Starting']].drop_duplicates().sort_values('week_start_iso')
        
        # --- Safe State Initialization for Week Selector ---
        # 1. Determine the "Current Week" (closest match)
        # Find the week that starts before or on today
        default_week = weeks.iloc[0]['week_start_iso'] # Fallback to first
        
        # 2. Initialize state if missing
        if "dashboard_week_select" not in st.session_state:
            st.session_state.dashboard_week_select = default_week

        # 3. Render Widget
        week_map = {row['week_start_iso']: f"Week of {row['Week Starting']}" for _, row in weeks.iterrows()}
        
        selected_iso = st.segmented_control(
            "Select Week",
            options=weeks['week_start_iso'].tolist(),
            format_func=lambda x: week_map.get(x, x),
            key="dashboard_week_select",
            label_visibility="collapsed"
        )

        # Render Content for Selected Week
        if selected_iso:
            render_week_content(goals_df, selected_iso)
    else:
        st.info("No production goals set for the coming weeks.")

def render_week_content(goals_df, week_iso):
    """Helper to filter data and render the grid for a specific week."""
    week_data = goals_df[goals_df['week_start_iso'] == week_iso].copy()
    
    # Check for date column to group by day
    date_col = next((col for col in ['goal_date', 'date', 'due_date'] if col in week_data.columns), None)
    
    if date_col:
        week_data[date_col] = pd.to_datetime(week_data[date_col])
        week_data = week_data.sort_values(date_col)
        
        unique_dates = week_data[date_col].dt.date.unique()
        for date_val in unique_dates:
            st.subheader(date_val.strftime('%A, %b %d'))
            day_data = week_data[week_data[date_col].dt.date == date_val].reset_index(drop=True)
            render_grid(day_data, key_suffix=f"_{date_val}")
    else:
        render_grid(week_data.reset_index(drop=True))

def render_grid(week_data, key_suffix=""):
    # Create a grid: 2 columns on desktop, stacks on mobile
    for i in range(0, len(week_data), 2):
        grid_cols = st.columns(2)
        for j in range(2):
            if i + j < len(week_data):
                row = week_data.iloc[i + j]
                needed = row['qty_ordered'] - row['qty_fulfilled']
                stock = row['stock_on_hand']
                
                with grid_cols[j]:
                    with st.container(border=True):
                        # Added col_img to the layout
                        col_img, col_add, col_name, col_qty, col_undo = st.columns([1.5, 0.6, 2, 1, 0.6], vertical_alignment="center", gap="small")
                        
                        with col_img:
                            if pd.notna(row['image_data']):
                                st.image(row['image_data'], width="stretch")
                        
                        with col_add:
                            # Button Logic:
                            # - Checkmark if done.
                            # - Box (Pack) if needed > 0 AND stock > 0.
                            # - Disabled/Warning if needed > 0 but NO stock.
                            btn_label = "✅" if needed <= 0 else "📦"
                            st.button(
                                btn_label, 
                                key=f"btn_{row['goal_id']}", 
                                disabled=(needed <= 0 or stock <= 0), 
                                use_container_width=True,
                                on_click=handle_log_production,
                                args=(row['goal_id'], row['Product'])
                            )
                        
                        with col_name:
                            display_name = f"[{row['product_id']}] {row['Product']}"
                            if row['active'] == 0:
                                display_name = f"⚠️ {display_name}"
                                
                            st.markdown(f"### **{display_name}**" if needed > 0 else f"~~{display_name}~~")
                        
                        with col_qty:
                            st.markdown(f"### **{needed}** left" if needed > 0 else "Done")
                            if needed > 0:
                                if stock > 0:
                                    st.caption(f"In Cooler: {stock}")
                                else:
                                    st.caption(":red[Empty Cooler]")

                        with col_undo:
                            # Only allow undo if something has been made this week
                            can_undo = row['qty_fulfilled'] > 0
                            with st.popover("➖", disabled=not can_undo, width="stretch", help="Undo last production"):
                                st.write("⚠️ **Confirm Undo?**")
                                st.button(
                                    "Confirm", 
                                    key=f"undo_{row['goal_id']}", 
                                    use_container_width=True,
                                    on_click=handle_undo_production,
                                    args=(row['goal_id'], row['Product'])
                                )