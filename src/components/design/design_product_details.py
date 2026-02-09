import streamlit as st
import datetime
from src.utils import db_utils, settings_utils

def render(container, inventory_df):
    """Renders the Product Details form (Name, Image, Pricing) in the provided container."""
    
    # --- AUTO-LOAD LOGIC (Moved to top) ---
    # We must check and update session state BEFORE widgets are instantiated to avoid StreamlitAPIException.
    current_name = st.session_state.get("prod_name_input", "")
    
    if 'last_loaded_prod_name' not in st.session_state:
        st.session_state.last_loaded_prod_name = ""
        
    # Check if name changed
    if current_name != st.session_state.last_loaded_prod_name:
        if current_name:
            # Try to fetch details
            details = db_utils.get_product_details(current_name)
            if details:
                # Found existing product! Load it.
                st.session_state.new_recipe = []
                for ing in details['recipe']:
                    # Find cost from inventory_df
                    cost = 0.0
                    if not inventory_df.empty:
                        match = inventory_df[inventory_df['item_id'] == ing['item_id']]
                        if not match.empty:
                            cost = match.iloc[0]['unit_cost']
                    
                    st.session_state.new_recipe.append({
                        'id': ing['item_id'],
                        'name': ing['name'],
                        'qty': ing['qty'],
                        'cost': cost,
                        'type': ing.get('type', 'Specific'),
                        'val': ing.get('val'),
                        'note': ing.get('note')
                    })
                
                # Update Pricing
                st.session_state.final_price_input = float(details['price'])
                st.session_state.last_suggested_price = float(details['price'])
                
                # Set Editing Context
                st.session_state.editing_product_id = details['product_id']
                st.session_state.editing_product_original_name = details['name']
                
                # Load Category
                if details.get('category'):
                    st.session_state.prod_type_input = details['category']
                
                st.toast(f"Loaded recipe for '{details['name']}'", icon="📖")
            else:
                # Name changed to something new -> Clear ID (New Product Mode)
                st.session_state.pop('editing_product_id', None)
                st.session_state.pop('editing_product_original_name', None)
        else:
            # Name cleared -> Clear ID
            st.session_state.pop('editing_product_id', None)
            st.session_state.pop('editing_product_original_name', None)
        
        st.session_state.last_loaded_prod_name = current_name

    with container:
        st.subheader("1. Product Details")
        prod_type = st.radio("Product Type", ["Standard", "One-Off"], horizontal=True, help="One-Off items auto-archive when finished.", key="prod_type_input")
        
        goal_date = None
        goal_qty = 0
        
        if prod_type == "One-Off":
            create_goal = st.checkbox("Schedule Production Immediately?", value=True, key="create_goal_input")
            if create_goal:
                col_d, col_q = st.columns(2)
                with col_d:
                    goal_date = st.date_input("Due Date", value=datetime.date.today() + datetime.timedelta(days=1), min_value=datetime.date.today(), key="goal_date_input")
                with col_q:
                    goal_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key="goal_qty_input")

        prod_name = st.text_input("Product Name", placeholder="e.g., Summer Breeze", key="prod_name_input")
        
        
        # Show ID if available
        if st.session_state.get('editing_product_id'):
             st.caption(f"Recipe ID: {st.session_state.editing_product_id}")

        # Show existing image if it exists so user knows they don't need to re-upload
        if prod_name:
            current_img = db_utils.get_product_image(prod_name)
            if current_img:
                st.image(current_img, caption="Current Image (Will be kept if no new upload)", width=150)

        uploaded_file = st.file_uploader("Upload Thumbnail", type=['png', 'jpg', 'jpeg'], key=f"uploader_{st.session_state.uploader_key}")
        
        st.divider()
        
        # --- COSTING FORMULA (HIGHLIGHTED FOR ADJUSTMENT) ---
        st.subheader("3. Pricing")
        
        # Load Settings
        settings = settings_utils.load_settings()

        # Calculate Costs
        cogs = sum(item['cost'] * item['qty'] for item in st.session_state.new_recipe)
        
        suggested_price, total_cost, breakdown, markup_val = settings_utils.calculate_price(cogs, settings)

        # Auto-update input when recipe changes
        if 'last_suggested_price' not in st.session_state:
            st.session_state.last_suggested_price = 0.0
            
        if abs(suggested_price - st.session_state.last_suggested_price) > 0.001:
            st.session_state.final_price_input = float(f"{suggested_price:.2f}")
            st.session_state.last_suggested_price = suggested_price

        st.markdown(f"**Cost of Goods (COGS):** `${cogs:.2f}`")
        for line in breakdown:
            st.markdown(f"**{line}**")
        st.markdown(f"**Total Cost:** `${total_cost:.2f}`")
        
        st.markdown(f"### **Formula Suggested:** `${suggested_price:.2f}`")
        st.caption(f"(Based on {markup_val}x markup)")
        
        st.number_input("Final Selling Price ($)", min_value=0.0, step=1.0, key="final_price_input")
        st.checkbox("Rollover Stock Count?", value=True, key="rollover_stock_input", help="If checked, existing stock count will be moved to the new version.")
        st.checkbox("Migrate Unfulfilled Goals?", value=True, key="migrate_goals_input", help="If checked, pending production goals will be moved to the new version.")

        save_clicked = st.button("💾 Save / Update Product", type="primary", width="stretch")
        
        return uploaded_file, save_clicked, prod_type, goal_date, goal_qty