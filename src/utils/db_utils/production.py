import sqlite3
import pandas as pd
import logging

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
        s_date = start_date.strftime('%Y-%m-%d') if hasattr(start_date, 'strftime') else str(start_date)
        e_date = end_date.strftime('%Y-%m-%d') if hasattr(end_date, 'strftime') else str(end_date)

        query = """
        SELECT pg.goal_id, p.product_id, p.display_name as Product, p.active, p.stock_on_hand, p.note, p.variant_type, pg.due_date, pg.qty_ordered, pg.qty_fulfilled, pg.time_slot
        FROM production_goals pg
        JOIN products p ON pg.product_id = p.product_id
        WHERE pg.due_date BETWEEN ? AND ?
        ORDER BY pg.due_date ASC, p.display_name ASC
        """
        df = pd.read_sql_query(query, conn, params=(s_date, e_date))

        if 'time_slot' in df.columns:
            df['time_slot'] = df['time_slot'].fillna('Any').astype(str).str.strip().str.upper()

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
        s_date = start_date.strftime('%Y-%m-%d') if hasattr(start_date, 'strftime') else str(start_date)
        e_date = end_date.strftime('%Y-%m-%d') if hasattr(end_date, 'strftime') else str(end_date)

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
    """Removes a goal. Items already made are returned to general stock."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT product_id, qty_fulfilled FROM production_goals WHERE goal_id = ?", (goal_id,))
        res = cursor.fetchone()

        if res:
            p_id, made_count = res

            if made_count > 0:
                logger.info(f"delete_production_goal: Returning {made_count} items to stock for product {p_id}")
                cursor.execute(
                    "UPDATE products SET stock_on_hand = stock_on_hand + ? WHERE product_id = ?",
                    (made_count, p_id),
                )
                # PACK logs (Stock -> Goal) are deleted; MAKE logs are detached as STOCK production
                cursor.execute("DELETE FROM production_logs WHERE goal_id = ? AND action_type = 'PACK'", (goal_id,))
                cursor.execute(
                    "UPDATE production_logs SET goal_id = NULL, action_type = 'STOCK' WHERE goal_id = ? AND action_type != 'PACK'",
                    (goal_id,),
                )

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


def release_overage_to_stock(goal_id: int, qty_to_release: int) -> bool:
    """Moves items from goal progress to general stock (cooler)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT product_id FROM production_goals WHERE goal_id = ?", (goal_id,))
        p_id = cursor.fetchone()[0]

        cursor.execute(
            "UPDATE production_goals SET qty_fulfilled = qty_fulfilled - ? WHERE goal_id = ?",
            (qty_to_release, goal_id),
        )
        cursor.execute(
            "UPDATE products SET stock_on_hand = stock_on_hand + ? WHERE product_id = ?",
            (qty_to_release, p_id),
        )

        cursor.execute(
            "SELECT log_id, action_type FROM production_logs WHERE goal_id = ? ORDER BY log_id DESC LIMIT ?",
            (goal_id, qty_to_release),
        )
        logs = cursor.fetchall()

        pack_ids = [str(row[0]) for row in logs if row[1] == 'PACK']
        make_ids = [str(row[0]) for row in logs if row[1] != 'PACK']

        if pack_ids:
            cursor.execute(f"DELETE FROM production_logs WHERE log_id IN ({','.join(pack_ids)})")

        if make_ids:
            cursor.execute(
                f"UPDATE production_logs SET goal_id = NULL, action_type = 'STOCK' WHERE log_id IN ({','.join(make_ids)})"
            )

        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"release_overage_to_stock: {e}")
        return False
    finally:
        conn.close()


