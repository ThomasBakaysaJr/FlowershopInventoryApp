import streamlit as st
from src.components import recipe_display
from . import dashboard_weekly
from . import goal_setter

def render_designer_dashboard():
    goal_setter.render_goal_setter()
    
    st.divider()
    
    dashboard_weekly.render()
    
    st.divider()
    recipe_display.render_recipe_display(allow_edit=False)