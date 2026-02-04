# University Flowers Production Dashboard
An internal production dashboard designed for high-volume floral operations. 

## Project Background
This application was developed to solve specific operational bottlenecks in a fast-paced floral environment. The primary challenge addressed is the "Cooler Connectivity Gap"—where staff need to manage inventory in Wi-Fi-shielded walk-in coolers. By implementing a "Clipboard Protocol" and a Streamlit-based local server, this tool bridges the gap between physical stock-counting and digital inventory management.

## Core Functionality
The system focuses on rapid inventory updates, recipe-based stock deduction (Bill of Materials), and real-time production tracking.

# Goals
* Track current inventory of items
    * Items are tracked with ID numbers, have major category and sub-category for grouping.
* Allow for the creation of recipes from inventory items
* Automate inventory deduction via production logging
* Support offline-to-online workflows for low-connectivity areas (walk-in coolers)

## Key Features
* **Bill of Materials (BOM) Deduction:** Clicking "+1 Made" on a product automatically subtracts the required stems and hard goods from the inventory.
* **Clipboard Protocol:** A text parser that allows staff to paste inventory lists from mobile notes apps—solving the "no Wi-Fi in the cooler" problem.
* **Recipe Management:** Define arrangements with specific ingredients and manual price overrides.
* **Image Handling:** Integrated thumbnail storage using Pillow for compressed BLOB storage in SQLite.
* **Production Goals:** Track `qty_ordered` vs `qty_made` for specific dates/events.

## Tech Stack
* **Language:** Python 3.x
* **UI Framework:** Streamlit (No HTML/CSS/JS)
* **Database:** SQLite (Local `inventory.db`)
* **Image Processing:** Pillow (PIL) - Resizes/compresses uploads into BLOBs
* **Deployment:** Local Network only (Host PC acts as server)

## Database Schema
The application uses a local SQLite database (`inventory.db`) with the following structure:

```sql
CREATE TABLE inventory (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,          -- e.g., "Freedom Red Rose"
    category TEXT,               -- "Stem", "Hard Good", "Greenery"
    sub_category TEXT,           -- "Rose", "Lily", "Vase"
    count_on_hand INTEGER DEFAULT 0,
    unit_cost REAL DEFAULT 0.00
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL,  -- e.g., "Valentine Special"
    image_data BLOB,             -- Thumbnail storage
    selling_price REAL DEFAULT 0.00, -- Manual Override
    active BOOLEAN DEFAULT 1
);

CREATE TABLE recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    item_id INTEGER,
    qty_needed INTEGER,
    FOREIGN KEY(product_id) REFERENCES products(product_id),
    FOREIGN KEY(item_id) REFERENCES inventory(item_id)
);

CREATE TABLE production_goals (
    goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    due_date DATE,
    qty_ordered INTEGER DEFAULT 0,
    qty_made INTEGER DEFAULT 0,
    FOREIGN KEY(product_id) REFERENCES products(product_id)
);
```

## Getting Started

### Prerequisites
* Python 3.10+

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/FlowershopInventoryApp.git
   ```
2. Install required packages:
   ```bash
   pip install streamlit pillow
   ```
3. Start the application:
   ```bash
   streamlit run app.py
   ```

## Usage
1. **Inventory Update:** Use the "Clipboard" tool to paste text lists from the cooler or manually update counts.
2. **Recipe Builder:** Link inventory items (stems/vases) to products to define the Bill of Materials.
3. **Production:** Use the Dashboard to log completed arrangements, which triggers real-time inventory deduction.