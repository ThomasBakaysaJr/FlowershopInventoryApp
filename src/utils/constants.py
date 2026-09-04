"""Central place for business-level constants and their thin accessors.

Variants and time slots are kept as lists-of-dicts (rather than scattered
parallel maps) so the deferred migration to user-configurable settings is a
one-line swap inside each accessor — consumers never need to change.
"""


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------

VARIANTS: list[dict] = [
    {"code": "STD", "label": "Standard", "color": "green", "order": 1},
    {"code": "DLX", "label": "Deluxe",   "color": "blue",  "order": 2},
    {"code": "PRM", "label": "Premium",  "color": "red",   "order": 3},
]

# Suffix → code mapping used when parsing product names like "Spring Mix Deluxe".
VARIANT_SUFFIX_MAP = {"standard": "STD", "deluxe": "DLX", "premium": "PRM"}


def _find_variant(code: str) -> dict | None:
    for v in VARIANTS:
        if v["code"] == code:
            return v
    return None


def variant_label(code: str) -> str:
    """Long-form label for a variant code; falls back to the code itself."""
    v = _find_variant(code)
    return v["label"] if v else code


def variant_color(code: str) -> str:
    """Streamlit markdown color name for a variant code; defaults to 'grey'."""
    v = _find_variant(code)
    return v["color"] if v else "grey"


def variant_order(code: str) -> int:
    """Sort order for a variant code; unknowns go to the end."""
    v = _find_variant(code)
    return v["order"] if v else 99


def variant_codes_sorted() -> list[str]:
    """All variant codes in display order."""
    return [v["code"] for v in sorted(VARIANTS, key=lambda v: v["order"])]


def variant_badge(code: str) -> str:
    """Colored markdown badge for a variant, e.g. ':green[**[STD]**]'."""
    color = variant_color(code)
    return f":{color}[**[{code}]**]"


def strip_variant_suffix(name: str) -> str:
    """Strip a trailing variant label from a product name.

    e.g. 'Spring Mix Deluxe' → 'Spring Mix'. Returns the name unchanged if
    no known variant label is present at the end.
    """
    for v in VARIANTS:
        label = v["label"]
        if name.endswith(label):
            return name.removesuffix(label).strip()
    return name


# ---------------------------------------------------------------------------
# Time slots
# ---------------------------------------------------------------------------

TIME_SLOTS: list[dict] = [
    {"code": "AM",  "label": "AM",  "color": "blue",   "order": 1},
    {"code": "PM",  "label": "PM",  "color": "orange", "order": 2},
    {"code": "ANY", "label": "Any", "color": None,     "order": 3},
]


def _find_time_slot(code: str) -> dict | None:
    for s in TIME_SLOTS:
        if s["code"] == code:
            return s
    return None


def time_slot_label(code: str) -> str:
    s = _find_time_slot(code)
    return s["label"] if s else code


def time_slot_color(code: str) -> str | None:
    s = _find_time_slot(code)
    return s["color"] if s else None


def time_slot_rank(code: str) -> int:
    """Sort rank for a time-slot code; unknowns go to the end."""
    s = _find_time_slot(code)
    return s["order"] if s else 99


# ---------------------------------------------------------------------------
# Operational constants (not business-configurable)
# ---------------------------------------------------------------------------

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB cap on CSV / image uploads

# Streamlit fragment refresh intervals, in seconds. Admin views update faster
# because staff are actively editing; read-only dashboards are slower.
FRAGMENT_REFRESH_SECONDS = {
    "stock_levels":        10,
    "production_viewer":   10,
    "production_overview": 60,
    "weekly_dashboard":    120,
}
