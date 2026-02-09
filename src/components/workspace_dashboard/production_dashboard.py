import streamlit as st
import pandas as pd
import datetime
from src.utils import db_utils
from src.components import recipe_display

def handle_make_stock(product_id, product_name):
    """Callback to increase stock."""
    # 1. Check Requirements
    reqs = db_utils.get_recipe_requirements(product_id)
    
    if not reqs['has_generics']:
        # Fast Path: Just Log it
        if db_utils.produce_stock(product_id):
            st.session_state['prod_dash_toast'] = (f"Made 1 {product_name}", "📦")
    else:
        # Slow Path: Open Modal for Selection
        trigger_generic_stock_modal(product_id, product_name, reqs['generic_items'])

@st.dialog("🌸 Select Flowers Used")
def trigger_generic_stock_modal(product_id, product_name, generic_reqs):
    st.write(f"Making **{product_name}**. Please specify generic items used.")
    
    substitutions_to_make = []
    valid_form = True
    
    # Loop through each requirement
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
            cols = st.columns([3, 1])
            with cols[0]:
                st.write(f"{item['name']} (Stock: {item['count_on_hand']})")
            with cols[1]:
                allocated = st.number_input(
                    "Use", 
                    min_value=0, 
                    step=1,
                    key=f"stock_alloc_{product_id}_{item['item_id']}",
                    label_visibility="collapsed"
                )
            
            if allocated > 0:
                substitutions_to_make.append((item['item_id'], allocated))
                total_allocated += allocated
        
        if total_allocated != needed:
            st.warning(f"Selected {total_allocated} / {needed} {category}s.")
        else:
            st.success(f"✅ {category} requirements met.")

    st.divider()
    if st.button("Confirm Production", type="primary", disabled=not valid_form, width='stretch'):
        if db_utils.produce_stock(product_id, substitutions=substitutions_to_make):
            st.session_state['prod_dash_toast'] = (f"Made 1 {product_name} with details!", "📦")
            st.rerun()

@st.dialog("📝 Adjust Recipe & Make")
def trigger_adjustment_modal(product_id, product_name):
    st.write(f"Adjusting ingredients for **{product_name}**.")
    
    # 1. Fetch Standard Recipe
    details = db_utils.get_product_details(product_name)
    if not details:
        st.error("Could not load recipe.")
        return

    # Initialize state for this modal if not present
    if f"adj_items_{product_id}" not in st.session_state:
        # Convert recipe to list of dicts for editing
        # We flatten generics into this list too, so the user sees everything
        initial_items = []
        for item in details['recipe']:
            # If it's a generic requirement (no item_id), we can't pre-fill an ID, 
            # but we can show it as a placeholder or just skip it and let them add.
            # Better: Skip generics here, they must be added manually if specific items were used.
            if item['item_id']:
                initial_items.append({'item_id': item['item_id'], 'name': item['name'], 'qty': item['qty'], 'note': item.get('note')})
        st.session_state[f"adj_items_{product_id}"] = initial_items

    # 2. Render Editable List
    items = st.session_state[f"adj_items_{product_id}"]
    
    # Use Data Editor for quick adjustments
    edited_df = st.data_editor(
        pd.DataFrame(items),
        column_config={
            "name": st.column_config.TextColumn("Ingredient", disabled=True),
            "note": st.column_config.TextColumn("Note"),
            "qty": st.column_config.NumberColumn("Qty Used", min_value=0, step=1),
            "item_id": None # Hide ID
        },
        hide_index=True,
        width="stretch",
        key=f"editor_{product_id}"
    )
    
    # 3. Add Extra Item Section
    st.divider()
    st.caption("Add Substitution / Extra Item")
    inventory_df = db_utils.get_inventory()
    if not inventory_df.empty:
        # Create a lookup for names
        inv_options = inventory_df['name'].tolist()
        inv_map = dict(zip(inventory_df['name'], inventory_df['item_id']))
        
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            new_item_name = st.selectbox("Item", options=inv_options, key=f"add_sel_{product_id}", label_visibility="collapsed", index=None, placeholder="Select item...")
        with c2:
            new_qty = st.number_input("Qty", min_value=1, value=1, key=f"add_qty_{product_id}", label_visibility="collapsed")
        with c3:
            if st.button("Add", key=f"add_btn_{product_id}", width="stretch"):
                if new_item_name:
                    # Add to session state list
                    new_id = inv_map[new_item_name]
                    # Check if exists
                    existing = next((x for x in st.session_state[f"adj_items_{product_id}"] if x['item_id'] == new_id), None)
                    if existing:
                        existing['qty'] += new_qty
                    else:
                        st.session_state[f"adj_items_{product_id}"].append({'item_id': new_id, 'name': new_item_name, 'qty': new_qty, 'note': None})
                    st.rerun()

    st.divider()
    if st.button("Confirm & Make", type="primary", width='stretch'):
        # Convert edited DF back to list
        final_items = []
        # We iterate the edited_df to get the values from the widget
        for _, row in edited_df.iterrows():
            if row['qty'] > 0:
                final_items.append((row['item_id'], row['qty']))
        
        # We also need to include any newly added items that might not be in the editor yet 
        # (Actually, st.data_editor updates session state? No, it returns a new DF)
        # The "Add" button updates the source list, which re-renders the editor.
        # So edited_df IS the source of truth for the *next* render, but we need to capture it here.
        
        if db_utils.produce_stock(product_id, substitutions=final_items, ignore_recipe=True):
            st.session_state['prod_dash_toast'] = (f"Made 1 {product_name} (Custom)", "🛠️")
            # Cleanup
            del st.session_state[f"adj_items_{product_id}"]
            st.rerun()

