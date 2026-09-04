import sys
import types

from ._core import DB_PATH as DB_PATH
from ._core import filter_dataframe_by_terms as filter_dataframe_by_terms
from ._core import get_connection as get_connection
from .catalog import (
    check_product_exists as check_product_exists,
)
from .catalog import (
    check_product_variant as check_product_variant,
)
from .catalog import (
    clear_products as clear_products,
)
from .catalog import (
    create_new_product as create_new_product,
)
from .catalog import (
    delete_product as delete_product,
)
from .catalog import (
    export_products_csv as export_products_csv,
)
from .catalog import (
    get_active_product_options as get_active_product_options,
)
from .catalog import (
    get_all_recipes as get_all_recipes,
)
from .catalog import (
    get_product_details as get_product_details,
)
from .catalog import (
    get_product_group_id as get_product_group_id,
)
from .catalog import (
    get_product_image as get_product_image,
)
from .catalog import (
    get_product_image_by_id as get_product_image_by_id,
)
from .catalog import (
    get_recipe_requirements as get_recipe_requirements,
)
from .catalog import (
    process_bulk_recipe_upload as process_bulk_recipe_upload,
)
from .catalog import (
    update_product_recipe as update_product_recipe,
)
from .forecasting import (
    get_forecast_generic_requirements as get_forecast_generic_requirements,
)
from .forecasting import (
    get_forecast_initial_data as get_forecast_initial_data,
)
from .inventory import (
    add_inventory_item as add_inventory_item,
)
from .inventory import (
    clear_inventory as clear_inventory,
)
from .inventory import (
    export_inventory_csv as export_inventory_csv,
)
from .inventory import (
    get_inventory as get_inventory,
)
from .inventory import (
    get_inventory_categories as get_inventory_categories,
)
from .inventory import (
    get_items_by_category as get_items_by_category,
)
from .inventory import (
    process_bulk_inventory_upload as process_bulk_inventory_upload,
)
from .inventory import (
    process_clipboard_update as process_clipboard_update,
)
from .inventory import (
    update_inventory_cost as update_inventory_cost,
)
from .inventory import (
    update_item_details as update_item_details,
)
from .production import (
    add_production_goal as add_production_goal,
)
from .production import (
    delete_production_goal as delete_production_goal,
)
from .production import (
    get_active_and_scheduled_products as get_active_and_scheduled_products,
)
from .production import (
    get_goal_product_id as get_goal_product_id,
)
from .production import (
    get_production_goals_range as get_production_goals_range,
)
from .production import (
    log_production as log_production,
)
from .production import (
    undo_production as undo_production,
)
from .production import (
    update_goal_quantity as update_goal_quantity,
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
