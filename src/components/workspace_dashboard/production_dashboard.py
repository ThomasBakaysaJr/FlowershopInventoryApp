import streamlit as st
import pandas as pd
import io
from src.utils import db_utils
from src.components import date_selector
from src.components.workspace_dashboard.shared_modals import generic_selection_modal, adjustment_modal

def handle_make_stock(product_id, product_name):
    """Callback to increase stock."""
    reqs = db_utils.get_recipe_requirements(product_id)

    if not reqs['has_generics']:
        if db_utils.produce_stock(product_id):
            st.session_state['prod_dash_toast'] = (f"Made 1 {product_name}", "📦")
    else:
        generic_selection_modal(
            key_prefix=f"stock_{product_id}",
            display_name=product_name,
            generic_reqs=reqs['generic_items'],
            on_confirm=lambda subs: db_utils.produce_stock(product_id, substitutions=subs),
            toast_key='prod_dash_toast',
            toast_success_msg=f"Made 1 {product_name} with details!",
        )

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
    
    # --- Date Selection ---
    start_date, end_date = date_selector.render("prod_dash")
    
    if start_date > end_date:
        return

    # Search Bar & Filter
    c_search, c_filter, c_clear = st.columns([5, 2, 1], vertical_alignment="bottom")
    with c_search:
        search_term = st.text_input("Search", placeholder="Filter by product name...", label_visibility="collapsed", key="prod_dash_search")
    with c_filter:
        show_all = st.checkbox("Show All Items", value=False, help="Uncheck to see only items with a deficit.")
    with c_clear:
        if st.button("Clear", key="clear_prod_dash_search", help="Clear Search", width="stretch"):
            st.session_state.prod_dash_search = ""
            st.rerun()

    st.divider()

    # --- Fetch Data ---
    df = db_utils.get_production_requirements(st.session_state.prod_dash_start, st.session_state.prod_dash_end)
    recipes_df = db_utils.get_all_recipes()
    
    # Apply Search Filter
    if search_term:
        df = db_utils.filter_dataframe_by_terms(df, 'Product', search_term)
    
    # Apply "Needed Only" Filter (Default)
    # If searching, we ignore this filter to show what the user is looking for.
    elif not show_all:
        df = df[df['stock_on_hand'] < df['required_qty']]

    if df.empty:
        st.info("No active products or requirements found for this period.")
        return

    # --- Sorting Logic ---
    # Sort by Product Family (Base Name) then Variant (STD -> DLX -> PRM)
    df['sort_rank'] = df['variant_type'].map({'STD': 0, 'DLX': 1, 'PRM': 2}).fillna(3)
    df['sort_base'] = df['Product'].str.replace(r'\s+(Standard|Deluxe|Premium)$', '', regex=True)

    df = df.sort_values(by=['sort_base', 'sort_rank'], ascending=[True, True])

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
        # Layout: Info (Name, Stats, Bar) | Actions (+/-)
        c_info, c_act = st.columns([3, 1], vertical_alignment="center")

        with c_info:
            # Name & ID
            name = f"[{row['product_id']}] {row['Product']}"
            if row['active'] == 0:
                name = "⚠️ " + name
            
            # Variant Badge
            v_type = row.get('variant_type', 'STD')
            variant_str = ":green[**[STD]**]"
            if v_type == 'DLX':
                variant_str = ":blue[**[DLX]**]"
            elif v_type == 'PRM':
                variant_str = ":red[**[PRM]**]"

            st.markdown(f"**{name}** {variant_str}")

            if pd.notna(row['note']) and row['note']:
                st.caption(f"📝 {row['note']}")
            
            # Stats
            stock = row['stock_on_hand']
            needed = row['required_qty']
            
            # Health Bar Calculation
            if needed > 0:
                progress = max(0.0, min(1.0, stock / needed))
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
                    adjustment_modal(
                        key_prefix=f"stock_{int(row['product_id'])}",
                        display_name=row['Product'],
                        product_name=row['Product'],
                        on_confirm=lambda subs: db_utils.produce_stock(int(row['product_id']), substitutions=subs, ignore_recipe=True),
                        toast_key='prod_dash_toast',
                        toast_success_msg=f"Made 1 {row['Product']} (Custom)",
                    )
            
            # Undo Button (Removes from Stock)
            st.button(
                "➖", 
                key=f"undo_stock_{row['product_id']}", 
                width="stretch",
                disabled=stock <= 0,
                on_click=handle_undo_stock,
                args=(int(row['product_id']), row['Product'])
            )
        
        with st.expander("🌿 Recipe & Image"):
            if 'image_data' in row and pd.notna(row['image_data']):
                st.image(io.BytesIO(row['image_data']), width=200)
            
            # Filter for recipe
            r_data = recipes_df[recipes_df['product_id'] == row['product_id']]
            if not r_data.empty:
                st.dataframe(
                    r_data[['Ingredient', 'Qty', 'Note']], 
                    hide_index=True, 
                    width="stretch"
                )
            else:
                st.caption("No ingredients listed.")