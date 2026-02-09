import streamlit as st
import datetime

def render(key_prefix: str):
    """
    Renders a standardized date selector with Quick Select buttons.
    
    Args:
        key_prefix (str): Unique prefix for session state keys (e.g., 'prod_dash').
        
    Returns:
        tuple: (start_date, end_date)
    """
    start_key = f"{key_prefix}_start"
    end_key = f"{key_prefix}_end"
    
    # Initialize defaults if missing
    if start_key not in st.session_state:
        st.session_state[start_key] = datetime.date.today()
    if end_key not in st.session_state:
        st.session_state[end_key] = datetime.date.today() + datetime.timedelta(days=7)

    # Layout: Quick Buttons (Left) | Date Pickers (Right)
    col_btns, col_dates = st.columns([1.5, 2], vertical_alignment="bottom")
    
    with col_btns:
        st.write("Quick Select:")
        b_col1, b_col2, b_col3 = st.columns(3, gap="small")
        
        if b_col1.button("Today", key=f"{key_prefix}_btn_today", width="stretch"):
            st.session_state[start_key] = datetime.date.today()
            st.session_state[end_key] = datetime.date.today()
            st.rerun()
            
        if b_col2.button("This Week", key=f"{key_prefix}_btn_week", width="stretch"):
            st.session_state[start_key] = datetime.date.today()
            st.session_state[end_key] = datetime.date.today() + datetime.timedelta(days=6)
            st.rerun()
            
        if b_col3.button("This Month", key=f"{key_prefix}_btn_month", width="stretch"):
            st.session_state[start_key] = datetime.date.today()
            st.session_state[end_key] = datetime.date.today() + datetime.timedelta(days=30)
            st.rerun()

    with col_dates:
        d_col1, d_col2 = st.columns(2)
        start_date = d_col1.date_input("Start", key=start_key)
        end_date = d_col2.date_input("End", key=end_key)

    if start_date > end_date:
        st.error("Start date must be before end date.")
    else:
        st.subheader(f"Displaying: {start_date.strftime('%b %d, %Y')} – {end_date.strftime('%b %d, %Y')}")
    
    return start_date, end_date