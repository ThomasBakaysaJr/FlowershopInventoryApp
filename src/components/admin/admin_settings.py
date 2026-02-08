import streamlit as st
import pandas as pd
from src.utils import settings_utils

def render_settings_panel():
    st.header("⚙️ System Settings")
    
    settings = settings_utils.load_settings()
    formula = settings.get('cost_formula', {})
    
    st.subheader("Pricing Formula")
    st.caption("Configure how suggested prices are calculated in the Design Studio.")
    
    # 1. Additives Section
    st.markdown("#### 1. Pre-Markup Additives")
    st.caption("Costs added to the base ingredients (COGS) before markup (e.g., Labor, Prep Fees).")
    
    current_additives = formula.get('additives', [])
    df_additives = pd.DataFrame(current_additives)
    
    # Ensure columns exist if empty
    if df_additives.empty:
        df_additives = pd.DataFrame(columns=["name", "type", "value"])
    
    edited_additives = st.data_editor(
        df_additives,
        column_config={
            "name": st.column_config.TextColumn("Name", required=True),
            "type": st.column_config.SelectboxColumn("Type", options=["Percentage", "Fixed ($)"], required=True),
            "value": st.column_config.NumberColumn("Value", min_value=0.0, step=0.1, required=True, help="Enter 20 for 20%")
        },
        num_rows="dynamic",
        width="stretch",
        key="settings_additives_editor"
    )
    
    # 2. Markup Section
    st.markdown("#### 2. Global Markup")
    st.caption("Multiplier applied to the Total Cost (COGS + Additives).")
    
    current_markup = formula.get('markup', 3.5)
    new_markup = st.number_input("Markup Multiplier", min_value=1.0, value=float(current_markup), step=0.1)
    
    st.divider()
    
    if st.button("💾 Save Settings", type="primary", width="stretch"):
        # Reconstruct settings object
        new_settings = settings.copy()
        
        # Clean up additives dataframe to list of dicts
        cleaned_additives = []
        for _, row in edited_additives.iterrows():
            if row['name']: # Filter empty rows if any
                cleaned_additives.append({
                    "name": row['name'],
                    "type": row['type'],
                    "value": float(row['value'])
                })
        
        new_settings['cost_formula'] = {
            "additives": cleaned_additives,
            "markup": new_markup
        }
        
        if settings_utils.save_settings(new_settings):
            st.success("Settings saved successfully!")
            st.rerun()
        else:
            st.error("Failed to save settings.")