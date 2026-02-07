import streamlit as st
from src.components import recipe_display
from . import dashboard_weekly

def render_designer_dashboard():
    dashboard_weekly.render()

    st.divider()
    recipe_display.render_recipe_display(allow_edit=False)