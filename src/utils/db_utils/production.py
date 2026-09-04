import logging
import sqlite3

import pandas as pd

from src.utils.utils import normalize_time_slots, safe_date_string

from ._core import get_connection

logger = logging.getLogger(__name__)


def get_goal_product_id(goal_id: int):
    """Fetches the product_id associated with a specific goal."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT product_id FROM production_goals WHERE goal_id = ?", (goal_id,))
        res = cursor.fetchone()
        return res[0] if res else None
    except Exception as e:
        logger.error(f"get_goal_product_id: {e}")
        return None
    finally:
        conn.close()


def get_production_goals_range(start_date, end_date) -> pd.DataFrame:
    """Fetches production goals falling within a specific date range."""
    conn = get_connection()
    try:
        s_date = safe_date_string(start_date)
        e_date = safe_date_string(end_date)

        query = """
        SELECT pg.goal_id, p.product_id, p.display_name as Product, p.active, p.image_data, p.note, p.variant_type, pg.due_date, pg.qty_ordered, pg.qty_fulfilled, pg.time_slot
        FROM production_goals pg
        JOIN products p ON pg.product_id = p.product_id
        WHERE pg.due_date BETWEEN ? AND ?
        ORDER BY pg.due_date ASC, p.display_name ASC
        """
        df = pd.read_sql_query(query, conn, params=(s_date, e_date))
        normalize_time_slots(df)
        return df
    except Exception as e:
        logger.error(f"get_production_goals_range: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def get_active_and_scheduled_products(start_date, end_date) -> pd.DataFrame:
    """Returns products that are active OR have goals in the date range."""
    conn = get_connection()
    try:
        s_date = safe_date_string(start_date)
        e_date = safe_date_string(end_date)

        query = """
        SELECT DISTINCT p.product_id, p.display_name
        FROM products p
        WHERE p.active = 1
        OR p.product_id IN (
            SELECT product_id FROM production_goals
            WHERE due_date BETWEEN ? AND ?
        )
        ORDER BY p.display_name ASC
        """
        return pd.read_sql_query(query, conn, params=(s_date, e_date))
    except Exception as e:
        logger.error(f"get_active_and_scheduled_products: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def add_production_goal(product_id: int, due_date: str, qty_ordered: int, time_slot: str = 'Any') -> bool:
    """Adds a new production goal."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO production_goals (product_id, due_date, qty_ordered, qty_fulfilled, time_slot) VALUES (?, ?, ?, 0, ?)",
            (product_id, due_date, qty_ordered, time_slot),
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"add_production_goal: {e}")
        return False
    finally:
        conn.close()


def delete_production_goal(goal_id: int) -> bool:
    """Deletes a goal and its production logs. Already-made items are physical excess — no ledger move."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM production_logs WHERE goal_id = ?", (goal_id,))
        cursor.execute("DELETE FROM production_goals WHERE goal_id = ?", (goal_id,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"delete_production_goal: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def update_goal_quantity(goal_id: int, new_qty: int) -> dict:
    """Updates the target quantity and reports if now over-fulfilled."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT qty_fulfilled FROM production_goals WHERE goal_id = ?", (goal_id,))
        res = cursor.fetchone()
        current_made = res[0] if res else 0

        cursor.execute("UPDATE production_goals SET qty_ordered = ? WHERE goal_id = ?", (new_qty, goal_id))
        conn.commit()

        return {"success": True, "overage": max(0, current_made - new_qty)}
    except sqlite3.Error as e:
        logger.error(f"update_goal_quantity: {e}")
        return {"success": False, "overage": 0}
    finally:
        conn.close()


