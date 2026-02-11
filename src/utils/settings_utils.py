import json
import os
import logging

logger = logging.getLogger(__name__)

SETTINGS_PATH = 'settings.json'

DEFAULT_SETTINGS = {
    "cost_formula": {
        "additives": [
            {"name": "Labor", "type": "Percentage", "value": 20.0}
        ],
        "markup": 3.5
    },
    "low_stock_threshold": 25
}

def load_settings():
    if not os.path.exists(SETTINGS_PATH):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS
    
    try:
        with open(SETTINGS_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return DEFAULT_SETTINGS

def save_settings(settings):
    try:
        with open(SETTINGS_PATH, 'w') as f:
            json.dump(settings, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return False

def calculate_price(cogs, settings):
    """Calculates price based on COGS and settings formula."""
    formula = settings.get('cost_formula', DEFAULT_SETTINGS['cost_formula'])
    
    additives_cost = 0.0
    breakdown = []
    
    # 1. Apply Additives (Pre-Markup)
    for item in formula.get('additives', []):
        try:
            val = float(item['value'])
            name = item['name']
            if item['type'] == 'Percentage':
                # % of COGS
                amt = cogs * (val / 100.0)
                breakdown.append(f"{name} ({val}%): ${amt:.2f}")
            else:
                # Fixed Amount
                amt = val
                breakdown.append(f"{name} (Fixed): ${amt:.2f}")
            
            additives_cost += amt
        except (ValueError, KeyError):
            continue
            
    total_cost = cogs + additives_cost
    
    # 2. Apply Markup
    markup = float(formula.get('markup', 3.5))
    suggested_price = total_cost * markup
    
    return suggested_price, total_cost, breakdown, markup