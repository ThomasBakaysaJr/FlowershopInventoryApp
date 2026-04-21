import streamlit as st
import pandas as pd
import io
from src.utils import db_utils
from src.components import date_selector
from src.components.workspace_dashboard.shared_modals import generic_selection_modal

def handle_log_production(goal_id, product_name):
    p_id = db_utils.get_goal_product_id(goal_id)
    if not p_id:
        return

    reqs = db_utils.get_recipe_requirements(p_id)

    if not reqs['has_generics']:
        if db_utils.log_production(int(goal_id)):
            st.session_state['weekly_dash_toast'] = (f"Made 1 {product_name}!", "✅")
    else:
        generic_selection_modal(
            key_prefix=f"goal_{goal_id}",
            display_name=product_name,
            generic_reqs=reqs['generic_items'],
            on_confirm=lambda subs: db_utils.log_production(int(goal_id), substitutions=subs),
            toast_key='weekly_dash_toast',
            toast_success_msg=f"Made 1 {product_name} with details!",
        )

def handle_fulfill_goal(goal_id, product_name, qty=1):
    """Fulfills a goal using existing Cooler Stock."""
    packed = db_utils.fulfill_goal(int(goal_id), qty=int(qty))
    if packed > 0:
        if packed > 1:
            st.session_state['weekly_dash_toast'] = (f"Packed {packed} {product_name}s!", "🚀")
        else:
            st.session_state['weekly_dash_toast'] = (f"Packed 1 {product_name} from Cooler!", "📦")

def handle_undo_production(goal_id, product_name):
    # Standard Undo Logic
    if db_utils.undo_production(int(goal_id)):
        st.session_state['weekly_dash_toast'] = (f"Undid 1 {product_name}", "↩️")

def handle_fulfill_slot(goals_data, product_name):
    """Fulfills multiple goals in a slot sequentially until stock runs out."""
    total_packed = 0
    for g_id, g_needed in goals_data:
        # Try to pack the full needed amount for this goal
        # db_utils.fulfill_goal will automatically clamp to available stock
        packed = db_utils.fulfill_goal(int(g_id), qty=int(g_needed))
        total_packed += packed
        if packed < g_needed:
            break # Stock ran out
            
    if total_packed > 0:
        st.session_state['weekly_dash_toast'] = (f"Packed {total_packed} {product_name}s!", "🚀")

@st.fragment(run_every=120) # re-run every two minutes
def render():
    if 'weekly_dash_toast' in st.session_state:
        msg, icon = st.session_state.pop('weekly_dash_toast')
        st.toast(msg, icon=icon)

    st.subheader("Production Goals")
    
    # --- Date Selection ---
    start_date, end_date = date_selector.render("weekly_dash")
    
    if start_date > end_date:
        return

    # Search Bar
    c_search, c_clear = st.columns([6, 1], vertical_alignment="bottom")
    with c_search:
        search_term = st.text_input("Search Goals", placeholder="Filter by product name...", label_visibility="collapsed", key="weekly_dash_search")
    with c_clear:
        if st.button("Clear", key="clear_weekly_search", help="Clear Search", width="stretch"):
            st.session_state.weekly_dash_search = ""
            st.rerun()
    
    st.divider()

    # --- Fetch Data ---
    goals_df = db_utils.get_production_goals_range(start_date, end_date)
    recipes_df = db_utils.get_all_recipes()

    # Apply Search
    if search_term:
        goals_df = db_utils.filter_dataframe_by_terms(goals_df, 'Product', search_term)

    if not goals_df.empty:
        goals_df['due_date'] = pd.to_datetime(goals_df['due_date'])
        
        # Sort by Time Slot (AM -> PM -> Any) within the date
        goals_df['time_rank'] = goals_df['time_slot'].map({'AM': 0, 'PM': 1, 'ANY': 2}).fillna(3)
        goals_df = goals_df.sort_values(by=['due_date', 'time_rank', 'Product', 'goal_id'])
        
        unique_dates = goals_df['due_date'].dt.date.unique()
        for date_val in unique_dates:
            st.subheader(date_val.strftime('%A, %b %d'))
            day_data = goals_df[goals_df['due_date'].dt.date == date_val].reset_index(drop=True)
            render_grid(day_data, recipes_df, key_suffix=f"_{date_val}")
    else:
        st.info("No production goals set for this period.")

def render_grid(week_data, recipes_df, key_suffix=""):
    # Group by Product ID to combine entries into single cards
    # Sort by Product Name first for the grid layout
    week_data = week_data.sort_values(by=['Product', 'time_rank'])
    unique_products = week_data['product_id'].unique()

    # Create a grid: 2 columns on desktop
    for i in range(0, len(unique_products), 2):
        grid_cols = st.columns(2)
        for j in range(2):
            if i + j < len(unique_products):
                p_id = unique_products[i + j]
                # Get all goals for this product on this day
                group_df = week_data[week_data['product_id'] == p_id]
                
                with grid_cols[j]:
                    render_grouped_card(group_df, recipes_df, key_suffix)

