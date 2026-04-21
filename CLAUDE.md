# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Run the app
streamlit run app.py

# Initialize (or reset) the database
python init_db.py
python init_db.py --reset   # drops and recreates

# Seed with sample data
python seed_db.py
python uni_seed.py           # smart seeder: scans images/recipes/, groups by variant suffix

# Run all tests
pytest

# Run a single test file or test
pytest tests/test_db_utils.py
pytest tests/test_db_utils.py::test_produce_stock

# Lint
ruff check .
ruff check . --fix
```

## Architecture

### Navigation Model
`app.py` is the sole entry point. It renders a three-level segmented navigation (no page files, no `st.navigation`):
- **Workspace** → Production Dashboard / Upcoming Orders / Calculator
- **Designer Space** → Recipe Book / Design Studio
- **Admin Space** → Stock Levels / Production Manager / Forecaster / EOD Inventory Count / Bulk Operations / Settings

Navigation state lives in `st.session_state` under `nav_main`, `nav_workspace`, `nav_design`, and `nav_admin`. Pending navigation changes are staged as `pending_nav_*` keys and swapped at the top of each run to avoid `StreamlitAPIException` from mid-run state changes.

### Database Layer (`src/utils/db_utils.py`)
All DB access goes through `get_connection()`, which enforces WAL mode, `foreign_keys=ON`, and a 30-second lock timeout. Every function opens and closes its own connection in a `try/finally` block — there are no shared or long-lived connections.

`inventory.db` and `settings.json` are gitignored (local only). `init_db.py` is the single source of truth for the schema.

### The Cooler Model (Two-Step Production)
The core operational concept:
1. **Make** (`produce_stock` / `log_production`): deducts raw `inventory.count_on_hand`, increments `products.stock_on_hand` (the walk-in cooler).
2. **Pack/Fulfill** (`fulfill_goal`): deducts `products.stock_on_hand`, increments `production_goals.qty_fulfilled`.

`production_logs.action_type` tracks which step occurred:
- `'MAKE'` — raw inventory → cooler (or directly toward a goal)
- `'STOCK'` — same as MAKE but not tied to a goal (`goal_id IS NULL`)
- `'PACK'` — cooler → goal fulfillment

Undo operations use the log type to decide what to restore. `undo_production` restores raw inventory; `undo_fulfillment` restores to cooler stock.

### Immutable Product Update Pattern
Products are **never mutated in place**. `update_product_recipe()` always:
1. Archives the old row (`active = 0`)
2. Inserts a new product row with the updated data
3. Optionally migrates unfulfilled goals to the new `product_id`

This means `product_id` values change on every recipe edit. Components that need to follow a product across edits use `variant_group_id` (a UUID) instead.

### Recipe Requirement Types
Recipes support two ingredient modes stored in `recipes.requirement_type`:
- `'Specific'` — links to a concrete `item_id`; deducted automatically on production
- `'Category'` — stores a category string in `requirement_value` (e.g. `"Rose"`); requires user to pick a specific item at production time via a modal dialog

### Product Variant System
Products are grouped into families via `variant_group_id` (UUID). Within a family, each variant has a `variant_type`: `STD`, `DLX`, or `PRM`. The Design Studio reads sibling variants through this group ID and renders them as tabs. `uni_seed.py` auto-assigns group IDs by detecting name suffixes (Standard/Deluxe/Premium).

### Settings
`settings.json` (gitignored) stores pricing formula config (markup multiplier + additive line items). `src/utils/settings_utils.py` reads/writes it and exposes `calculate_price(cogs, settings)`.

### Testing
Tests use two fixture patterns:
- `conftest.py` (`setup_db`): patches `db_utils.DB_PATH` directly to `test_suite.db`, initializes via `init_db.initialize_database()`.
- `test_db_utils.py` (`mock_db`): uses `unittest.mock.patch("src.utils.db_utils.DB_PATH", ...)` with a `tmp_path` temp file.

Both fixtures use the real `init_db` schema as the single source of truth — no manual `CREATE TABLE` in test setup.

### Image Handling
Product images are resized/compressed via Pillow (`src/utils/utils.py`) and stored as BLOBs in `products.image_data`. `_get_local_image_bytes()` in `db_utils.py` auto-imports images from `images/recipes/` by matching product names during bulk upload.
