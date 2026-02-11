import streamlit as st
import pandas as pd
import datetime
import math
from src.utils import db_utils
from src.components import date_selector

def render_forecaster():
    st.header("🔮 Production Forecaster")
    st.caption("Simulate production scenarios to see inventory requirements.")

    # 1. Date Selection
    start_date, end_date = date_selector.render("fc")
    
    if start_date > end_date:
        return

    # 2. Reset Logic
    if "fc_reset_counter" not in st.session_state:
        st.session_state.fc_reset_counter = 0

    if st.button("🔄 Reset to Actuals", help="Reloads the table with actual values from the database.", width="stretch"):
        st.session_state.fc_reset_counter += 1
        st.rerun()

    # 3. Fetch Data
    # Get base production numbers
    initial_df = db_utils.get_forecast_initial_data(start_date, end_date)
    
    if initial_df.empty:
        st.info("No products found.")
        return

    # Mark archived products
    initial_df['Product'] = initial_df.apply(
        lambda x: f"⚠️ {x['Product']}" if x['active'] == 0 else x['Product'], 
        axis=1
    )

    # 4. Editable Table (Production Inputs)
    st.subheader("1. Production Scenarios")
    edited_df = st.data_editor(
        initial_df,
        column_config={
            "product_id": st.column_config.NumberColumn("ID", disabled=True),
            "Product": st.column_config.TextColumn("Recipe Name", disabled=True),
            "active": None, # Hide active column
            "Expected": st.column_config.NumberColumn("Count to Make", min_value=0, step=1, required=True)
        },
        hide_index=True,
        width="stretch",
        key=f"fc_editor_{st.session_state.fc_reset_counter}"
    )

    # 5. Calculate Ingredients
    st.divider()
    st.subheader("2. Inventory Requirements")

    # Fetch all recipes and inventory data
    recipes_df = db_utils.get_all_recipes()
    inventory_df = db_utils.get_inventory()

    if recipes_df.empty or inventory_df.empty:
        st.warning("Insufficient data to calculate requirements.")
        return

    # Calculation Loop
    total_needs = {} # item_id -> qty needed

    for _, row in edited_df.iterrows():
        qty_to_make = row['Expected']
        if qty_to_make > 0:
            p_id = row['product_id']
            # Filter recipes for this product
            prod_recipe = recipes_df[recipes_df['product_id'] == p_id]
            
            for _, r_row in prod_recipe.iterrows():
                item_id = r_row['item_id']
                qty_needed = r_row['Qty']
                
                if pd.notna(item_id):
                    total_needs[item_id] = total_needs.get(item_id, 0) + (qty_needed * qty_to_make)

    # Build Results Table
    results = []
    for item_id, needed_qty in total_needs.items():
        inv_row = inventory_df[inventory_df['item_id'] == item_id]
        if not inv_row.empty:
            name = inv_row.iloc[0]['name']
            stock = inv_row.iloc[0]['count_on_hand']
            bundle_size = inv_row.iloc[0]['bundle_count']
            
            # Calculate Deficit
            # Note: Stock is in units (bundles), but recipe is usually in stems/singles?
            # Wait, usually inventory count_on_hand is physical units.
            # If recipe calls for 12 stems, and bundle is 25 stems.
            # We need to know if recipe qty is in stems or units.
            # Assuming recipe qty is raw units (e.g. stems) and inventory is packs.
            # Actually, standard practice: Inventory Count * Bundle Count = Total Stems Available.
            
            total_available_stems = stock * bundle_size
            net_need = needed_qty - total_available_stems
            
            deficit_stems = max(0, net_need)
            bundles_to_buy = math.ceil(deficit_stems / bundle_size) if deficit_stems > 0 else 0

            results.append({
                "Ingredient": name,
                "Total Needed": needed_qty,
                "Current Stock (Packs)": stock,
                "Bundle Size": bundle_size,
                "Deficit (Units)": deficit_stems,
                "To Buy (Packs)": bundles_to_buy
            })

    if results:
        res_df = pd.DataFrame(results)
        # Sort by To Buy (descending) then Name
        res_df = res_df.sort_values(by=['To Buy (Packs)', 'Ingredient'], ascending=[False, True])
        
        st.dataframe(
            res_df,
            hide_index=True,
            width="stretch",
            column_config={
                "To Buy (Packs)": st.column_config.NumberColumn("To Buy (Packs)", format="%d 📦")
            }
        )
        
        # Export Button
        csv = res_df.to_csv(index=False)
        st.download_button(
            label="🛒 Download Shopping List (.csv)",
            data=csv,
            file_name=f"shopping_list_{datetime.date.today()}.csv",
            mime="text/csv",
            type="primary",
            width="stretch"
        )
    else:
        st.info("No ingredients required for the selected production.")

    # --- Generic Forecast ---
    st.divider()
    st.subheader("🧩 Generic Category Forecast")
    st.caption("Buying guide for generic requirements (e.g. 'Any Rose').")
    
    generic_df = db_utils.get_forecast_generic_requirements(start_date, end_date)
    
    if not generic_df.empty:
        # Add a column for current stock of that category
        inventory_df = db_utils.get_inventory()
        
        def get_cat_stock(cat):
            if inventory_df.empty: return 0
            return inventory_df[inventory_df['sub_category'] == cat]['count_on_hand'].sum()
            
        generic_df['Current Category Stock'] = generic_df['Category'].apply(get_cat_stock)
        generic_df['Net Need'] = generic_df['Needed'] - generic_df['Current Category Stock']
        
        st.dataframe(generic_df, hide_index=True, width="stretch")
    else:
        st.info("No generic requirements found for this period.")