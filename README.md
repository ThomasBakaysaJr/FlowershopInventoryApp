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

## Built with Claude

This project was built with AI assistance throughout, and since the *how* is more interesting than the fact, here is the honest version.

The initial build — 118 commits across eight days in February — ran on a different assistant. Claude Code did the April and September work, which is where the architecture actually got fixed. That is the part worth reading, and the part the commit history is worth scrolling for.

**How I work with it.** The repo keeps a single living context document (`CLAUDE.md`) describing the architecture, the deliberate decisions, and the known gaps. It is maintained, not generated once — including a convention added after getting burned: cite functions and files by name, never by line number, because line numbers went stale inside a single refactor and function names did not. I describe behavior in terms of what happens on the shop floor, review what comes back, and correct the parts that misunderstand the domain.

**What I decided, not the tool:**

* **The `track_inventory` flag.** The obvious design is an all-or-nothing bill of materials — every recipe ingredient is stock, every production event deducts it. That is wrong for a florist. The shop counts vases and hard goods; it does not count individual stems, and pretending otherwise produces numbers nobody trusts and everybody stops updating. So tracking is a per-item toggle the user controls, and an untracked ingredient is a costing reference the app never decrements. It propagates through production logging, undo, low-stock alerts, the end-of-day count, and the substitution modal — a partially untracked recipe is a supported state everywhere, not an edge case. It deliberately does **not** propagate to the forecaster, which is a purchasing view: the flowers you do not count are exactly the ones you need to order.
* **Immutable product updates.** Covered above. The cost is that `product_id` changes on every edit, which is why anything following a product across edits uses a `variant_group_id` UUID instead.
* **Over-production is legal.** Logging past `qty_ordered` is not blocked. If the designer made fourteen arrangements against an order of twelve, fourteen exist. Blocking it would make the app disagree with the room it is installed in.

**Where I overrode the design I had been handed.** Production was originally two-step: *make* moved raw inventory into a `stock_on_hand` column representing the walk-in cooler, then *pack* moved cooler stock into fulfilled orders, with an `action_type` column tracking which step happened and separate undo paths for each. That "Cooler Buffer" model was written into the AI context file as a stated project constraint, and I built inside it for two months.

It was wrong. It modeled a staging step the shop does not actually perform as a discrete state, and it bought nothing — an audit found `stock_on_hand` was written about eleven times across the catalog layer and meaningfully read by nothing. So I collapsed production to a single step, dropped both columns, deleted the orphaned forecasting function and an unimported module that existed to serve them, and removed the model from the context file so it would stop being treated as a given. `track_inventory` is what replaced it — a per-item flag that matches how the floor works instead of an abstraction that only matched a diagram.

The two commits are `refactor: collapse production flow` and `refactor: purge cooler-era fossils from schema and code`; the second names each dropped column and why it went.

**Handling real data.** This is a public repo for a working business, so the shop's actual catalog is not in it. Real product names, wholesale costs, and item IDs live in a gitignored `private/`; the `recipes.csv` in the tree is synthetic output from a generator, kept working so the bulk-import format still has a real example. Same rule for `inventory.db` and `settings.json` — the schema is public, the shop's numbers are not.

**What is not done.** `CLAUDE.md` carries a `Known Gaps` section listing the real unfixed issues: an untested bulk-import path, an unused pricing function, mixed line endings, and an inventory unit convention that is stated but not enforced at the write side. I would rather carry those in writing than have them found. The largest: this runs on the shop's local network only. Moving it to Postgres behind a `DATABASE_URL` environment variable is the planned next step, and the data layer is written so that is a swap rather than a rewrite.

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
