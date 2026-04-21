import pandas as pd
import logging

from ._core import get_connection

logger = logging.getLogger(__name__)


def get_forecast_initial_data(start_date, end_date) -> pd.DataFrame:
    """Fetches active products + archived ones with goals, aggregating expected qty."""
    conn = get_connection()
    try:
        s_date = start_date.strftime('%Y-%m-%d') if hasattr(start_date, 'strftime') else str(start_date)
        e_date = end_date.strftime('%Y-%m-%d') if hasattr(end_date, 'strftime') else str(end_date)

        query = """
        SELECT p.product_id, p.display_name as Product, p.active, COALESCE(SUM(MAX(0, pg.qty_ordered - pg.qty_fulfilled)), 0) as Expected
        FROM products p
        LEFT JOIN production_goals pg ON p.product_id = pg.product_id AND pg.due_date BETWEEN ? AND ?
        WHERE p.active = 1 OR pg.goal_id IS NOT NULL
        GROUP BY p.product_id
        ORDER BY p.display_name ASC
        """
        return pd.read_sql_query(query, conn, params=(s_date, e_date))
    except Exception as e:
        logger.error(f"get_forecast_initial_data: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def get_production_requirements(start_date, end_date) -> pd.DataFrame:
    """Fetches products with current stock and aggregated requirements for the date range."""
    conn = get_connection()
    try:
        s_date = start_date.strftime('%Y-%m-%d') if hasattr(start_date, 'strftime') else str(start_date)
        e_date = end_date.strftime('%Y-%m-%d') if hasattr(end_date, 'strftime') else str(end_date)

        query = """
        SELECT
            p.product_id,
            p.display_name as Product,
            p.active,
            MAX(p.stock_on_hand) as stock_on_hand,
            MAX(p.note) as note,
            MAX(p.variant_type) as variant_type,
            COALESCE(SUM(MAX(0, pg.qty_ordered - pg.qty_fulfilled)), 0) as required_qty
        FROM products p
        LEFT JOIN production_goals pg ON p.product_id = pg.product_id AND pg.due_date BETWEEN ? AND ?
        WHERE p.active = 1 OR pg.goal_id IS NOT NULL
        GROUP BY p.product_id
        ORDER BY p.display_name ASC
        """
        return pd.read_sql_query(query, conn, params=(s_date, e_date))
    except Exception as e:
        logger.error(f"get_production_requirements: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def get_forecast_generic_requirements(start_date, end_date) -> pd.DataFrame:
    """Returns aggregated demand for generic categories within a date range."""
    conn = get_connection()
    try:
        s_date = start_date.strftime('%Y-%m-%d') if hasattr(start_date, 'strftime') else str(start_date)
        e_date = end_date.strftime('%Y-%m-%d') if hasattr(end_date, 'strftime') else str(end_date)

        query = """
            SELECT
                r.requirement_value as Category,
                SUM((g.qty_ordered - g.qty_fulfilled) * r.qty_needed) as Needed
            FROM production_goals g
            JOIN recipes r ON g.product_id = r.product_id
            WHERE g.due_date BETWEEN ? AND ?
              AND r.requirement_type = 'Category'
              AND (g.qty_ordered - g.qty_fulfilled) > 0
            GROUP BY r.requirement_value
        """
        return pd.read_sql_query(query, conn, params=(s_date, e_date))
    except Exception as e:
        logger.error(f"get_forecast_generic_requirements: {e}")
        return pd.DataFrame()
    finally:
        conn.close()
