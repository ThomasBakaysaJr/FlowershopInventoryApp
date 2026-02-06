import streamlit as st
from src.utils import db_utils

def render(container):
    """Renders the Product Details form (Name, Image, Pricing) in the provided container."""
    with container:
        st.subheader("1. Product Details")
        prod_name = st.text_input("Product Name", placeholder="e.g., Summer Breeze", key="prod_name_input")
        
        # Show existing image if it exists so user knows they don't need to re-upload
        if prod_name:
            current_img = db_utils.get_product_image(prod_name)
            if current_img:
                st.image(current_img, caption="Current Image (Will be kept if no new upload)", width=150)

        uploaded_file = st.file_uploader("Upload Thumbnail", type=['png', 'jpg', 'jpeg'], key=f"uploader_{st.session_state.uploader_key}")
        
        st.divider()
        
        # --- COSTING FORMULA (HIGHLIGHTED FOR ADJUSTMENT) ---
        st.subheader("3. Pricing")
        
        # >>> FORMULA VARIABLES <<<
        LABOR_RATE = 0.20  # 20% of COGS
        MARKUP = 3.5       # 3.5x Markup on Total Cost
        # >>> END FORMULA <<<

        # Calculate Costs
        cogs = sum(item['cost'] * item['qty'] for item in st.session_state.new_recipe)
        labor_cost = cogs * LABOR_RATE
        total_cost = cogs + labor_cost
        suggested_price = total_cost * MARKUP

        # Auto-update input when recipe changes
        if 'last_suggested_price' not in st.session_state:
            st.session_state.last_suggested_price = 0.0
            
        if abs(suggested_price - st.session_state.last_suggested_price) > 0.001:
            st.session_state.final_price_input = float(f"{suggested_price:.2f}")
            st.session_state.last_suggested_price = suggested_price

        st.markdown(f"**Cost of Goods (COGS):** `${cogs:.2f}`")
        st.markdown(f"**Labor ({int(LABOR_RATE*100)}%):** `${labor_cost:.2f}`")
        st.markdown(f"**Total Cost:** `${total_cost:.2f}`")
        
        st.markdown(f"### **Formula Suggested:** `${suggested_price:.2f}`")
        st.caption(f"(Based on {MARKUP}x markup)")
        
        st.number_input("Final Selling Price ($)", min_value=0.0, step=1.0, key="final_price_input")

        save_clicked = st.button("💾 Save / Update Product", type="primary", width="stretch")
        
        return uploaded_file, save_clicked