def log_production(goal_id: int, substitutions: list = None, ignore_recipe: bool = False) -> bool:
    """
    Increments qty_fulfilled and deducts inventory (BOM) for a goal.
    substitutions: list of (item_id, qty) for generic recipe items resolved by the user.
    ignore_recipe: if True, skips standard specific-item deductions (only substitutions are used).
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT product_id, qty_fulfilled, qty_ordered FROM production_goals WHERE goal_id = ?",
            (goal_id,),
        )
        res = cursor.fetchone()

        if not res:
            logger.error(f"log_production: Goal ID {goal_id} not found.")
            return False

        p_id, qty_fulfilled, qty_ordered = res
        logger.debug(f"log_production: goal_id={goal_id}, product_id={p_id}")

        cursor.execute("UPDATE production_goals SET qty_fulfilled = qty_fulfilled + 1 WHERE goal_id = ?", (goal_id,))
        cursor.execute(
            "INSERT INTO production_logs (goal_id, product_id, action_type) VALUES (?, ?, 'MAKE')",
            (goal_id, p_id),
        )

        if not ignore_recipe:
            cursor.execute(
                "SELECT item_id, qty_needed FROM recipes WHERE product_id = ? AND requirement_type = 'Specific'",
                (p_id,),
            )
            for i_id, qty in cursor.fetchall():
                cursor.execute(
                    "UPDATE inventory SET count_on_hand = count_on_hand - ? WHERE item_id = ?",
                    (qty, i_id),
                )

        if substitutions:
            for sub_item_id, sub_qty in substitutions:
                cursor.execute(
                    "UPDATE inventory SET count_on_hand = count_on_hand - ? WHERE item_id = ?",
                    (sub_qty, sub_item_id),
                )

        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"log_production: Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def produce_stock(product_id: int, substitutions: list = None, ignore_recipe: bool = False) -> bool:
    """Increments stock_on_hand and deducts inventory (BOM). Logs with goal_id=NULL."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE products SET stock_on_hand = stock_on_hand + 1 WHERE product_id = ?",
            (product_id,),
        )

        if cursor.rowcount == 0:
            logger.warning(f"produce_stock: No product found with ID {product_id}")
            return False

        cursor.execute(
            "INSERT INTO production_logs (goal_id, product_id, action_type) VALUES (NULL, ?, 'STOCK')",
            (product_id,),
        )

        if not ignore_recipe:
            cursor.execute(
                "SELECT item_id, qty_needed FROM recipes WHERE product_id = ? AND requirement_type = 'Specific'",
                (product_id,),
            )
            for i_id, qty in cursor.fetchall():
                cursor.execute(
                    "UPDATE inventory SET count_on_hand = count_on_hand - ? WHERE item_id = ?",
                    (qty, i_id),
                )

        if substitutions:
            for sub_item_id, sub_qty in substitutions:
                cursor.execute(
                    "UPDATE inventory SET count_on_hand = count_on_hand - ? WHERE item_id = ?",
                    (sub_qty, sub_item_id),
                )

        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"produce_stock: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def undo_production(goal_id: int) -> bool:
    """Decrements qty_fulfilled and restores inventory (BOM)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT product_id FROM production_goals WHERE goal_id = ?", (goal_id,))
        res = cursor.fetchone()
        if not res:
            return False
        goal_p_id = res[0]

        cursor.execute(
            "SELECT log_id, action_type, product_id FROM production_logs WHERE goal_id = ? ORDER BY log_id DESC LIMIT 1",
            (goal_id,),
        )
        log_res = cursor.fetchone()

        if log_res:
            l_id, action_type, log_p_id = log_res
            logger.info(f"undo_production: Reverting goal_id {goal_id}, log_id {l_id}")

            if action_type == 'PACK':
                cursor.execute("DELETE FROM production_logs WHERE log_id = ?", (l_id,))
                cursor.execute(
                    "UPDATE production_goals SET qty_fulfilled = qty_fulfilled - 1 WHERE goal_id = ?",
                    (goal_id,),
                )
                cursor.execute(
                    "UPDATE products SET stock_on_hand = stock_on_hand + 1 WHERE product_id = ?",
                    (goal_p_id,),
                )
                conn.commit()
                return True

            cursor.execute("DELETE FROM production_logs WHERE log_id = ?", (l_id,))
            cursor.execute(
                "UPDATE production_goals SET qty_fulfilled = qty_fulfilled - 1 WHERE goal_id = ?",
                (goal_id,),
            )

            # Restore using the original product version's recipe (handles archived products correctly)
            cursor.execute("SELECT item_id, qty_needed FROM recipes WHERE product_id = ?", (log_p_id,))
            for i_id, qty in cursor.fetchall():
                cursor.execute(
                    "UPDATE inventory SET count_on_hand = count_on_hand + ? WHERE item_id = ?",
                    (qty, i_id),
                )

            conn.commit()
            return True
        return False
    except sqlite3.Error as e:
        logger.error(f"undo_production: Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def undo_stock_production(product_id: int) -> bool:
    """Decrements stock_on_hand and restores inventory. Reverts last STOCK log."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT log_id, action_type FROM production_logs WHERE product_id = ? AND goal_id IS NULL ORDER BY log_id DESC LIMIT 1",
            (product_id,),
        )
        res = cursor.fetchone()

        if not res:
            return False

        log_id, action_type = res

        # Never undo a PACK action here — those belong to deleted goals
        if action_type == 'PACK':
            logger.warning(f"undo_stock_production: Skipped PACK log {log_id}.")
            return False

        cursor.execute("DELETE FROM production_logs WHERE log_id = ?", (log_id,))
        cursor.execute(
            "UPDATE products SET stock_on_hand = stock_on_hand - 1 WHERE product_id = ?",
            (product_id,),
        )

        if cursor.rowcount == 0:
            logger.warning(f"undo_stock_production: No product found with ID {product_id}")
            return False

        cursor.execute("SELECT item_id, qty_needed FROM recipes WHERE product_id = ?", (product_id,))
        for i_id, qty in cursor.fetchall():
            cursor.execute(
                "UPDATE inventory SET count_on_hand = count_on_hand + ? WHERE item_id = ?",
                (qty, i_id),
            )

        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"undo_stock_production: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def fulfill_goal(goal_id: int, qty: int = 1) -> int:
    """Decrements stock_on_hand and increments qty_fulfilled (Cooler -> Order)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        qty = int(qty)

        cursor.execute(
            """
            SELECT p.stock_on_hand, p.product_id, p.category, pg.qty_ordered, pg.qty_fulfilled
            FROM production_goals pg
            JOIN products p ON pg.product_id = p.product_id
            WHERE pg.goal_id = ?
            """,
            (goal_id,),
        )
        res = cursor.fetchone()

        if not res:
            return 0
        stock, p_id, category, ordered, fulfilled = res

        needed = max(0, ordered - fulfilled)
        actual_qty = min(qty, stock, needed)

        if actual_qty <= 0:
            logger.warning(f"fulfill_goal: Cannot pack (Requested: {qty}, Stock: {stock}, Needed: {needed})")
            return 0

        cursor.execute(
            "UPDATE products SET stock_on_hand = stock_on_hand - ? WHERE product_id = ?",
            (actual_qty, p_id),
        )
        cursor.execute(
            "UPDATE production_goals SET qty_fulfilled = qty_fulfilled + ? WHERE goal_id = ?",
            (actual_qty, goal_id),
        )

        logs = [(goal_id, p_id, 'PACK') for _ in range(actual_qty)]
        cursor.executemany(
            "INSERT INTO production_logs (goal_id, product_id, action_type) VALUES (?, ?, ?)",
            logs,
        )

        if category == 'One-Off':
            new_stock = stock - actual_qty
            cursor.execute(
                "SELECT COUNT(*) FROM production_goals WHERE product_id = ? AND qty_fulfilled < qty_ordered",
                (p_id,),
            )
            pending_goals = cursor.fetchone()[0]
            if new_stock <= 0 and pending_goals == 0:
                logger.info(f"fulfill_goal: Auto-archiving completed One-Off product {p_id}")
                cursor.execute("UPDATE products SET active = 0 WHERE product_id = ?", (p_id,))

        conn.commit()
        return actual_qty
    except sqlite3.Error as e:
        logger.error(f"fulfill_goal: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()


def undo_fulfillment(goal_id: int) -> bool:
    """Reverts a fulfillment: increments stock_on_hand, decrements qty_fulfilled."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT product_id FROM production_goals WHERE goal_id = ?", (goal_id,))
        res = cursor.fetchone()
        if not res:
            return False
        p_id = res[0]

        cursor.execute(
            "SELECT log_id FROM production_logs WHERE goal_id = ? ORDER BY log_id DESC LIMIT 1",
            (goal_id,),
        )
        log_res = cursor.fetchone()
        if not log_res:
            return False
        log_id = log_res[0]

        cursor.execute("DELETE FROM production_logs WHERE log_id = ?", (log_id,))
        cursor.execute(
            "UPDATE production_goals SET qty_fulfilled = qty_fulfilled - 1 WHERE goal_id = ?",
            (goal_id,),
        )
        cursor.execute(
            "UPDATE products SET stock_on_hand = stock_on_hand + 1 WHERE product_id = ?",
            (p_id,),
        )

        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"undo_fulfillment: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
