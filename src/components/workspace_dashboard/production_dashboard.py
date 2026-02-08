import streamlit as st
import pandas as pd
import datetime
from src.utils import db_utils

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
            st.error(f"No {category} in stock!")
            valid_form = False
            continue

        total_allocated = 0
        
        # Dynamic inputs for allocation
        for _, item in inventory_df.iterrows():
            cols = st.columns([3, 1])
            with cols[0]:
                st.write(f"{item['name']} (Stock: {item['count_on_hand']})")
            with cols[1]:
                max_val = int(item['count_on_hand']) if pd.notna(item['count_on_hand']) else 0
                allocated = st.number_input(
                    "Use", 
                    min_value=0, 
                    max_value=max_val,
                    step=1,
                    key=f"stock_alloc_{product_id}_{item['item_id']}",
                    label_visibility="collapsed"
                )
            
            if allocated > 0:
                substitutions_to_make.append((item['item_id'], allocated))
                total_allocated += allocated
        
        if total_allocated != needed:
            st.warning(f"Selected {total_allocated} / {needed} {category}s.")
            valid_form = False
        else:
            st.success(f"✅ {category} requirements met.")

    st.divider()
    if st.button("Confirm Production", type="primary", disabled=not valid_form, width='stretch'):
        if db_utils.produce_stock(product_id, substitutions=substitutions_to_make):
            st.session_state['prod_dash_toast'] = (f"Made 1 {product_name} with details!", "📦")
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

    st.divider()

    # --- Fetch Data ---
    df = db_utils.get_production_requirements(st.session_state.prod_dash_start, st.session_state.prod_dash_end)

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
                    render_card(row)

def render_card(row):
    with st.container(border=True):
        # Layout: Image | Info (Name, Stats, Bar) | Actions (+/-)
        c_img, c_info, c_act = st.columns([1, 2.5, 0.8], vertical_alignment="center")
        
        with c_img:
            if pd.notna(row['image_data']):
                st.image(row['image_data'], width="stretch")
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
            # Make Button (Adds to Stock)
            st.button(
                "➕", 
                key=f"make_stock_{row['product_id']}", 
                width="stretch",
                on_click=handle_make_stock,
                args=(int(row['product_id']), row['Product'])
            )
            
            # Undo Button (Removes from Stock)
            st.button(
                "➖", 
                key=f"undo_stock_{row['product_id']}", 
                width="stretch",
                on_click=handle_undo_stock,
                args=(int(row['product_id']), row['Product'])
            )