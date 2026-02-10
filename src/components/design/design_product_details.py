import streamlit as st
import io
from src.utils import db_utils
from . import design_recipe_builder

def render_variant_tab(v_type, label, variant_map, group_id, base_name, category):
    # Check if variant exists
    if v_type in variant_map:
        v_summary = variant_map[v_type]
        v_details = db_utils.get_product_details(v_summary['name'])
        
        if not v_details:
            st.error(f"Could not load details for {label}")
            return

        p_id = v_details['product_id']
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            render_info_form(p_id, v_details, label, group_id)
        
        with col2:
            design_recipe_builder.render_recipe_editor(p_id, v_details, group_id, v_type, variant_map)

    else:
        render_create_button(v_type, label, base_name, group_id, category)

def render_info_form(p_id, v_details, label, group_id):
    # Image
    if v_details['image_data']:
        st.image(io.BytesIO(v_details['image_data']), caption=f"{label} Preview", width="stretch")
    else:
        st.info("No image available")
    
    new_img = st.file_uploader(f"Update {label} Image", type=['png', 'jpg', 'jpeg'], key=f"img_{p_id}")
    
    with st.form(key=f"form_info_{p_id}"):
        new_name = st.text_input("Display Name", value=v_details['name'])
        new_price = st.number_input("Selling Price ($)", value=float(v_details['price']), step=0.5)
        new_note = st.text_area("Notes", value=v_details['note'] if v_details['note'] else "")
        
        if st.form_submit_button("💾 Save Info"):
            img_bytes = new_img.getvalue() if new_img else None
            
            # Use recipe from session state if available (edited), otherwise use DB version
            final_recipe = st.session_state.get(f"recipe_state_{p_id}", v_details['recipe'])
            
            success = db_utils.update_product_recipe(
                current_product_id=p_id,
                new_name=new_name,
                recipe_items=final_recipe,
                image_bytes=img_bytes,
                new_price=new_price,
                note=new_note,
                variant_group_id=group_id,
                category=v_details['category']
            )
            if success:
                # Clear dirty state so next load fetches fresh from DB
                if f"recipe_state_{p_id}" in st.session_state:
                    del st.session_state[f"recipe_state_{p_id}"]
                st.success("Updated!")
                st.rerun()

    # Duplicate Feature
    if st.button("©️ Duplicate as New Product", key=f"dup_{p_id}", help="Creates a new Product Family based on this variant."):
        new_name = f"{v_details['name']} (Copy)"
        
        # Use recipe from session state if available (edited), otherwise use DB version
        final_recipe = st.session_state.get(f"recipe_state_{p_id}", v_details['recipe'])
        
        success = db_utils.create_new_product(
            name=new_name,
            selling_price=v_details['price'],
            image_bytes=v_details['image_data'],
            recipe_items=final_recipe,
            category=v_details['category'],
            note=v_details['note'],
            variant_type="STD" # Start as Standard of new family
        )
        
        if success:
            st.success(f"Created {new_name}!")
            # Trigger edit mode for the new product
            st.session_state['design_edit_name'] = new_name
            st.rerun()

def render_create_button(v_type, label, base_name, group_id, category):
    st.info(f"No {label} version exists for this product.")
    if st.button(f"➕ Create {label} Version", key=f"create_{v_type}"):
        # Strip existing suffix if present to get clean base
        clean_base = base_name
        for s in ['Standard', 'Deluxe', 'Premium']:
            if clean_base.endswith(s):
                clean_base = clean_base.replace(s, "").strip()
                break
        
        new_name = f"{clean_base} {label}"
        
        success = db_utils.create_new_product(
            name=new_name,
            selling_price=0.0,
            image_bytes=None,
            recipe_items=[],
            category=category,
            variant_group_id=group_id,
            variant_type=v_type
        )
        if success:
            st.success(f"Created {new_name}!")
            st.rerun()