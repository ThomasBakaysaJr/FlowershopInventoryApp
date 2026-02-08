2# AI CONTEXT: DEVELOPMENT RULES
# This file outlines the coding standards, database constraints, and best practices.
# For the project structure and file map, please refer to gemini.md.

# AI Development Guidelines for University Flowers Production Dashboard

## 1. Project Context
* **Goal:** A high-volume floral production dashboard for managing inventory and recipes.
* **Key Constraints:** * **Offline-First:** Must support "Clipboard Protocol" for text-based inventory updates (coolers have no Wi-Fi).
    * **Local Execution:** Runs locally on a host PC using Streamlit; no cloud dependencies.
    * **Data Integrity:** Use **Immutable Data** patterns for product history. Never overwrite active product recipes; always archive (soft delete) and create new versions.
* **Operational Model:** **"Cooler Buffer" Model**. Production fills "Cooler Stock" (`stock_on_hand`). Logistics fulfills orders (`qty_fulfilled`) from that stock.

## 2. Tech Stack & Standards
* **Language:** Python 3.10+
* **UI:** Streamlit (No raw HTML/JS unless absolutely necessary).
* **Database:** SQLite (`inventory.db`). 
    * *Rule:* Always use `product_id` or `item_id` for logic, never names (names are not unique).
* **Image Handling:** Pillow (PIL) for compressing thumbnails to JPEG BLOBs.

## 3. Database Architecture Rules
* **Soft Deletes:** Never run `DELETE FROM products`. Set `active = 0`.
* **Immutable Versioning:** When editing a recipe:
    1.  Set old `product_id` to `active = 0`.
    2.  Insert NEW product row with `active = 1`.
    3.  Link new recipe items to the NEW `product_id`.
    4.  **Stock Rollover:** Carry over `stock_on_hand` to the new version unless explicitly reset.
* **Logging:** All production actions must be recorded in `production_logs` with a timestamp.
* **Inventory Units:** Inventory `count_on_hand` represents physical units (packs/bunches). Total stem count = `count_on_hand * bundle_count`.
* **Fulfillment Logic:** `qty_ordered` is the demand. `qty_fulfilled` is the amount packed/shipped. `stock_on_hand` is the buffer.

## 4. Coding Style
* **Functions:** Type-hint all arguments and return values.
* **Error Handling:** Wrap all DB operations in `try/except sqlite3.Error`.
* **Testing:** Use `pytest`. Critical paths (Inventory Deduction, Undo Logic) must be tested.
* **Logging:** All logs should goto `logs/app.log`. Use logging instead of print statements, make sure all logs record the script they reside in, and when called, the function that called it.
* **Separation of Concerns:** Maintain good separation between UI and logic. Logic should go into respective scripts in `src/` (e.g. `src/utils/` or `src/logic/`) rather than embedding complex logic in UI files.


## 5. UI/UX Patterns
* **Workspace Structure:**
    * *Production Dashboard (Cooler View):* The "Make" view. Shows `stock_on_hand` vs. upcoming demand. Action: Build to Stock.
    * *Daily Logistics:* The "Ship" view. Shows Daily Orders. Action: Fulfill from Stock (`qty_fulfilled`).
    * *Update Work:* Ad-hoc production logging and history.
* **Buttons:** Action buttons (Make/Undo) should use `st.toast` for feedback and `st.rerun()` to refresh state after `0.25` seconds.
* **Recipe Visibility:**
    * *Workspace:* Active recipes + Archived (if in goals).
    * *Designer:* Active and Archived separated.
* **Data Entry:** Bulk edits (like Inventory) must include a "Review Changes" diff view before saving.

## 6. Database Connection & Error Handling Rules
* **The "Safe Pattern" Requirement:** SQLite relies on strict connection management to avoid "Database Locked" errors.
    * **Do not** rely solely on `with conn:` context managers (they commit transactions but do not guaranteed close connections).
    * **Do** use the explicit `try-except-finally` pattern for all database interactions.
* **Standard Write Pattern:**
    ```
    python
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # ... perform SQL operations ...
        conn.commit()
        return True
    except sqlite3.Error as e:
        # 1. Log the specific error
        logger.error(f"Function Name: Database error: {e}")
        # 2. Rollback to prevent data corruption
        conn.rollback()
        return False
    finally:
        # 3. Always close the connection to release the lock
        conn.close()
    ```

## 7. Streamlit Rules
* **Layout Arguments:** Use `width='stretch'` instead of `use_container_width=True` for all widgets (buttons, dataframes, editors) to ensure consistent layout and avoid deprecation warnings.

## 8. Business Logic Constraints
* **Clipboard Symmetry:** The "Download Inventory" format must match the "Clipboard Parser" logic. Updates rely on `item_id` and `bundle_count` to calculate `(count * bundle_count) - loss`.
* **Two-Step Production Flow:** Production and Fulfillment are decoupled.
    1.  **Production:** `produce_stock()` consumes raw inventory and increments `stock_on_hand`.
    2.  **Fulfillment:** `fulfill_goal()` consumes `stock_on_hand` and increments `qty_fulfilled`.
    *   *Constraint:* Goals cannot be fulfilled if `stock_on_hand <= 0`.

## 9. Reporting & Analytics
* **Success Metrics:** Performance is measured by `production_goals` data: `qty_ordered` (Demand) vs. `qty_fulfilled` (Success).
* **End Report:** Should list goals and calculate fulfillment rates to track operational success.

## 10. Concurrency & Auto-Updates
* **Lightweight Polling:** Use `@st.fragment(run_every=N)` on dashboard render functions to enable auto-refreshing views without reloading the entire page.
* **Data Freshness:** Fragments must fetch their own data (e.g., `db_utils.get_inventory()`) inside the function body to ensure updates are reflected.