def render_grouped_card(group_df, recipes_df, key_suffix):
    # Extract static info from the first row (since it's all the same product)
    first_row = group_df.iloc[0]
    product_name = first_row['Product']
    product_id = first_row['product_id']
    stock = first_row['stock_on_hand']
    
    with st.container(border=True):
        # --- Header: Name + Variant ---
        display_name = f"[{product_id}] {product_name}"
        if first_row['active'] == 0:
            display_name = f"⚠️ {display_name}"
            
        v_type = first_row.get('variant_type', 'STD')
        if v_type == 'DLX':
            st.markdown(f"**{display_name}** :blue[**[DLX]**]")
        elif v_type == 'PRM':
            st.markdown(f"**{display_name}** :red[**[PRM]**]")
        else:
            st.markdown(f"**{display_name}** :green[**[STD]**]")

        # Stock Indicator
        if stock > 0:
            st.caption(f"🧊 Cooler Stock: **{stock}**")
        else:
            st.caption("🧊 Cooler Stock: :red[Empty]")

        st.divider()

        # --- Aggregated Goals by Time Slot ---
        # 1. Get unique slots in order (AM -> PM -> Any)
        # group_df is already sorted by time_rank in render()
        slots = group_df['time_slot'].unique()

        for slot in slots:
            # Filter rows for this slot (e.g. all AM goals)
            slot_df = group_df[group_df['time_slot'] == slot]
            
            # Aggregate stats
            qty_ordered = slot_df['qty_ordered'].sum()
            qty_fulfilled = slot_df['qty_fulfilled'].sum()
            needed = qty_ordered - qty_fulfilled
            
            # Determine Target Goal ID for Actions
            # Priority: First goal that needs items.
            # If all done, we target the last one (for Undo).
            target_goal = None
            pending_goals = slot_df[slot_df['qty_fulfilled'] < slot_df['qty_ordered']]
            
            if not pending_goals.empty:
                target_goal = pending_goals.iloc[0]
            else:
                target_goal = slot_df.iloc[-1]
            
            goal_id = target_goal['goal_id']
            
            c_time, c_info, c_act = st.columns([0.8, 2, 1.2], vertical_alignment="center")
            
            with c_time:
                if slot == 'AM':
                    st.markdown(":blue[**AM**]")
                elif slot == 'PM':
                    st.markdown(":orange[**PM**]")
                else:
                    st.markdown("**Any**")
            
            with c_info:
                if needed <= 0:
                    st.markdown("✅ Done")
                else:
                    st.markdown(f"Need **{needed}**")
            
            with c_act:
                if needed <= 0:
                    # Find the last goal that actually has progress to undo
                    undo_candidates = slot_df[slot_df['qty_fulfilled'] > 0]
                    if not undo_candidates.empty:
                        undo_goal = undo_candidates.iloc[-1]
                        if st.button("↩️", key=f"undo_slot_{product_id}_{slot}{key_suffix}", help="Undo last item"):
                            handle_undo_production(undo_goal['goal_id'], product_name)
                            st.rerun()
                else:
                    # Pack or Make
                    if stock > 0:
                        packable = min(stock, needed)
                        if packable > 1:
                            # Show Single Pack AND Pack All
                            b1, b2 = st.columns(2)
                            with b1:
                                st.button("📦", key=f"pack_1_{product_id}_{slot}{key_suffix}", help="Pack 1", on_click=handle_fulfill_goal, args=(goal_id, product_name))
                            with b2:
                                # Prepare list of (goal_id, needed) for this slot
                                goals_to_pack = []
                                for _, pg in pending_goals.iterrows():
                                    rem = pg['qty_ordered'] - pg['qty_fulfilled']
                                    goals_to_pack.append((pg['goal_id'], rem))
                                st.button(f"🚀 {packable}", key=f"pack_all_{product_id}_{slot}{key_suffix}", help=f"Pack all {packable}", on_click=handle_fulfill_slot, args=(goals_to_pack, product_name))
                        else:
                            st.button("📦 Pack", key=f"pack_slot_{product_id}_{slot}{key_suffix}", on_click=handle_fulfill_goal, args=(goal_id, product_name))
                    else:
                        st.button("➕ Make", key=f"make_slot_{product_id}_{slot}{key_suffix}", on_click=handle_log_production, args=(goal_id, product_name))

        # --- Recipe Expander ---
        with st.expander("🌿 Recipe & Image"):
            if 'image_data' in first_row and pd.notna(first_row['image_data']):
                st.image(io.BytesIO(first_row['image_data']), width=200)
            
            r_data = recipes_df[recipes_df['product_id'] == product_id]
            if not r_data.empty:
                st.dataframe(r_data[['Ingredient', 'Qty', 'Note']], hide_index=True, width="stretch")
            else:
                st.caption("No ingredients listed.")