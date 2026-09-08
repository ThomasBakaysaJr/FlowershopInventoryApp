# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

It is the **single** AI-context document for this repo. If you find another one, it is stale — delete it rather than letting the two drift apart.

> **Referencing convention:** cite functions and files by name, never by line number. Line numbers in this file went stale within a single refactor; function names did not.

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
pytest tests/test_db_utils.py
pytest tests/test_db_utils.py::test_log_production_skips_untracked_items

# Lint / audit (what CI runs)
ruff check .
ruff check . --fix
pip-audit -r requirements.txt
bandit -r src/ -ll
```

**Supported Python: 3.11+.** The floor is declared once, in `pyproject.toml` (`project.requires-python`) — ruff infers its lint target from it, so do not re-add a `target-version`. `app.py` guards it at runtime (with a `noqa: UP036`, because ruff wrongly assumes `requires-python` is enforced; this app is never pip-installed, so nothing enforces it). The constraint comes from pandas 3.x, which dropped 3.10. Local dev runs 3.12, the Ubuntu 24.04 system interpreter.

One-shot data-prep scripts live in `scripts/` and are not part of the running app. They use working-directory-relative paths, so run them **from the repo root** (`python scripts/make_csv.py`). See `scripts/README.md`.

---

## ⚠️ This Repository Is Public

`github.com/ThomasBakaysaJr/FlowershopInventoryApp` is a **public** repo for a real florist. Treat all shop commercial data as sensitive.

**Never commit:** real product names paired with prices, wholesale `unit_cost` values, internal item IDs, or customer/order data.

- `recipes.csv` and `scripts/make_csv.py` are **synthetic demo data** — invented products, prices, and IDs. `make_csv.py` is a generator, not a data dump. Keep it that way.
- The real originals live in `private/`, which is gitignored. Never move them back into the tree.
- `inventory.db` and `settings.json` are gitignored and hold real data locally.
- The synthetic `recipes.csv` is a working example of the bulk-import format and is verified to import through `process_bulk_recipe_upload`. If you regenerate it, re-verify that.

**Already public, unchanged:** the 61 product photos under `images/recipes/` were pushed in early commits. Their filenames expose product names (e.g. `18 rose deluxe.jpeg`) but no pricing.

**If sensitive data is ever committed:** scrub it from history *before* pushing. A later deletion commit does not remove it.

---

## Architecture

### Navigation Model
`app.py` is the sole entry point. It renders a three-level segmented navigation (no page files, no `st.navigation`):
- **Workspace** → Production Overview / Upcoming Orders
- **Designer Space** → Recipe Book / Design Studio
- **Admin Space** → Stock Levels / Production Manager / Forecaster / EOD Inventory Count / Bulk Operations / Settings

Navigation state lives in `st.session_state` under `nav_main`, `nav_workspace`, `nav_design`, and `nav_admin`. Pending navigation changes are staged as `pending_nav_*` keys and swapped at the top of each run to avoid `StreamlitAPIException` from mid-run state changes.

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

All DB access goes through `get_connection()`, which sets `journal_mode=WAL`, `foreign_keys=ON`, and a 30-second busy timeout on **every** connection — SQLite ships with FK enforcement off and the pragma is per-connection, so it must be reapplied each time. `test_foreign_keys_enforced` pins that this actually takes effect. Every function opens and closes its own connection in a `try/finally` block; there are no shared or long-lived connections.

`init_db.py` is the single source of truth for the schema — do not hand-copy it into docs.

**The `_PatchableModule` shim** (bottom of `src/utils/db_utils/__init__.py`): tests assign `db_utils.DB_PATH = <tmp>`, but `get_connection()` reads `_core.DB_PATH`. Without intervention the patch would silently target the real database. The package swaps its own module class for one whose `__setattr__` propagates `DB_PATH` writes down into `_core`. Non-obvious; don't "clean it up" without redirecting the test fixtures first.

### Production Model (Single-Step)
`log_production(goal_id, qty, substitutions, ignore_recipe)` in `production.py` does everything in one transaction:

1. Increments `production_goals.qty_fulfilled`.
2. Inserts one `production_logs` row **per unit** — this is what makes undo unit-granular.
3. Deducts `inventory.count_on_hand` for `Specific` recipe items, **only where `inventory.track_inventory = 1`**.

`undo_production(goal_id)` reverses the most recent unit, restoring tracked items only.

Notes on deliberate behavior:
- **Over-production is allowed.** Logging past `qty_ordered` is physical excess in the shop, not a ledger error.
- **Substitutions follow the same tracked-only rule.**
- **`One-Off` products auto-archive** (`active = 0`) once every outstanding goal for that product is fulfilled.

### The `track_inventory` Flag
The centerpiece of the current inventory model. It is **per-item and user-controlled** via the checkbox column in Stock Levels (`admin_inventory_view.py`), not a global mode.

- `track_inventory = 1` — the app maintains this item's count; production deducts it.
- `track_inventory = 0` — the item is a recipe reference for costing and forecasting only. Counts are meaningless and never deducted.

This is what lets one shop track vases and hard goods while not tracking cut stems, which matches how the floor actually operates. It also means an empty or partially-untracked recipe is a valid, fully-supported state throughout the app.

### Immutable Product Update Pattern
Products are **never mutated in place**. `update_product_recipe()` in `catalog.py` always:
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

### Image Handling
Product images are resized/compressed via Pillow (`src/utils/utils.py`) and stored as BLOBs in `products.image_data`. `_get_local_image_bytes()` in `catalog.py` auto-imports images from `images/recipes/` by matching product names during bulk upload.

---

## Testing

Tests use two fixture patterns:
- `conftest.py` (`setup_db`): patches `db_utils.DB_PATH` directly to `test_suite.db`, initializes via `init_db.initialize_database()`.
- `test_db_utils.py` (`mock_db`): uses `unittest.mock.patch("src.utils.db_utils.DB_PATH", ...)` with a `tmp_path` temp file.

Both fixtures use the real `init_db` schema as the single source of truth — no manual `CREATE TABLE` in test setup. Both rely on the `_PatchableModule` shim described above.

32 tests currently pass.

## CI (`.github/workflows/main.yml`)

Two jobs, running in parallel on push to `main` and on PRs:

| Job | Python | Runs |
|---|---|---|
| `test` | matrix: 3.11, 3.12 | `ruff check .`, `pytest -v tests/` |
| `security` | 3.12 | `pip-audit -r requirements.txt`, `bandit -r src/ -ll` |

The 3.11 leg exists specifically to prove the declared floor is real. Security checks are not version-dependent, so they run once rather than across the matrix.

Ruff config lives in `pyproject.toml`: rules `E,F,W,I,UP,B`, with `E501` and `B008` ignored, and `scripts/*` exempt from style rules (they are ad-hoc utilities).

---

## Known Gaps

Real, unfixed, and deliberately recorded rather than silently carried:

- **Inventory units are conventional, not enforced.** `count_on_hand` holds **individual units** (stems), not packs. Only `process_clipboard_update` Strategy 0 establishes this, by multiplying the counted bundles up (`count * bundle_count - loss`) before storing. Every other write path — the two loose clipboard strategies, bulk CSV import, and hand-edits in the Stock Levels grid — stores whatever integer it is handed, and the grid labels the column just "Stock". Someone entering `4` meaning four bundles silently stores four stems. The forecaster now states the convention where it subtracts; nothing validates it at the write side.
- **Stock freshness is invisible.** The forecaster subtracts `count_on_hand` from demand with no indication of when that count was taken. For untracked items nothing maintains the number between physical counts, so a stale figure silently understates a purchase. See *Counted stock for untracked items* under Deferred Work.
- **`calculate_price()` has no callers.** The Settings page writes a pricing formula (markup multiplier + additive line items) that nothing consumes. The dead Calculator menu item that was going to host it has been removed; the config and the function remain, unused.
- **Mixed line endings.** 28 `.py` files are CRLF (Windows-authored), 18 are LF, and there is no `.gitattributes`. Not currently breaking anything, but it makes whole-file diffs likely on edit. Normalizing is a repo-wide diff, so it has been left as a deliberate decision rather than folded into unrelated work.
- **Test suite is not parallel-safe.** `setup_db` uses one shared `test_suite.db` rather than `tmp_path`, so `pytest -n auto` would fail. Migrating the rest of the suite to the `mock_db` pattern would fix it.
- **Untested paths:** bulk CSV upload, Clipboard Strategy 0 (the ID-based `count=` parser, the most complex branch), `calculate_price`, variant tab logic / "Copy from Standard", and One-Off auto-archive.
- **`catalog.py` is the long file** (~700 lines); `process_bulk_recipe_upload` is ~180 of them, deeply nested. Functionally correct, just dense.

## Deferred Work

- **Cloud deployment.** Planned two-phase: AWS EC2 + RDS Postgres first (free tier, resume value), then migrate to Render + Neon before it expires. Prerequisite is a SQLite→Postgres swap in `db_utils`, reading `DATABASE_URL` from the environment from day one so phase two is config-only.
- **Counted stock for untracked items (forecaster).** The forecaster deliberately ignores `track_inventory` on the *demand* side and must keep doing so — it is a purchasing view, and the flowers the shop does not count are exactly the ones it needs to order. `test_forecast_generic_requirements_aggregates_category_demand` pins this; do not "fix" it. The open work is the *supply* side, in three parts:
  1. **Let untracked items be counted.** `render_eod_tools` filters the count sheet to `track_inventory = 1`. Rather than deleting that filter, add a mode: *Reconciliation count* (tracked only — the app believes it has N, you correct the drift; nightly) and *Purchasing count* (untracked or category-filtered — a snapshot before ordering, with no app-maintained number to reconcile against). Different jobs, different cadence. Downstream needs nothing: the parser and writeback already accept untracked rows.
  2. **Record when a count happened.** Add a nullable `last_counted DATE` to `inventory`, following the two existing additive-migration blocks in `init_db.py` verbatim. Stamp it only where a *human* supplies a count — clipboard writeback, bulk CSV import, hand-edits in the grid — and explicitly **not** on production deduction, which changes the number without anyone looking in the cooler.
  3. **Surface staleness, don't enforce it.** Show the date and its age in the per-item deficit table and against `Current Category Stock` — that one sums a whole `sub_category`, so show the **oldest** member's date, since a category is only as fresh as its stalest row. No hardcoded threshold: roses go stale in days and vases in months, and showing the date beats guessing on the buyer's behalf. `NULL` renders as "never counted", which is the state every row starts in.

- **Variants and time slots as settings.** Move them from `constants.py` into `settings.json` so the app reads as generic retail. The accessor functions in `constants.py` are the migration seam — their internals change, callers don't.
