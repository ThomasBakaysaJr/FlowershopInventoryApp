import logging
import sqlite3

import pandas as pd

logger = logging.getLogger(__name__)

DB_PATH = 'inventory.db'


def get_connection() -> sqlite3.Connection:
    # timeout=30: wait up to 30s if DB is locked before raising
    conn = sqlite3.connect(DB_PATH, timeout=30)
    # WAL allows concurrent reads during writes
    conn.execute("PRAGMA journal_mode=WAL")
    # Enforce FK constraints (prevents orphaned recipes, etc.)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def filter_dataframe_by_terms(df: pd.DataFrame, column: str, search_term: str) -> pd.DataFrame:
    """Each whitespace-delimited token must appear in `column` (AND logic, case-insensitive)."""
    if not search_term or df.empty:
        return df
    for term in search_term.split():
        df = df[df[column].str.contains(term, case=False, na=False, regex=False)]
    return df
