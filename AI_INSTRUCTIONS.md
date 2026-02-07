# AI Development Guidelines for University Flowers Production Dashboard

## 1. Project Context
* **Goal:** A high-volume floral production dashboard for managing inventory and recipes.
* **Key Constraints:** * **Offline-First:** Must support "Clipboard Protocol" for text-based inventory updates (coolers have no Wi-Fi).
    * **Local Execution:** Runs locally on a host PC using Streamlit; no cloud dependencies.
    * **Data Integrity:** Use **Immutable Data** patterns for product history. Never overwrite active product recipes; always archive (soft delete) and create new versions.

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
* **Logging:** All production actions must be recorded in `production_logs` with a timestamp.
* **Inventory Units:** Inventory `count_on_hand` represents physical units (packs/bunches). Total stem count = `count_on_hand * bundle_count`.

## 4. Coding Style
* **Functions:** Type-hint all arguments and return values.
* **Error Handling:** Wrap all DB operations in `try/except sqlite3.Error`.
* **Testing:** Use `pytest`. Critical paths (Inventory Deduction, Undo Logic) must be tested.
* **Logging:** All logs should goto `logs/app.log`. Use logging instead of print statements, make sure all logs record the script they reside in, and when called, the function that called it.
* **Separation of Concerns:** Maintain good separation between UI and logic. Logic should go into respective scripts in `src/` (e.g. `src/utils/` or `src/logic/`) rather than embedding complex logic in UI files.


## 5. UI/UX Patterns
* **Workspace Structure:**
    * *Upcoming Work:* Displays production goals (Weekly Goals).
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
* **Deprecated Arguments:** Use `width='stretch'` instead of `use_container_width=True` (or `use_content_width`) where applicable for dataframes/editors to ensure consistent layout.

## 8. Business Logic Constraints
* **Clipboard Symmetry:** The "Download Inventory" format must match the "Clipboard Parser" logic. Updates rely on `item_id` and `bundle_count` to calculate `(count * bundle_count) - loss`.