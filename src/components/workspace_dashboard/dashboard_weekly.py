import streamlit as st
import pandas as pd
import datetime
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
    
    substitutions_to_make = []
    valid_form = True
    
    # Loop through each requirement (e.g., "12 Roses")
    for req in generic_reqs:
        category = req['category']
        needed = req['qty']
        
        st.divider()
        st.markdown(f"**Required:** {needed} x {category}")
        
        # Fetch available items in this category
        inventory_df = db_utils.get_items_by_category(category) 
        
        if inventory_df.empty:
            st.warning(f"No items found for category '{category}' in inventory.")
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

@st.fragment(run_every=5)
def render():
    if 'weekly_dash_toast' in st.session_state:
        msg, icon = st.session_state.pop('weekly_dash_toast')
        st.toast(msg, icon=icon)

    st.subheader("Production Goals")
    
    # --- Date Selection ---
    start_date, end_date = date_selector.render("weekly_dash")
    
    if start_date > end_date:
        return

    # --- Fetch Data ---
    goals_df = db_utils.get_production_goals_range(start_date, end_date)
    recipes_df = db_utils.get_all_recipes()

    if not goals_df.empty:
        goals_df['due_date'] = pd.to_datetime(goals_df['due_date'])
        
        unique_dates = goals_df['due_date'].dt.date.unique()
        for date_val in unique_dates:
            st.subheader(date_val.strftime('%A, %b %d'))
            day_data = goals_df[goals_df['due_date'].dt.date == date_val].reset_index(drop=True)
            render_grid(day_data, recipes_df, key_suffix=f"_{date_val}")
    else:
        st.info("No production goals set for this period.")

def render_grid(week_data, recipes_df, key_suffix=""):
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
                        col_add, col_name, col_qty, col_undo = st.columns([0.7, 2.5, 1, 0.7], vertical_alignment="center", gap="small")
                        
                        with col_add:
                            # Button Logic:
                            # - Checkmark if done.
                            # - Box (Pack) if needed > 0 AND stock > 0.
                            # - Disabled/Warning if needed > 0 but NO stock.
                            
                            if needed <= 0:
                                btn_label = "✅"
                                handler = None
                                is_disabled = True
                            elif stock > 0:
                                btn_label = "📦" # Pack from Stock
                                handler = handle_fulfill_goal
                                is_disabled = False
                            else:
                                btn_label = "➕" # Make New
                                handler = handle_log_production
                                is_disabled = False

                            st.button(
                                btn_label, 
                                key=f"btn_{row['goal_id']}", 
                                disabled=is_disabled, 
                                width="stretch",
                                on_click=handler,
                                args=(row['goal_id'], row['Product'])
                            )
                        
                        with col_name:
                            display_name = f"[{row['product_id']}] {row['Product']}"
                            if row['active'] == 0:
                                display_name = f"⚠️ {display_name}"
                            
                            # Variant Badge
                            v_type = row.get('variant_type', 'STD')
                            if v_type == 'DLX':
                                st.markdown(f"**{display_name}** :blue[**[DLX]**]")
                            elif v_type == 'PRM':
                                st.markdown(f"**{display_name}** :red[**[PRM]**]")
                            else:
                                st.markdown(f"**{display_name}**" if needed > 0 else f"~~{display_name}~~")

                            if pd.notna(row['note']) and row['note']:
                                st.caption(f"📝 {row['note']}")
                        
                        with col_qty:
                            st.markdown(f"**{needed}** left" if needed > 0 else "Done")
                            if needed > 0:
                                if stock > 0:
                                    st.caption(f"In Cooler: {stock}")
                                    
                                    # Pack All Option
                                    packable = int(min(stock, needed)) # Ensure int
                                    if packable > 1:
                                        st.button(
                                            f"🚀 Pack {packable}", 
                                            key=f"pack_all_{row['goal_id']}", 
                                            width="stretch",
                                            help="Pack all available items for this goal",
                                            on_click=handle_fulfill_goal,
                                            args=(row['goal_id'], row['Product'], packable)
                                        )
                                else:
                                    st.caption(":red[Empty Cooler]")

                        with col_undo:
                            # Only allow undo if something has been made this week
                            can_undo = row['qty_fulfilled'] > 0
                            with st.popover("➖", disabled=not can_undo, use_container_width=True, help="Undo last production"):
                                st.write("⚠️ **Confirm Undo?**")
                                st.button(
                                    "Confirm", 
                                    key=f"undo_{row['goal_id']}", 
                                    width="stretch",
                                    on_click=handle_undo_production,
                                    args=(row['goal_id'], row['Product'])
                                )
                        
                        with st.expander("🌿 Recipe & Image"):
                            if pd.notna(row['image_data']):
                                st.image(row['image_data'], width=200)
                            
                            # Filter for recipe
                            r_data = recipes_df[recipes_df['product_id'] == row['product_id']]
                            if not r_data.empty:
                                st.dataframe(
                                    r_data[['Ingredient', 'Qty', 'Note']], 
                                    hide_index=True, 
                                    use_container_width=True
                                )
                            else:
                                st.caption("No ingredients listed.")