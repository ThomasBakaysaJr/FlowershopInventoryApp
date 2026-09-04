# University Flowers Production Dashboard

An internal production dashboard for a working florist — inventory, recipe design, and production tracking for a high-volume floral operation. Built as a real tool, in real use.

## Project Background

This application solves specific operational bottlenecks in a fast-paced floral environment. The original driver: staff need to count stock inside **Wi-Fi-shielded walk-in coolers**, where no app can reach the network. The "Clipboard Protocol" bridges that gap — count offline in a phone's notes app, paste the text back in, and a parser reconciles it against inventory.

## Core Functionality

Rapid inventory updates, recipe-driven stock deduction, and real-time production tracking against dated goals.

## Goals

* Track current inventory of items, with ID numbers and major/sub-category grouping
* Allow the creation of recipes from inventory items
* Automate inventory deduction via production logging
* Support offline-to-online workflows for low-connectivity areas

## Key Features

* **Selective recipe deduction.** Logging production deducts a product's recipe ingredients from stock — but only for items flagged `track_inventory`. Every item carries its own toggle, so the shop can track vases and hard goods while treating cut stems as costing references it never counts. This hybrid model matches how the floor actually works better than an all-or-nothing bill of materials.
* **Clipboard Protocol.** A text parser that accepts inventory lists pasted from mobile notes apps — solving the "no Wi-Fi in the cooler" problem. Three parsing strategies (ID-based, comma-separated, whitespace) run per line, so one malformed row doesn't abort the batch.
* **Recipe management.** Define arrangements with specific ingredients or generic category requirements ("any Rose"), plus manual price overrides.
* **Product variants.** Products group into families via `variant_group_id`, with Standard / Deluxe / Premium variants rendered as tabs sharing a lineage.
* **Image handling.** Pillow-compressed thumbnails stored as BLOBs in SQLite, so one database file is the entire shop state.
* **Production goals.** Track `qty_ordered` vs `qty_fulfilled` for specific dates, events, and time slots.

## Engineering Notes

Two design decisions worth calling out:

**SQLite connection hygiene.** Every database function opens its own connection and closes it in a `finally` block — no shared handles, no Streamlit-cached connections. The factory (`src/utils/db_utils/_core.py`) sets three pragmas on *every* connection: `journal_mode=WAL` (readers don't block writers), `foreign_keys=ON` (SQLite defaults this **off**, and it's per-connection, so it must be reapplied each time), and a 30-second busy timeout. This matters in Streamlit, which re-runs the whole script top-to-bottom on every interaction.

**Immutable product updates.** Products are never mutated in place. Editing a recipe archives the old row (`active = 0`) and inserts a new one in a single transaction, optionally migrating unfulfilled goals to the new `product_id`. Historical production logs therefore keep pointing at the exact recipe that was used at the time. Since `product_id` changes on every edit, components follow a product across edits via its `variant_group_id` UUID instead.

## Tech Stack

* **Language:** Python 3.11+ — CI tests 3.11 and 3.12 (pandas 3.x dropped 3.10)
* **UI Framework:** Streamlit (no HTML/CSS/JS)
* **Database:** SQLite (local `inventory.db`)
* **Image Processing:** Pillow — resizes/compresses uploads into BLOBs
* **CI:** GitHub Actions — ruff + pytest across a 3.11/3.12 matrix, plus pip-audit and bandit
* **Deployment:** Local network only (host PC acts as server)

## Database Schema

`init_db.py` is the single source of truth for the schema — read it directly rather than trusting a copy here. It defines five tables: `inventory`, `products`, `recipes`, `production_goals`, and `production_logs`, and applies additive column migrations for existing databases on each run.

## Getting Started

### Prerequisites
* Python 3.11 or newer (declared in `pyproject.toml`; `app.py` exits early on anything older)

1. Clone the repository:
   ```bash
   git clone https://github.com/ThomasBakaysaJr/FlowershopInventoryApp.git
   cd FlowershopInventoryApp
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # On Windows (Command Prompt):
   .\.venv\Scripts\activate.bat
   # On Windows (PowerShell):
   .\.venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source .venv/bin/activate
   ```

3. Install required packages:
   ```bash
   pip install -r requirements.txt        # runtime only
   pip install -r requirements-dev.txt    # adds pytest, ruff, pip-audit, bandit
   ```

4. Initialize the database:
   ```bash
   python init_db.py
   python seed_db.py     # optional: sample data
   ```

5. Start the application:
   ```bash
   streamlit run app.py
   ```

### Running Tests

```bash
pytest
ruff check .
```

## Usage

1. **Inventory Update:** Use the Clipboard tool to paste text lists from the cooler, or edit counts directly in the Stock Levels grid.
2. **Recipe Builder:** Link inventory items (stems, vases) to products to define ingredients. Mark which items should actually be counted using the Track column in Stock Levels.
3. **Production:** Use the dashboard to log completed arrangements, which deducts tracked ingredients in real time.

## Repository Layout

```
app.py              Entry point and navigation
init_db.py          Schema — the source of truth
seed_db.py          Sample data
uni_seed.py         Smart seeder: scans images/recipes/, builds variant families
src/utils/          Database layer, settings, image processing
src/components/     Streamlit UI, grouped by workspace / design / admin
scripts/            One-shot data-prep utilities (not part of the app)
tests/              pytest suite
```
