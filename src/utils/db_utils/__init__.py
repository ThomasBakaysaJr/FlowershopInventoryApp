import sys
import types

from ._core import DB_PATH as DB_PATH, get_connection as get_connection, filter_dataframe_by_terms as filter_dataframe_by_terms
from .inventory import (
    get_inventory as get_inventory,
    update_item_details as update_item_details,
    update_inventory_cost as update_inventory_cost,
    add_inventory_item as add_inventory_item,
    get_inventory_categories as get_inventory_categories,
    get_items_by_category as get_items_by_category,
    export_inventory_csv as export_inventory_csv,
    process_bulk_inventory_upload as process_bulk_inventory_upload,
    clear_inventory as clear_inventory,
    process_clipboard_update as process_clipboard_update,
)
from .catalog import (
    get_all_recipes as get_all_recipes,
    get_active_product_options as get_active_product_options,
    get_recipe_requirements as get_recipe_requirements,
    get_product_details as get_product_details,
    get_product_image as get_product_image,
    get_product_image_by_id as get_product_image_by_id,
    get_product_group_id as get_product_group_id,
    check_product_exists as check_product_exists,
    check_product_variant as check_product_variant,
    create_new_product as create_new_product,
    update_product_recipe as update_product_recipe,
    delete_product as delete_product,
    export_products_csv as export_products_csv,
    process_bulk_recipe_upload as process_bulk_recipe_upload,
    clear_products as clear_products,
)
from .production import (
    get_goal_product_id as get_goal_product_id,
    get_production_goals_range as get_production_goals_range,
    get_active_and_scheduled_products as get_active_and_scheduled_products,
    add_production_goal as add_production_goal,
    delete_production_goal as delete_production_goal,
    update_goal_quantity as update_goal_quantity,
    log_production as log_production,
    undo_production as undo_production,
)
from .forecasting import (
    get_forecast_initial_data as get_forecast_initial_data,
    get_production_requirements as get_production_requirements,
    get_forecast_generic_requirements as get_forecast_generic_requirements,
)


class _PatchableModule(types.ModuleType):
    """Propagates DB_PATH assignments to _core so test patches work correctly.

    Tests patch db_utils.DB_PATH = TEST_DB. Without this, _core.DB_PATH
    (which get_connection() reads) would be unaffected.
    """

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == 'DB_PATH':
            from . import _core
            _core.DB_PATH = value


sys.modules[__name__].__class__ = _PatchableModule
