import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.recipes import RecipeOut
from db.recipes import calculate_recipe_cost, get_recipe

router = APIRouter(tags=["recipes"])


@router.get("/products/{product_id}/recipe", response_model=RecipeOut)
def read_product_recipe(
    product_id: int,
    batch_qty: float = 1,
    conn: sqlite3.Connection = Depends(get_db),
) -> RecipeOut:
    # calculate_recipe_cost raises NotFoundError itself if the product
    # doesn't exist, so no manual existence check is needed here.
    unit_cost_at_qty_1 = calculate_recipe_cost(conn, product_id, 1)
    unit_cost_at_batch_qty = calculate_recipe_cost(conn, product_id, batch_qty)
    items = get_recipe(conn, product_id)
    return RecipeOut.model_validate(
        {
            "items": items,
            "unit_cost_at_qty_1": unit_cost_at_qty_1,
            "unit_cost_at_batch_qty": unit_cost_at_batch_qty,
        }
    )
