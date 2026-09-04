"""Generate a demo recipes.csv for bulk-import testing.

The catalog below is entirely synthetic — invented product names, prices, and
item IDs. It exists so the repo ships a working example of the bulk-import
format without publishing the shop's real catalog, retail prices, or wholesale
costs.

Emits the columns the Bulk Operations importer expects:
    product_id, Product, Price, Type, Product Note, item_id, Ingredient,
    Note, Qty, Category

Run from the repository root:
    python scripts/make_csv.py
"""

import pandas as pd

# --- Synthetic inventory -----------------------------------------------------
# item_id, name, category, sub_category, unit_cost
INVENTORY = [
    (101, "Rose Crimson",      "stem",     "Rose",      1.10),
    (102, "Rose Blush",        "stem",     "Rose",      1.10),
    (103, "Rose Ivory",        "stem",     "Rose",      1.15),
    (104, "Rose Sunrise",      "stem",     "Rose",      1.20),
    (105, "Lily Stargazer",    "stem",     "Lily",      2.40),
    (106, "Lily Casablanca",   "stem",     "Lily",      2.60),
    (107, "Tulip Yellow",      "stem",     "Tulip",     0.90),
    (108, "Carnation Pink",    "stem",     "Carnation", 0.65),
    (109, "Daisy Classic",     "stem",     "Daisy",     0.70),
    (110, "Snapdragon Coral",  "stem",     "Filler",    0.85),
    (201, "Vase Classic Clear", "hardgood", "Vase",     4.00),
    (202, "Vase Tall Frosted",  "hardgood", "Vase",     6.50),
    (203, "Vase Ruby Cube",     "hardgood", "Vase",     5.25),
    (204, "Ribbon Satin Roll",  "hardgood", "Wrap",     0.40),
    (205, "Care Packet",        "hardgood", "Wrap",     0.15),
]

# --- Synthetic products ------------------------------------------------------
# Each entry expands into Standard / Deluxe / Premium variants.
# base_name, base_price, vase_id, focal_id, focal_qty
PRODUCTS = [
    ("Rose Dozen Crimson",  95.00, 201, 101, 12),
    ("Rose Dozen Blush",    95.00, 203, 102, 12),
    ("Lily Elegance",       85.00, 202, 105,  5),
    ("Tulip Spring Mix",    60.00, 201, 107, 15),
    ("Carnation Cheer",     45.00, 203, 108, 18),
    ("Daisy Sunshine",      50.00, 201, 109, 14),
]

# Variant name, price multiplier, extra ingredients (Ingredient, Note, Qty)
VARIANTS = [
    ("Standard", 1.00, [("Greenery", "Generic", 1)]),
    ("Deluxe",   1.15, [("Greenery", "Generic", 1), ("Filler", "Generic", 1)]),
    ("Premium",  1.35, [("Greenery", "Generic", 1), ("Filler", "Generic", 1),
                        ("Eucalyptus", "Generic", 2)]),
]

rows = []
product_id = 1001
for base_name, base_price, vase_id, focal_id, focal_qty in PRODUCTS:
    focal_name = dict((i[0], i[1]) for i in INVENTORY)[focal_id]
    vase_name = dict((i[0], i[1]) for i in INVENTORY)[vase_id]
    for variant, mult, extras in VARIANTS:
        name = f"{base_name} {variant}"
        price = round(base_price * mult)
        rows.append((product_id, name, price, variant, "", focal_id, focal_name, "", focal_qty))
        for ing, note, qty in extras:
            rows.append((product_id, name, price, variant, "", pd.NA, ing, note, qty))
        rows.append((product_id, name, price, variant, "", vase_id, vase_name, "", 1))
        product_id += 1

df_recipes = pd.DataFrame(
    rows,
    columns=["product_id", "Product", "Price", "Type", "Product Note",
             "item_id", "Ingredient", "Note", "Qty"],
).astype({"item_id": "Int64"})

df_inv = pd.DataFrame(
    INVENTORY, columns=["item_id", "name", "category", "sub_category", "unit_cost"]
)

# --- Categorize ingredients --------------------------------------------------
inv_map = df_inv.set_index("item_id")["category"].to_dict()
df_recipes["Category"] = pd.NA

# Generic placeholders resolve to "Any stem" so the importer creates a
# Category requirement rather than a Specific item link.
for label in ("Greenery", "Filler", "Eucalyptus"):
    mask = df_recipes["Ingredient"] == label
    df_recipes.loc[mask, "item_id"] = pd.NA
    df_recipes.loc[mask, "Ingredient"] = "Any stem"
    df_recipes.loc[mask, "Category"] = "stem"
    df_recipes.loc[mask, "Note"] = label

# Remaining rows inherit their category from the inventory table.
needs_cat = df_recipes["Category"].isna() & df_recipes["item_id"].notna()
df_recipes.loc[needs_cat, "Category"] = df_recipes.loc[needs_cat, "item_id"].map(inv_map)

# --- Emit --------------------------------------------------------------------
df_output = df_recipes.copy()
df_output["item_id"] = df_output["item_id"].astype("object").fillna("")
df_output.to_csv("recipes.csv", index=False)
print(f"Saved {len(df_output)} rows to recipes.csv (synthetic demo data)")
