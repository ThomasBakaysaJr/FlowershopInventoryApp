import streamlit as st
import pandas as pd
import io
from src.utils import db_utils
from src.utils.constants import variant_badge, FRAGMENT_REFRESH_SECONDS
from src.components import date_selector
from src.components.workspace_dashboard.shared_modals import generic_selection_modal


def handle_log_production(goal_id, product_name):
    p_id = db_utils.get_goal_product_id(goal_id)
    if not p_id:
        return

    reqs = db_utils.get_recipe_requirements(p_id)

    if not reqs['has_generics']:
        if db_utils.log_production(int(goal_id)) > 0:
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


def handle_undo_production(goal_id, product_name):
    if db_utils.undo_production(int(goal_id)):
        st.session_state['weekly_dash_toast'] = (f"Undid 1 {product_name}", "↩️")


@st.fragment(run_every=FRAGMENT_REFRESH_SECONDS["weekly_dashboard"])
def render():
    if 'weekly_dash_toast' in st.session_state:
        msg, icon = st.session_state.pop('weekly_dash_toast')
        st.toast(msg, icon=icon)

    st.subheader("Production Goals")

    start_date, end_date = date_selector.render("weekly_dash")
    if start_date > end_date:
        return

    c_search, c_clear = st.columns([6, 1], vertical_alignment="bottom")
    with c_search:
        search_term = st.text_input(
            "Search Goals",
            placeholder="Filter by product name...",
            label_visibility="collapsed",
            key="weekly_dash_search",
        )
    with c_clear:
        if st.button("Clear", key="clear_weekly_search", help="Clear Search", width="stretch"):
            st.session_state.weekly_dash_search = ""
            st.rerun()

    st.divider()

    goals_df = db_utils.get_production_goals_range(start_date, end_date)
    recipes_df = db_utils.get_all_recipes()

    if search_term:
        goals_df = db_utils.filter_dataframe_by_terms(goals_df, 'Product', search_term)

    if goals_df.empty:
        st.info("No production goals set for this period.")
        return

    goals_df['due_date'] = pd.to_datetime(goals_df['due_date'])
    # time_rank is already set by get_production_goals_range via normalize_time_slots
    goals_df = goals_df.sort_values(by=['due_date', 'time_rank', 'Product', 'goal_id'])

    for date_val in goals_df['due_date'].dt.date.unique():
        st.subheader(date_val.strftime('%A, %b %d'))
        day_data = goals_df[goals_df['due_date'].dt.date == date_val].reset_index(drop=True)
        render_grid(day_data, recipes_df, key_suffix=f"_{date_val}")


def render_grid(week_data, recipes_df, key_suffix=""):
    week_data = week_data.sort_values(by=['Product', 'time_rank'])
    unique_products = week_data['product_id'].unique()

    for i in range(0, len(unique_products), 2):
        grid_cols = st.columns(2)
        for j in range(2):
            if i + j < len(unique_products):
                p_id = unique_products[i + j]
                group_df = week_data[week_data['product_id'] == p_id]
                with grid_cols[j]:
                    render_grouped_card(group_df, recipes_df, key_suffix)


def render_grouped_card(group_df, recipes_df, key_suffix):
    first_row = group_df.iloc[0]
    product_name = first_row['Product']
    product_id = first_row['product_id']

    with st.container(border=True):
        display_name = f"[{product_id}] {product_name}"
        if first_row['active'] == 0:
            display_name = f"⚠️ {display_name}"

        v_type = first_row.get('variant_type', 'STD')
        st.markdown(f"**{display_name}** {variant_badge(v_type)}")

        st.divider()

        for slot in group_df['time_slot'].unique():
            slot_df = group_df[group_df['time_slot'] == slot]
            qty_ordered = slot_df['qty_ordered'].sum()
            qty_fulfilled = slot_df['qty_fulfilled'].sum()
            needed = qty_ordered - qty_fulfilled

            # Pick the target goal_id for the action buttons:
            # prefer the first pending goal; if everything's done, target the last (for Undo).
            pending_goals = slot_df[slot_df['qty_fulfilled'] < slot_df['qty_ordered']]
            target_goal = pending_goals.iloc[0] if not pending_goals.empty else slot_df.iloc[-1]
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
                    # Only offer Undo if at least one unit has actually been logged.
                    undo_candidates = slot_df[slot_df['qty_fulfilled'] > 0]
                    if not undo_candidates.empty:
                        undo_goal = undo_candidates.iloc[-1]
                        if st.button(
                            "↩️",
                            key=f"undo_slot_{product_id}_{slot}{key_suffix}",
                            help="Undo last item",
                        ):
                            handle_undo_production(undo_goal['goal_id'], product_name)
                            st.rerun()
                else:
                    st.button(
                        "➕ Make",
                        key=f"make_slot_{product_id}_{slot}{key_suffix}",
                        on_click=handle_log_production,
                        args=(goal_id, product_name),
                    )

        with st.expander("🌿 Recipe & Image"):
            if 'image_data' in first_row and pd.notna(first_row['image_data']):
                st.image(io.BytesIO(first_row['image_data']), width=200)

            r_data = recipes_df[recipes_df['product_id'] == product_id]
            if not r_data.empty:
                st.dataframe(
                    r_data[['Ingredient', 'Qty', 'Note']],
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.caption("No ingredients listed.")
