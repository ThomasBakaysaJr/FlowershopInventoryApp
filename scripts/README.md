# One-Shot Scripts

Data-prep utilities used to bootstrap the database and image library. These are
**not part of the running app** — `app.py` and `src/` never import them.

> **Run these from the repository root, not from inside `scripts/`.**
> Every path below is relative to the working directory (`inventory.db`,
> `images/recipes/`, `recipes.csv`), so `cd`-ing into `scripts/` will point them
> at files that don't exist.

```bash
python scripts/make_csv.py        # emits a synthetic demo recipes.csv
python scripts/resize_images.py   # images/test/ -> images/recipes/, longest side 400px
python scripts/match_images.py    # fuzzy-matches images/recipes/ filenames to products
python scripts/group_items.py     # backfills variant_group_id by name suffix
```

`match_images.py` and `group_items.py` write directly to `inventory.db`. Back it
up first — neither has a dry-run mode.

`make_csv.py` generates an entirely **synthetic** catalog — invented products,
prices, and item IDs. It ships so the repo has a working example of the
bulk-import format; it is not the shop's real data.
