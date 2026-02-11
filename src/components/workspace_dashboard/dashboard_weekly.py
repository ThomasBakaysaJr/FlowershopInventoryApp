import streamlit as st
import pandas as pd
import io
from src.utils import db_utils
from src.components import recipe_display, date_selector

def handle_log_production(goal_id, product_name):
    # 1. Check Requirements
    # We need to get the product_id from the goal first
    conn = db_utils.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT product_id FROM production_goals WHERE goal_id = ?", (goal_id,))
    res = cursor.fetchone()
    conn.close()
    
    if not res: return
    p_id = res[0]
    
    reqs = db_utils.get_recipe_requirements(p_id)
    
    if not reqs['has_generics']:
        # Fast Path: Just Log it (Standard Logic)
        if db_utils.log_production(int(goal_id)):
            st.session_state['weekly_dash_toast'] = (f"Made 1 {product_name}!", "✅")
    else:
        # Slow Path: Open Modal for Selection
        trigger_generic_selection_modal(goal_id, reqs['generic_items'])

@st.dialog("🌸 Select Flowers Used")
def trigger_generic_selection_modal(goal_id, generic_reqs):
    st.write("This recipe requires generic items. Please specify what was used.")
    
    # Search Bar
    search_term = st.text_input("Search Items", placeholder="Type to filter...", label_visibility="collapsed", key=f"search_gen_goal_{goal_id}")

    substitutions_to_make = []
    valid_form = True
    
    # Loop through each requirement (e.g., "12 Roses")
    for req in generic_reqs:
        category = req['category']
        needed = req['qty']
        note = req.get('note')
        
        st.divider()
        label = f"**Required:** {needed} x {category}"
        if note:
            label += f" ({note})"
        st.markdown(label)
        
        # Fetch available items in this category
        inventory_df = db_utils.get_items_by_category(category) 
        
        if inventory_df.empty:
            st.warning(f"No items found for category '{category}' in inventory.")
            continue
            
        # Filter by search (keeping allocated items visible)
        if search_term:
            def is_allocated(row):
                key = f"alloc_{goal_id}_{row['item_id']}"
                return st.session_state.get(key, 0) > 0
            
            mask = (inventory_df['name'].str.contains(search_term, case=False, na=False)) | (inventory_df.apply(is_allocated, axis=1))
            inventory_df = inventory_df[mask]
            
            if inventory_df.empty:
                st.caption(f"No items match '{search_term}' in {category}.")
                continue

        total_allocated = 0
        
        # Dynamic inputs for allocation
        for _, item in inventory_df.iterrows():
            # Show "Red Rose (50 in stock)"
            cols = st.columns([3, 1])
            with cols[0]:
                st.write(f"{item['name']} (Stock: {item['count_on_hand']})")
            with cols[1]:
                allocated = st.number_input(
                    "Use", 
                    min_value=0, 
                    step=1,
                    key=f"alloc_{goal_id}_{item['item_id']}",
                    label_visibility="collapsed"
                )
            
            if allocated > 0:
                substitutions_to_make.append((item['item_id'], allocated))
                total_allocated += allocated
        
        # Validation
        if total_allocated != needed:
            st.warning(f"Selected {total_allocated} / {needed} {category}s.")
        else:
            st.success(f"✅ {category} requirements met.")

    st.divider()
    if st.button("Confirm Production", type="primary", disabled=not valid_form, width='stretch'):
        if db_utils.log_production(goal_id, substitutions=substitutions_to_make):
            st.session_state['weekly_dash_toast'] = ("Production Logged with Details!", "✅")
            st.rerun()

@st.dialog("📝 Adjust Recipe & Make")
def trigger_adjustment_modal(goal_id, product_name, product_id):
    st.write(f"Adjusting ingredients for **{product_name}**.")
    
    details = db_utils.get_product_details(product_name)
    if not details:
        st.error("Could not load recipe.")
        return

    if f"adj_goal_{goal_id}" not in st.session_state:
        initial_items = []
        for item in details['recipe']:
            if item['item_id']:
                initial_items.append({'item_id': item['item_id'], 'name': item['name'], 'qty': item['qty']})
        st.session_state[f"adj_goal_{goal_id}"] = initial_items

    items = st.session_state[f"adj_goal_{goal_id}"]
    
    edited_df = st.data_editor(
        pd.DataFrame(items),
        column_config={
            "name": st.column_config.TextColumn("Ingredient", disabled=True),
            "qty": st.column_config.NumberColumn("Qty Used", min_value=0, step=1),
            "item_id": None
        },
        hide_index=True,
        width="stretch",
        key=f"editor_goal_{goal_id}"
    )
    
    st.divider()
    st.caption("Add Substitution / Extra Item")
    inventory_df = db_utils.get_inventory()
    if not inventory_df.empty:
        inv_options = inventory_df['name'].tolist()
        inv_map = dict(zip(inventory_df['name'], inventory_df['item_id']))
        
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            new_item_name = st.selectbox("Item", options=inv_options, key=f"add_sel_g_{goal_id}", label_visibility="collapsed", index=None, placeholder="Select item...")
        with c2:
            new_qty = st.number_input("Qty", min_value=1, value=1, key=f"add_qty_g_{goal_id}", label_visibility="collapsed")
        with c3:
            if st.button("Add", key=f"add_btn_g_{goal_id}", width="stretch"):
                if new_item_name:
                    new_id = inv_map[new_item_name]
                    existing = next((x for x in st.session_state[f"adj_goal_{goal_id}"] if x['item_id'] == new_id), None)
                    if existing:
                        existing['qty'] += new_qty
                    else:
                        st.session_state[f"adj_goal_{goal_id}"].append({'item_id': new_id, 'name': new_item_name, 'qty': new_qty})
                    st.rerun()

    st.divider()
    if st.button("Confirm & Make", type="primary", width='stretch'):
        final_items = []
        for _, row in edited_df.iterrows():
            if row['qty'] > 0:
                final_items.append((row['item_id'], row['qty']))
        
        if db_utils.log_production(goal_id, substitutions=final_items, ignore_recipe=True):
            st.session_state['weekly_dash_toast'] = (f"Made 1 {product_name} (Custom)", "🛠️")
            del st.session_state[f"adj_goal_{goal_id}"]
            st.rerun()

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
            if pd.notna(first_row['image_data']):
                st.image(io.BytesIO(first_row['image_data']), width=200)
            
            r_data = recipes_df[recipes_df['product_id'] == product_id]
            if not r_data.empty:
                st.dataframe(r_data[['Ingredient', 'Qty', 'Note']], hide_index=True, width="stretch")
            else:
                st.caption("No ingredients listed.")