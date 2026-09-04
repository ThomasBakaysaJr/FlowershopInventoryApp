import pandas as pd
import streamlit as st

from src.utils import db_utils


@st.dialog("🌸 Select Flowers Used")
def generic_selection_modal(key_prefix, display_name, generic_reqs, on_confirm, toast_key, toast_success_msg):
    """
    Generic ingredient selection dialog for both stock and goal production.

    key_prefix:   caller-supplied string encoding context + entity ID so every
                  session state key is self-documenting, e.g.:
                    "stock_{product_id}"  — production dashboard
                    "goal_{goal_id}"      — weekly dashboard
    on_confirm:   callable(substitutions: list[tuple[int, int]]) -> bool
                  Caller binds the entity ID (product_id or goal_id) internally.
    """
    st.write(f"Making **{display_name}**. Please specify generic items used.")

    # Pass 1: read allocations from session state (set by previous render's widgets)
    substitutions_to_make = []
    validation_data = []

    for req in generic_reqs:
        category = req['category']
        # Show only tracked candidates — untracked items aren't deducted anyway,
        # so asking the user to pick between them has no effect.
        inventory_df = db_utils.get_items_by_category(category, tracked_only=True)

        current_allocated = 0
        if not inventory_df.empty:
            for _, item in inventory_df.iterrows():
                val = st.session_state.get(f"{key_prefix}_alloc_{item['item_id']}", 0)
                if val > 0:
                    substitutions_to_make.append((item['item_id'], val))
                    current_allocated += val

        validation_data.append({
            'req': req,
            'inventory_df': inventory_df,
            'allocated': current_allocated,
        })

    if st.button("Confirm Production", type="primary",
                 width='stretch', key=f"{key_prefix}_confirm"):
        if on_confirm(substitutions_to_make):
            st.session_state[toast_key] = (toast_success_msg, "📦")
            st.rerun()

    st.divider()

    search_term = st.text_input("Search Items", placeholder="Type to filter...",
                                label_visibility="collapsed", key=f"{key_prefix}_search")

    # Pass 2: render inputs
    for data in validation_data:
        req = data['req']
        inventory_df = data['inventory_df']
        allocated_qty = data['allocated']
        category = req['category']
        needed = req['qty']
        note = req.get('note')

        st.divider()
        label = f"**Required:** {needed} x {category}"
        if note:
            label += f" ({note})"
        st.markdown(label)

        if inventory_df.empty:
            st.warning(f"No items found for category '{category}' in inventory.")
            continue

        if search_term:
            def is_allocated(row, _pfx=key_prefix):
                return st.session_state.get(f"{_pfx}_alloc_{row['item_id']}", 0) > 0
            mask = (inventory_df['name'].str.contains(search_term, case=False, na=False) |
                    inventory_df.apply(is_allocated, axis=1))
            inventory_df = inventory_df[mask]
            if inventory_df.empty:
                st.caption(f"No items match '{search_term}' in {category}.")
                continue

        for _, item in inventory_df.iterrows():
            cols = st.columns([3, 1])
            with cols[0]:
                st.write(f"{item['name']} (Stock: {item['count_on_hand']})")
            with cols[1]:
                st.number_input("Use", min_value=0, step=1,
                                key=f"{key_prefix}_alloc_{item['item_id']}",
                                label_visibility="collapsed")

        if allocated_qty != needed:
            st.warning(f"Selected {allocated_qty} / {needed} {category}s.")
        else:
            st.success(f"✅ {category} requirements met.")


@st.dialog("📝 Adjust Recipe & Make")
def adjustment_modal(key_prefix, display_name, product_name, on_confirm, toast_key, toast_success_msg):
    """
    Recipe adjustment dialog for both stock and goal production.

    key_prefix:   caller-supplied string encoding context + entity ID, e.g.:
                    "stock_{product_id}"  — production dashboard
    product_name: passed to get_product_details() for recipe lookup.
    on_confirm:   callable(substitutions: list[tuple[int, int]]) -> bool
    """
    st.write(f"Adjusting ingredients for **{display_name}**.")

    details = db_utils.get_product_details(product_name)
    if not details:
        st.error("Could not load recipe.")
        return

    state_key = f"{key_prefix}_adj"
    if state_key not in st.session_state:
        st.session_state[state_key] = [
            {'item_id': item['item_id'], 'name': item['name'], 'qty': item['qty'], 'note': item.get('note')}
            for item in details['recipe']
            if item['item_id']  # skip generics — user must add them manually
        ]

    items = st.session_state[state_key]

    edited_df = st.data_editor(
        pd.DataFrame(items) if items else pd.DataFrame(columns=['item_id', 'name', 'qty', 'note']),
        column_config={
            "name": st.column_config.TextColumn("Ingredient", disabled=True),
            "note": st.column_config.TextColumn("Note"),
            "qty": st.column_config.NumberColumn("Qty Used", min_value=0, step=1),
            "item_id": None,
        },
        hide_index=True,
        width="stretch",
        key=f"{key_prefix}_editor",
    )

    st.divider()
    st.caption("Add Substitution / Extra Item")
    inventory_df = db_utils.get_inventory()
    if not inventory_df.empty:
        inv_options = inventory_df['name'].tolist()
        inv_map = dict(zip(inventory_df['name'], inventory_df['item_id'], strict=True))

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            new_item_name = st.selectbox("Item", options=inv_options,
                                         key=f"{key_prefix}_add_sel",
                                         label_visibility="collapsed",
                                         index=None, placeholder="Select item...")
        with c2:
            new_qty = st.number_input("Qty", min_value=1, value=1,
                                      key=f"{key_prefix}_add_qty",
                                      label_visibility="collapsed")
        with c3:
            if st.button("Add", key=f"{key_prefix}_add_btn", width="stretch"):
                if new_item_name:
                    new_id = inv_map[new_item_name]
                    existing = next((x for x in st.session_state[state_key] if x['item_id'] == new_id), None)
                    if existing:
                        existing['qty'] += new_qty
                    else:
                        st.session_state[state_key].append(
                            {'item_id': new_id, 'name': new_item_name, 'qty': new_qty, 'note': None}
                        )
                    st.rerun()

    st.divider()
    if st.button("Confirm & Make", type="primary", width='stretch'):
        final_items = [
            (row['item_id'], row['qty'])
            for _, row in edited_df.iterrows()
            if row['qty'] > 0
        ]
        if on_confirm(final_items):
            st.session_state[toast_key] = (toast_success_msg, "🛠️")
            del st.session_state[state_key]
            st.rerun()