def log_production(
    goal_id: int,
    qty: int = 1,
    substitutions: list = None,
    ignore_recipe: bool = False,
) -> int:
    """Log production of `qty` units toward a goal.

    - Deducts Specific-recipe-ingredient items from inventory, *only* for items
      with `track_inventory = 1`. Untracked items (e.g. cut flowers) are recipe
      references for pricing only; the app does not maintain their counts.
    - Writes one `production_logs` row per unit, preserving the unit-granular
      undo pattern.
    - Auto-archives completed One-Off products once every goal for that
      product is fulfilled.

    Returns the number of units actually logged.
    """
    qty = max(0, int(qty))
    if qty == 0:
        return 0

    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT p.product_id, p.category, pg.qty_ordered, pg.qty_fulfilled
            FROM production_goals pg
            JOIN products p ON pg.product_id = p.product_id
            WHERE pg.goal_id = ?
            """,
            (goal_id,),
        )
        res = cursor.fetchone()
        if not res:
            logger.error(f"log_production: Goal ID {goal_id} not found.")
            return 0
        p_id, category, ordered, fulfilled = res

        # Over-production is allowed — physical excess in the shop, not a ledger phantom.
        cursor.execute(
            "UPDATE production_goals SET qty_fulfilled = qty_fulfilled + ? WHERE goal_id = ?",
            (qty, goal_id),
        )

        log_rows = [(goal_id, p_id) for _ in range(qty)]
        cursor.executemany(
            "INSERT INTO production_logs (goal_id, product_id) VALUES (?, ?)",
            log_rows,
        )

        if not ignore_recipe:
            # Only tracked items get deducted; untracked (track_inventory=0) are skipped.
            cursor.execute(
                """
                SELECT r.item_id, r.qty_needed
                FROM recipes r
                JOIN inventory i ON r.item_id = i.item_id
                WHERE r.product_id = ? AND r.requirement_type = 'Specific' AND i.track_inventory = 1
                """,
                (p_id,),
            )
            for i_id, per_unit in cursor.fetchall():
                cursor.execute(
                    "UPDATE inventory SET count_on_hand = count_on_hand - ? WHERE item_id = ?",
                    (per_unit * qty, i_id),
                )

        if substitutions:
            for sub_item_id, sub_qty in substitutions:
                cursor.execute("SELECT track_inventory FROM inventory WHERE item_id = ?", (sub_item_id,))
                row = cursor.fetchone()
                if row and row[0] == 1:
                    cursor.execute(
                        "UPDATE inventory SET count_on_hand = count_on_hand - ? WHERE item_id = ?",
                        (sub_qty * qty, sub_item_id),
                    )

        # One-Off auto-archive: if this log completes the last outstanding goal for the product.
        if category == 'One-Off' and (fulfilled + qty) >= ordered:
            cursor.execute(
                "SELECT COUNT(*) FROM production_goals "
                "WHERE product_id = ? AND qty_fulfilled < qty_ordered AND goal_id != ?",
                (p_id, goal_id),
            )
            if cursor.fetchone()[0] == 0:
                logger.info(f"log_production: Auto-archiving completed One-Off product {p_id}")
                cursor.execute("UPDATE products SET active = 0 WHERE product_id = ?", (p_id,))

        conn.commit()
        return qty
    except sqlite3.Error as e:
        logger.error(f"log_production: Database error: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()


def undo_production(goal_id: int) -> bool:
    """Undo the most recent production event on a goal.

    - Deletes one production_logs row (the latest) and decrements `qty_fulfilled` by 1.
    - Restores tracked Specific-recipe items from the original recipe version
      (the log's `product_id`, which survives recipe edits thanks to the
      immutable-product pattern).
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT product_id FROM production_goals WHERE goal_id = ?", (goal_id,))
        if not cursor.fetchone():
            return False

        cursor.execute(
            "SELECT log_id, product_id FROM production_logs "
            "WHERE goal_id = ? ORDER BY log_id DESC LIMIT 1",
            (goal_id,),
        )
        log_res = cursor.fetchone()
        if not log_res:
            return False
        log_id, log_p_id = log_res

        cursor.execute("DELETE FROM production_logs WHERE log_id = ?", (log_id,))
        cursor.execute(
            "UPDATE production_goals SET qty_fulfilled = qty_fulfilled - 1 WHERE goal_id = ?",
            (goal_id,),
        )

        # Restore tracked recipe items using the log's original product version.
        cursor.execute(
            """
            SELECT r.item_id, r.qty_needed
            FROM recipes r
            JOIN inventory i ON r.item_id = i.item_id
            WHERE r.product_id = ? AND r.requirement_type = 'Specific' AND i.track_inventory = 1
            """,
            (log_p_id,),
        )
        for i_id, per_unit in cursor.fetchall():
            cursor.execute(
                "UPDATE inventory SET count_on_hand = count_on_hand + ? WHERE item_id = ?",
                (per_unit, i_id),
            )

        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"undo_production: Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