def handle_undo_stock(product_id, product_name):
    """Callback to decrease stock."""
    if db_utils.undo_stock_production(product_id):
        st.session_state['prod_dash_toast'] = (f"Undid 1 {product_name}", "↩️")
    else:
        st.session_state['prod_dash_toast'] = ("Nothing to undo.", "⚠️")

@st.fragment(run_every=5)
def render():
    if 'prod_dash_toast' in st.session_state:
        msg, icon = st.session_state.pop('prod_dash_toast')
        st.toast(msg, icon=icon)

    st.subheader("📦 Cooler Production Dashboard")
    st.caption("Manage 'Cooler Stock' (Finished Goods). Making items here deducts raw inventory and increases stock on hand.")
    
    # --- Date Selection Logic ---
    if 'prod_dash_start' not in st.session_state:
        st.session_state.prod_dash_start = datetime.date.today()
    if 'prod_dash_end' not in st.session_state:
        st.session_state.prod_dash_end = datetime.date.today() + datetime.timedelta(days=7)

    # Layout: Quick Buttons (Left) | Date Pickers (Right)
    col_btns, col_dates = st.columns([1.5, 2], vertical_alignment="bottom")
    
    with col_btns:
        st.write("Quick Select:")
        b_col1, b_col2, b_col3 = st.columns(3, gap="small")
        if b_col1.button("Today", width="stretch"):
            st.session_state.prod_dash_start = datetime.date.today()
            st.session_state.prod_dash_end = datetime.date.today()
            st.rerun()
        if b_col2.button("This Week", width="stretch"):
            st.session_state.prod_dash_start = datetime.date.today()
            st.session_state.prod_dash_end = datetime.date.today() + datetime.timedelta(days=6)
            st.rerun()
        if b_col3.button("This Month", width="stretch"):
            st.session_state.prod_dash_start = datetime.date.today()
            st.session_state.prod_dash_end = datetime.date.today() + datetime.timedelta(days=30)
            st.rerun()

    with col_dates:
        d_col1, d_col2 = st.columns(2)
        d_col1.date_input("Start", key="prod_dash_start")
        d_col2.date_input("End", key="prod_dash_end")

    # Search Bar
    c_search, c_clear = st.columns([6, 1], vertical_alignment="bottom")
    with c_search:
        search_term = st.text_input("Search", placeholder="Filter by product name...", label_visibility="collapsed", key="prod_dash_search")
    with c_clear:
        if st.button("Clear", help="Clear Search", width="stretch"):
            st.session_state.prod_dash_search = ""
            st.rerun()

    st.divider()

    # --- Fetch Data ---
    df = db_utils.get_production_requirements(st.session_state.prod_dash_start, st.session_state.prod_dash_end)
    recipes_df = db_utils.get_all_recipes()

    # Apply Search Filter
    if search_term:
        df = df[df['Product'].str.contains(search_term, case=False, na=False)]

    if df.empty:
        st.info("No active products or requirements found for this period.")
        return

    # --- Render Grid ---
    # 2 columns on desktop
    for i in range(0, len(df), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j < len(df):
                row = df.iloc[i+j]
                with cols[j]:
                    render_card(row, recipes_df)

def render_card(row, recipes_df):
    with st.container(border=True):
        # Layout: Image | Info (Name, Stats, Bar) | Actions (+/-)
        c_img, c_info, c_act = st.columns([1, 2.5, 0.8], vertical_alignment="center")
        
        with c_img:
            if pd.notna(row['image_data']):
                st.image(row['image_data'], use_container_width=True)
            else:
                st.text("No Image")

        with c_info:
            # Name & ID
            name = f"[{row['product_id']}] {row['Product']}"
            if row['active'] == 0:
                name = "⚠️ " + name
            st.markdown(f"**{name}**")
            
            # Stats
            stock = row['stock_on_hand']
            needed = row['required_qty']
            
            # Health Bar Calculation
            if needed > 0:
                progress = min(1.0, stock / needed)
            else:
                progress = 1.0 if stock > 0 else 0.0
            
            st.progress(progress)
            
            # Text Status
            # Green if we have enough, Red if we are short
            color = "green" if stock >= needed else "red"
            st.markdown(f"Cooler: :{color}[**{stock}**] / Needed: **{needed}**")
            
            # Surplus/Deficit Indicator
            diff = stock - needed
            if diff > 0:
                st.caption(f"(+{diff} surplus)")
            elif diff < 0:
                st.caption(f"({diff} deficit)")

        with c_act:
            # Split Make actions
            b1, b2 = st.columns([2, 1], gap="small")
            with b1:
                st.button(
                    "➕", 
                    key=f"make_stock_{row['product_id']}", 
                    width="stretch",
                    on_click=handle_make_stock,
                    args=(int(row['product_id']), row['Product'])
                )
            with b2:
                if st.button("📝", key=f"adj_stock_{row['product_id']}", help="Make with Adjustments", width="stretch"):
                    trigger_adjustment_modal(int(row['product_id']), row['Product'])
            
            # Undo Button (Removes from Stock)
            st.button(
                "➖", 
                key=f"undo_stock_{row['product_id']}", 
                width="stretch",
                on_click=handle_undo_stock,
                args=(int(row['product_id']), row['Product'])
            )
        
        recipe_display.render_recipe_expander(row['product_id'], recipes_df)