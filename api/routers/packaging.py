import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.packaging import (
    KitCreate,
    KitDetailOut,
    KitItemCreate,
    KitItemUpdate,
    KitOut,
)
from db.packaging import (
    add_kit_item,
    create_kit,
    deactivate_kit,
    get_kit,
    list_kits,
    remove_kit_item,
    update_kit_item,
)

router = APIRouter(tags=["packaging"])


@router.get("/packaging/kits", response_model=list[KitOut])
def read_kits(
    active_only: bool = True, conn: sqlite3.Connection = Depends(get_db)
) -> list[KitOut]:
    return [KitOut.model_validate(k) for k in list_kits(conn, active_only)]


@router.get("/packaging/kits/{kit_id}", response_model=KitDetailOut)
def read_kit(kit_id: int, conn: sqlite3.Connection = Depends(get_db)) -> KitDetailOut:
    # get_kit raises NotFoundError itself.
    return KitDetailOut.model_validate(get_kit(conn, kit_id))


@router.post("/packaging/kits", response_model=KitDetailOut, status_code=201)
def create_packaging_kit(
    body: KitCreate, conn: sqlite3.Connection = Depends(get_db)
) -> KitDetailOut:
    kit_id = create_kit(conn, body.name)
    return KitDetailOut.model_validate(get_kit(conn, kit_id))


@router.post(
    "/packaging/kits/{kit_id}/items", response_model=KitDetailOut, status_code=201
)
def create_kit_item(
    kit_id: int, body: KitItemCreate, conn: sqlite3.Connection = Depends(get_db)
) -> KitDetailOut:
    """Add a STOCK material to the kit; returns the whole updated kit."""
    add_kit_item(conn, kit_id, body.material_id, body.quantity)
    return KitDetailOut.model_validate(get_kit(conn, kit_id))


@router.patch("/packaging/kits/{kit_id}/items/{material_id}", response_model=KitDetailOut)
def patch_kit_item(
    kit_id: int,
    material_id: int,
    body: KitItemUpdate,
    conn: sqlite3.Connection = Depends(get_db),
) -> KitDetailOut:
    update_kit_item(conn, kit_id, material_id, body.quantity)
    return KitDetailOut.model_validate(get_kit(conn, kit_id))


@router.delete("/packaging/kits/{kit_id}/items/{material_id}", response_model=KitDetailOut)
def delete_kit_item(
    kit_id: int, material_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> KitDetailOut:
    """Remove a material from the kit. Deliberately returns 200 with the updated
    kit (not 204) so the UI can redraw the list without a follow-up request."""
    remove_kit_item(conn, kit_id, material_id)
    return KitDetailOut.model_validate(get_kit(conn, kit_id))


@router.post("/packaging/kits/{kit_id}/deactivate", response_model=KitDetailOut)
def deactivate_packaging_kit(
    kit_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> KitDetailOut:
    # deactivate_kit doesn't check existence; get_kit raises NotFoundError.
    deactivate_kit(conn, kit_id)
    return KitDetailOut.model_validate(get_kit(conn, kit_id))
