import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.packaging import KitDetailOut, KitOut
from db.packaging import get_kit, list_kits

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
