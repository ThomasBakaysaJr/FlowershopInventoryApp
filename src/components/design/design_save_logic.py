import streamlit as st
from src.utils import db_utils, utils

def execute_save(prod_name, final_price, uploaded_file, recipe_items, target_id=None, rollover_stock=True, category="Standard", migrate_goals=True, goal_date=None, goal_qty=0):
    """Core logic to save or update a product. Returns True if successful."""
    img_bytes = None
    if uploaded_file:
        img_bytes = utils.process_image(uploaded_file)
        if img_bytes is None:
            st.error("Error processing image. Please check the file format.")
            return False

    db_items = [(int(x['id']), int(x['qty'])) for x in recipe_items]

    success = False
    if target_id:
        # Update existing (or overwrite target)
        if db_utils.update_product_recipe(target_id, prod_name, db_items, img_bytes, final_price, rollover_stock, category, migrate_goals, goal_date, goal_qty):
            st.toast(f"Updated '{prod_name}'!", icon="💾")
            success = True
    else:
        # Create new
        if db_utils.create_new_product(prod_name, final_price, img_bytes, db_items, category, goal_date, goal_qty):
            st.toast(f"Successfully created '{prod_name}'!", icon="✨")
            success = True
    
    if success:
        st.session_state.confirm_overwrite = False
        st.session_state.should_clear_input = True
        
        # Clear specific edit context immediately to prevent ghost state in next run
        st.session_state.pop('editing_product_id', None)
        st.session_state.pop('editing_product_original_name', None)
        
        # Auto-navigate to Recipe Book
        # Use pending state to avoid StreamlitAPIException (modifying key after widget instantiation)
        st.session_state.pending_nav_design = "📖 Recipe Book"
        
        st.rerun()
    else:
        st.error("Failed to save product. Check database connection.")
    
    return success

def handle_save_click(prod_name, final_price, uploaded_file, recipe_items, rollover_stock=True, category="Standard", migrate_goals=True, goal_date=None, goal_qty=0):
    """Handles the initial save button click, checking for collisions."""
    if not prod_name or not recipe_items:
        st.warning("Please provide a name and at least one ingredient.")
        return

    original_name = st.session_state.get('editing_product_original_name')
    original_id = st.session_state.get('editing_product_id')
    
    # Check for Collision
    collision = False
    if original_name:
        # Edit Mode: Collision only if renaming to an existing product
        if prod_name.lower() != original_name.lower() and db_utils.check_product_exists(prod_name):
            collision = True
    else:
        # Create Mode: Collision if product exists
        if db_utils.check_product_exists(prod_name):
            collision = True
    
    # LOGIC DECISION:
    # 1. If it's a collision (Rename to existing OR Create existing), force confirm.
    # 2. If it's a standard edit (original_id exists, no collision), save immediately.
    # 3. If it's a standard create (no original_id, no collision), save immediately.
    
    if collision:
        st.session_state.confirm_overwrite = True
        st.rerun()
    elif original_id:
        # Standard Update
        execute_save(prod_name, final_price, uploaded_file, recipe_items, target_id=original_id, rollover_stock=rollover_stock, category=category, migrate_goals=migrate_goals, goal_date=goal_date, goal_qty=goal_qty)
    else:
        # Standard Create
        execute_save(prod_name, final_price, uploaded_file, recipe_items, category=category, goal_date=goal_date, goal_qty=goal_qty)

def render_overwrite_dialog(prod_name, final_price, uploaded_file, recipe_items, rollover_stock=True, category="Standard", migrate_goals=True, goal_date=None, goal_qty=0):
    """Renders the confirmation dialog if collision detected."""
    if st.session_state.get('confirm_overwrite'):
        st.warning(f"Product '{prod_name}' already exists. Overwrite?")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("Yes, Overwrite"):
                # Determine Target ID
                target_id = st.session_state.get('editing_product_id')
                
                if not target_id:
                    # Create Mode overwriting existing: Fetch ID of the existing product
                    details = db_utils.get_product_details(prod_name)
                    if details:
                        target_id = details['product_id']
                
                # Execute with the resolved target_id
                execute_save(prod_name, final_price, uploaded_file, recipe_items, target_id=target_id, rollover_stock=rollover_stock, category=category, migrate_goals=migrate_goals, goal_date=goal_date, goal_qty=goal_qty)
                
        with col_no:
            if st.button("Cancel"):
                st.session_state.confirm_overwrite = False
                st.rerun()