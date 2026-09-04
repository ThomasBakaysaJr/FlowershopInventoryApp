# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

It is the **single** AI-context document for this repo. If you find another one, it is stale — delete it rather than letting the two drift apart.

## Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt        # runtime only
pip install -r requirements-dev.txt    # + pytest, ruff, pip-audit, bandit

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
pytest tests/test_db_utils.py::test_log_production_skips_untracked_items

# Lint
ruff check .
ruff check . --fix
```

**Supported Python: 3.11+.** The floor is declared once, in `pyproject.toml` (`project.requires-python`) — ruff infers its lint target from it, so do not re-add a `target-version`. `app.py` guards it at runtime, and CI tests both 3.11 and 3.12. The constraint comes from pandas 3.x, which dropped 3.10. Local dev and the CI security job both run 3.12 (the Ubuntu 24.04 system interpreter).

One-shot data-prep scripts live in `scripts/` and are not part of the running app. They use working-directory-relative paths, so run them **from the repo root** (`python scripts/make_csv.py`). See `scripts/README.md`.

## Architecture

### Navigation Model
`app.py` is the sole entry point. It renders a three-level segmented navigation (no page files, no `st.navigation`):
- **Workspace** → Production Overview / Upcoming Orders / Calculator
- **Designer Space** → Recipe Book / Design Studio
- **Admin Space** → Stock Levels / Production Manager / Forecaster / EOD Inventory Count / Bulk Operations / Settings

Navigation state lives in `st.session_state` under `nav_main`, `nav_workspace`, `nav_design`, and `nav_admin`. Pending navigation changes are staged as `pending_nav_*` keys and swapped at the top of each run to avoid `StreamlitAPIException` from mid-run state changes.

The **Calculator** menu item is currently a stub — `app.py:96-97` renders the option then `pass`es. `calculate_price()` in `src/utils/settings_utils.py` has no callers, so the pricing config written by the Settings page is not consumed by any UI yet.

### Database Layer (`src/utils/db_utils/`)
A package, not a module. Split by concern:

| Module | Responsibility |
|---|---|
| `_core.py` | `get_connection()`, `DB_PATH`, `filter_dataframe_by_terms()` |
| `inventory.py` | Raw stock CRUD, CSV bulk upload, the Clipboard Protocol parser |
| `catalog.py` | Product + recipe CRUD, image lookup, bulk recipe import, variant grouping |
| `production.py` | Goals, production logging, undo |
| `forecasting.py` | Shopping-list / demand aggregation |

`__init__.py` re-exports the full flat API, so callers still write `db_utils.get_inventory(...)` and nothing outside the package changed when it was split.

All DB access goes through `get_connection()`, which sets `journal_mode=WAL`, `foreign_keys=ON`, and a 30-second busy timeout on **every** connection — SQLite ships with FK enforcement off and the pragma is per-connection, so it must be reapplied each time. Every function opens and closes its own connection in a `try/finally` block; there are no shared or long-lived connections.

`inventory.db` and `settings.json` are gitignored (local only). `init_db.py` is the single source of truth for the schema — do not hand-copy it into docs.

**The `_PatchableModule` shim** (`src/utils/db_utils/__init__.py:50-64`): tests assign `db_utils.DB_PATH = <tmp>`, but `get_connection()` reads `_core.DB_PATH`. Without intervention the patch would silently target the real database. The package swaps its own module class for one whose `__setattr__` propagates `DB_PATH` writes down into `_core`. Non-obvious; don't "clean it up" without redirecting the test fixtures first.

### Production Model (Single-Step)
`log_production(goal_id, qty, substitutions, ignore_recipe)` (`production.py:131-229`) does everything in one transaction:

1. Increments `production_goals.qty_fulfilled`.
2. Inserts one `production_logs` row **per unit** — this is what makes undo unit-granular.
3. Deducts `inventory.count_on_hand` for `Specific` recipe items, **only where `inventory.track_inventory = 1`**.

`undo_production(goal_id)` reverses the most recent unit, restoring tracked items only.

Notes on deliberate behavior:
- **Over-production is allowed.** Logging past `qty_ordered` is physical excess in the shop, not a ledger error.
- **Substitutions follow the same tracked-only rule** (`production.py:201-209`).
- **`One-Off` products auto-archive** (`active = 0`) once every outstanding goal for that product is fulfilled.

### The `track_inventory` Flag
The centerpiece of the current inventory model. It is **per-item and user-controlled** via the checkbox column in Stock Levels (`admin_inventory_view.py`), not a global mode.

- `track_inventory = 1` — the app maintains this item's count; production deducts it.
- `track_inventory = 0` — the item is a recipe reference for costing and forecasting only. Counts are meaningless and never deducted.

This is what lets one shop track vases and hard goods while not tracking cut stems, which matches how the floor actually operates. It also means an empty or partially-untracked recipe is a valid, fully-supported state throughout the app.

Known gap: `src/components/admin/forecaster.py` does **not** filter its deficit math by `track_inventory`, so its "Current Category Stock" figures include untracked items. Unfixed as of this writing.

### Immutable Product Update Pattern
Products are **never mutated in place**. `update_product_recipe()` (`catalog.py:372-457`) always:
1. Archives the old row (`active = 0`)
2. Inserts a new product row with the updated data
3. Optionally migrates unfulfilled goals to the new `product_id`

This means `product_id` values change on every recipe edit. Components that need to follow a product across edits use `variant_group_id` (a UUID) instead.

### Recipe Requirement Types
Recipes support two ingredient modes stored in `recipes.requirement_type`:
- `'Specific'` — links to a concrete `item_id`; deducted automatically on production if tracked
- `'Category'` — stores a category string in `requirement_value` (e.g. `"Rose"`); requires the user to pick a specific item at production time via a modal dialog. The modal auto-suppresses when every candidate in the category is untracked.

### Product Variant System
Products are grouped into families via `variant_group_id` (UUID). Within a family, each variant has a `variant_type`: `STD`, `DLX`, or `PRM`. The Design Studio reads sibling variants through this group ID and renders them as tabs. `uni_seed.py` auto-assigns group IDs by detecting name suffixes (Standard/Deluxe/Premium).

Variant and time-slot definitions live in `src/utils/constants.py` as lists-of-dicts behind accessor functions (`variant_label`, `variant_color`, `variant_order`, `time_slot_rank`, …). Consumers call the accessors, never the lists — that indirection is the seam for eventually making these configurable per-shop.

### Component Map (`src/components/`)

**Shared**
- `date_selector.py` — reusable date-range picker (`render(key_prefix)`)
- `recipe_display.py` — Recipe Book table; `allow_edit=True` in Designer Space, read-only when embedded elsewhere

**Workspace (`workspace_dashboard/`)**
- `dashboard.py` — composes the "Upcoming Orders" view: goal setter + weekly grid + read-only recipe book
- `production_dashboard.py` — "Production Overview": summary header, per-date goal cards
- `dashboard_weekly.py` — weekly goals grid; owns the log/undo production handlers
- `goal_setter.py` — form to add new production goals
- `shared_modals.py` — `generic_selection_modal` (pick a concrete item for a `Category` requirement) and `adjustment_modal` (correct what was actually used)

**Design Studio (`design/`)**
- `design_dashboard.py` — entry point; product selection and variant tabs. Mirrors widget state into `shadow_*` keys so navigating away and back restores the editor.
- `design_product_details.py` — variant view: image, metadata form, "Create Variant"
- `design_recipe_builder.py` — recipe editor: add/remove ingredients, "Copy from Standard"

**Admin (`admin/`)**
- `admin_inventory_view.py` — Stock Levels editable grid (including the `track_inventory` toggle)
- `production_viewer.py` — Production Manager: edit/delete existing goals
- `forecaster.py` — shopping lists from production scenarios
- `admin_tools.py` — `render_eod_tools()` (EOD counts) and `render_bulk_operations()` (CSV import/export)
- `admin_settings.py` — pricing markup and additive line items

### Settings
`settings.json` (gitignored) stores pricing formula config (markup multiplier + additive line items). `src/utils/settings_utils.py` reads/writes it and exposes `calculate_price(cogs, settings)`. New clones fall back to `DEFAULT_SETTINGS`.

### Testing
Tests use two fixture patterns:
- `conftest.py` (`setup_db`): patches `db_utils.DB_PATH` directly to `test_suite.db`, initializes via `init_db.initialize_database()`.
- `test_db_utils.py` (`mock_db`): uses `unittest.mock.patch("src.utils.db_utils.DB_PATH", ...)` with a `tmp_path` temp file.

Both fixtures use the real `init_db` schema as the single source of truth — no manual `CREATE TABLE` in test setup. Both rely on the `_PatchableModule` shim described above.

Because `setup_db` uses one shared file rather than `tmp_path`, the suite is not currently safe under `pytest -n auto`.

### Image Handling
Product images are resized/compressed via Pillow (`src/utils/utils.py`) and stored as BLOBs in `products.image_data`. `_get_local_image_bytes()` in `catalog.py` auto-imports images from `images/recipes/` by matching product names during bulk upload.
