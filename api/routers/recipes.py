import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.recipes import RecipeItemCreate, RecipeItemUpdate, RecipeOut
from db.recipes import (
    add_recipe_item,
    calculate_recipe_cost,
    get_recipe,
    remove_recipe_item,
    update_recipe_item,
)

router = APIRouter(tags=["recipes"])


def build_recipe(
    conn: sqlite3.Connection, product_id: int, batch_qty: float = 1
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


@router.get("/products/{product_id}/recipe", response_model=RecipeOut)
def read_product_recipe(
    product_id: int,
    batch_qty: float = 1,
    conn: sqlite3.Connection = Depends(get_db),
) -> RecipeOut:
    return build_recipe(conn, product_id, batch_qty)


@router.post(
    "/products/{product_id}/recipe/items", response_model=RecipeOut, status_code=201
)
def create_recipe_item(
    product_id: int,
    body: RecipeItemCreate,
    conn: sqlite3.Connection = Depends(get_db),
) -> RecipeOut:
    """Add a material to the product's recipe; returns the whole updated recipe."""
    add_recipe_item(
        conn,
        product_id,
        body.material_id,
        body.quantity_needed,
        cost_basis=body.cost_basis,
    )
    return build_recipe(conn, product_id)


@router.patch(
    "/products/{product_id}/recipe/items/{material_id}", response_model=RecipeOut
)
def patch_recipe_item(
    product_id: int,
    material_id: int,
    body: RecipeItemUpdate,
    conn: sqlite3.Connection = Depends(get_db),
) -> RecipeOut:
    """Change a recipe line's quantity. Omitting cost_basis (or sending null)
    keeps the line's existing cost_basis."""
    update_recipe_item(
        conn,
        product_id,
        material_id,
        body.quantity_needed,
        cost_basis=body.cost_basis,
    )
    return build_recipe(conn, product_id)


@router.delete(
    "/products/{product_id}/recipe/items/{material_id}", response_model=RecipeOut
)
def delete_recipe_item(
    product_id: int, material_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> RecipeOut:
    """Remove a recipe line. Deliberately returns 200 with the updated recipe
    (not 204) so the UI can redraw the list without a follow-up request."""
    remove_recipe_item(conn, product_id, material_id)
    return build_recipe(conn, product_id)
