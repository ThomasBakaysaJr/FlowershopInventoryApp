import datetime
import io

import pandas as pd
import streamlit as st

from src.components import date_selector
from src.utils import db_utils
from src.utils.constants import FRAGMENT_REFRESH_SECONDS, variant_badge


@st.fragment(run_every=FRAGMENT_REFRESH_SECONDS["production_overview"])
def render():
    st.subheader("📊 Production Overview")
    st.caption("Read-only status across today's and upcoming production goals. Use *Upcoming Orders* to actually log production.")

    # Compute fixed summary windows regardless of the detailed-view selection below.
    _render_summary_header()

    st.divider()

    # Detailed view (user-selectable range)
    start_date, end_date = date_selector.render("prod_dash")
    if start_date > end_date:
        return

    goals_df = db_utils.get_production_goals_range(start_date, end_date)
    if goals_df.empty:
        st.info("No production goals in this range.")
        return

    # Sort by date then time slot (AM → PM → Any) then product name.
    # time_rank is already set by get_production_goals_range via normalize_time_slots.
    goals_df['due_date'] = pd.to_datetime(goals_df['due_date'])
    goals_df = goals_df.sort_values(by=['due_date', 'time_rank', 'Product', 'goal_id'])

    recipes_df = db_utils.get_all_recipes()

    for date_val in goals_df['due_date'].dt.date.unique():
        day_df = goals_df[goals_df['due_date'].dt.date == date_val]
        st.subheader(date_val.strftime('%A, %b %d'))
        _render_date_goals(day_df, recipes_df)


def _render_summary_header():
    """Shows today / this-week / month-to-date roll-ups in a single glance."""
    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=today.weekday())  # Monday
    week_end = week_start + datetime.timedelta(days=6)
    month_start = today.replace(day=1)

    today_df = db_utils.get_production_goals_range(today, today)
    week_df = db_utils.get_production_goals_range(week_start, week_end)
    month_df = db_utils.get_production_goals_range(month_start, today)

    def progress(df):
        if df.empty:
            return 0, 0, 0
        ordered = int(df['qty_ordered'].sum())
        fulfilled = int(df['qty_fulfilled'].sum())
        overage = int((df['qty_fulfilled'] - df['qty_ordered']).clip(lower=0).sum())
        return fulfilled, ordered, overage

    t_done, t_total, t_over = progress(today_df)
    w_done, w_total, w_over = progress(week_df)
    m_done, m_total, _ = progress(month_df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Today", f"{t_done} / {t_total}")
    c2.metric("This week", f"{w_done} / {w_total}")
    c3.metric("Month to date", f"{m_done} / {m_total}")
    c4.metric("Over-production (week)", f"{w_over}")


def _render_date_goals(day_df, recipes_df):
    """Renders a single date's goals as a read-only grid."""
    # Group by product so a product with multiple time slots shows as one card.
    unique_products = day_df['product_id'].unique()

    for i in range(0, len(unique_products), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j < len(unique_products):
                p_id = unique_products[i + j]
                group_df = day_df[day_df['product_id'] == p_id]
                with cols[j]:
                    _render_product_card(group_df, recipes_df)


def _render_product_card(group_df, recipes_df):
    first_row = group_df.iloc[0]
    product_name = first_row['Product']
    product_id = first_row['product_id']

    # If every slot for this product is complete, de-emphasize the card.
    all_done = bool((group_df['qty_fulfilled'] >= group_df['qty_ordered']).all())

    with st.container(border=True):
        display_name = f"[{product_id}] {product_name}"
        if first_row['active'] == 0:
            display_name = f"⚠️ {display_name}"

        v_type = first_row.get('variant_type', 'STD')
        badge = variant_badge(v_type)

        if all_done:
            st.markdown(f"✅ :grey[~~**{display_name}**~~] {badge}")
        else:
            st.markdown(f"**{display_name}** {badge}")

        if pd.notna(first_row.get('note')) and first_row.get('note'):
            st.caption(f"📝 {first_row['note']}")

        # One line per time slot.
        for slot in group_df['time_slot'].unique():
            slot_df = group_df[group_df['time_slot'] == slot]
            ordered = int(slot_df['qty_ordered'].sum())
            fulfilled = int(slot_df['qty_fulfilled'].sum())
            needed = max(0, ordered - fulfilled)
            over = max(0, fulfilled - ordered)

            if slot == 'AM':
                slot_label = ":blue[**AM**]"
            elif slot == 'PM':
                slot_label = ":orange[**PM**]"
            else:
                slot_label = "**Any**"

            if needed == 0 and over == 0:
                status = "✅ Done"
            elif needed == 0 and over > 0:
                status = f"✅ Done (+{over} excess)"
            else:
                progress_pct = fulfilled / ordered if ordered else 0.0
                status = f"**{fulfilled}** / {ordered}  ·  {progress_pct:.0%}"

            c_slot, c_stat = st.columns([1, 3], vertical_alignment="center")
            with c_slot:
                st.markdown(slot_label)
            with c_stat:
                st.markdown(status)

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
