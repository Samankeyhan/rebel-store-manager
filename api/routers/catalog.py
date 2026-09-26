import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.routers.settings import build_settings
from api.schemas.catalog import CatalogOut
from api.schemas.materials import MaterialOut
from api.schemas.packaging import KitDetailOut
from api.schemas.products import ProductOut
from db.materials import list_materials
from db.packaging import get_kit, list_kits
from db.postage import get_current_postage_estimate
from db.products import list_products

router = APIRouter(tags=["catalog"])


@router.get("/catalog", response_model=CatalogOut)
def read_catalog(conn: sqlite3.Connection = Depends(get_db)) -> CatalogOut:
    products = [ProductOut.model_validate(p) for p in list_products(conn)]
    materials = [MaterialOut.model_validate(m) for m in list_materials(conn)]
    kits = [
        KitDetailOut.model_validate(get_kit(conn, kit["id"])) for kit in list_kits(conn)
    ]
    settings = build_settings(conn)
    postage_estimate = get_current_postage_estimate(conn)

    return CatalogOut(
        products=products,
        materials=materials,
        kits=kits,
        settings=settings,
        postage_estimate=postage_estimate,
    )
