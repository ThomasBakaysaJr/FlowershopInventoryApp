# AI CONTEXT: PROJECT STRUCTURE
# This file outlines the project architecture, file map, and component breakdown.
# For coding rules and standards, please refer to GEMINI.md.

# Project Context: Flowershop Inventory App

## Overview
A Streamlit application for managing a flower shop's inventory, designing product recipes, and tracking production goals.

## Architecture
- **Frontend**: Streamlit
- **Backend**: Python
- **Database**: SQLite (`inventory.db`)

## File Structure & Key Modules

### Root
- `app.py`: Application entry point. Handles main navigation (Workspace, Design, Admin).
- `init_db.py`: Database schema initialization.
- `seed_db.py`: Populates database with sample data.
- `uni_seed.py`: **Smart Seeder**. Scans `images/recipes`, groups files by suffix (Standard/Deluxe/Premium), and creates linked Product Families.
- `migrate_v2.py`: Database migration script (adds generic recipe support).

### Core Logic (`src/utils/`)
- `db_utils.py`: Central data access layer.
  - **Inventory**: `get_inventory`, `update_item_details`, `process_bulk_inventory_upload`.
  - **Recipes/Products**: `create_new_product`, `update_product_recipe`, `get_product_details`.
  - **Production**: `log_production`, `produce_stock`, `fulfill_goal`, `undo_production`.
  - **Forecasting**: `get_forecast_initial_data`, `get_production_requirements`.
- `utils.py`: Image processing utilities (resizing/compression).
- `settings_utils.py`: Configuration management (pricing formulas).

### Components (`src/components/`)

#### 1. Workspace Dashboard (`workspace_dashboard/`)
- `dashboard.py`: Aggregates the workspace views.
- `production_dashboard.py`: **Cooler Dashboard**. Manages stock-on-hand.
- `dashboard_weekly.py`: **Weekly Goals**. Tracks scheduled orders vs. fulfillment.
- `goal_setter.py`: Form to add new production goals.

#### 2. Design Studio (`design/`)
- `design_dashboard.py`: **Entry Point**. Handles product selection and renders the Variant Tabs (STD/DLX/PRM).
- `design_product_details.py`: **Variant View**. Displays image, metadata form, and "Create Variant" logic.
- `design_recipe_builder.py`: **Recipe Editor**. Handles ingredient addition, removal, and "Copy from Standard" logic.

#### 3. Admin Tools (`admin/`)
- `admin_inventory_view.py`: **Stock Levels**. Editable grid for raw inventory.
- `production_viewer.py`: **Production Manager**. Edit/Delete existing goals.
- `forecaster.py`: **Forecaster**. Generates shopping lists based on production scenarios.
- `admin_tools.py`: **Bulk Ops**. CSV Import/Export and EOD counts.
- `admin_settings.py`: **Settings**. Configure pricing markup and additives.

## Data Models
- **Inventory**: Raw items (Flowers, Vases).
- **Products**: Defined designs/recipes. Organized into **Families** via `variant_group_id`. Variants (`STD`, `DLX`, `PRM`) share a group but have unique recipes/prices.
- **Recipes**: Ingredients required for a product. Supports `Specific` (Item ID) or `Category` (e.g., "Any Rose").
- **Production Goals**: Orders with due dates.
- **Production Logs**: Audit trail of items made.

## Setup & Run
1. **Initialize Database**:
   ```bash
   python init_db.py
   ```
2. **Run Application**:
   ```bash
   streamlit run app.py
   ```