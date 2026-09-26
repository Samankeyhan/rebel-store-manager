import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.materials import MaterialCreate, MaterialOut
from db.errors import NotFoundError
from db.materials import (
    add_material,
    deactivate_material,
    get_low_stock_materials,
    get_material,
    list_materials,
)

router = APIRouter(tags=["materials"])


@router.get("/materials", response_model=list[MaterialOut])
def read_materials(
    active_only: bool = True, conn: sqlite3.Connection = Depends(get_db)
) -> list[MaterialOut]:
    return [MaterialOut.model_validate(m) for m in list_materials(conn, active_only)]


# Registered before /materials/{material_id} so "low-stock" is never treated
# as a material_id.
@router.get("/materials/low-stock", response_model=list[MaterialOut])
def read_low_stock_materials(
    threshold: float, conn: sqlite3.Connection = Depends(get_db)
) -> list[MaterialOut]:
    return [
        MaterialOut.model_validate(m) for m in get_low_stock_materials(conn, threshold)
    ]


@router.get("/materials/{material_id}", response_model=MaterialOut)
def read_material(
    material_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> MaterialOut:
    return build_material(conn, material_id)


def build_material(conn: sqlite3.Connection, material_id: int) -> MaterialOut:
    material = get_material(conn, material_id)
    if material is None:
        raise NotFoundError(f"Material with id {material_id} does not exist")
    return MaterialOut.model_validate(material)


@router.post("/materials", response_model=MaterialOut, status_code=201)
def create_material(
    body: MaterialCreate, conn: sqlite3.Connection = Depends(get_db)
) -> MaterialOut:
    material_id = add_material(
        conn,
        name=body.name,
        type=body.type,
        unit_cost=body.unit_cost,
        unit=body.unit,
        initial_stock=body.initial_stock,
    )
    return build_material(conn, material_id)


@router.post("/materials/{material_id}/deactivate", response_model=MaterialOut)
def deactivate(
    material_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> MaterialOut:
    # deactivate_material doesn't check existence; build_material 404s instead.
    deactivate_material(conn, material_id)
    return build_material(conn, material_id)
