import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.partners import (
    PartnerCreate,
    PartnerOut,
    PartnerPayoutOut,
    PartnerPercentageUpdate,
    PartnerTotalOut,
)
from db.errors import NotFoundError
from db.distributions import get_partner_payout_history, get_partner_totals
from db.partners import (
    add_partner,
    deactivate_partner,
    get_partner,
    list_partners,
    update_partner_percentage,
)

router = APIRouter(tags=["partners"])


@router.get("/partners", response_model=list[PartnerOut])
def read_partners(
    active_only: bool = True, conn: sqlite3.Connection = Depends(get_db)
) -> list[PartnerOut]:
    return [PartnerOut.model_validate(p) for p in list_partners(conn, active_only)]


@router.get("/partners/totals", response_model=list[PartnerTotalOut])
def read_partner_totals(
    conn: sqlite3.Connection = Depends(get_db),
) -> list[PartnerTotalOut]:
    totals = get_partner_totals(conn)
    return [PartnerTotalOut.model_validate(t) for t in totals]


@router.get("/partners/{partner_id}/payouts", response_model=list[PartnerPayoutOut])
def read_partner_payouts(
    partner_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> list[PartnerPayoutOut]:
    # get_partner_payout_history doesn't check the partner exists — an
    # unknown id would otherwise silently return an empty list.
    if get_partner(conn, partner_id) is None:
        raise NotFoundError(f"Partner with id {partner_id} does not exist")
    payouts = get_partner_payout_history(conn, partner_id)
    return [PartnerPayoutOut.model_validate(p) for p in payouts]


def build_partner(conn: sqlite3.Connection, partner_id: int) -> PartnerOut:
    partner = get_partner(conn, partner_id)
    if partner is None:
        raise NotFoundError(f"Partner with id {partner_id} does not exist")
    return PartnerOut.model_validate(partner)


@router.post("/partners", response_model=PartnerOut, status_code=201)
def create_partner(
    body: PartnerCreate, conn: sqlite3.Connection = Depends(get_db)
) -> PartnerOut:
    partner_id = add_partner(
        conn,
        body.name,
        body.current_percentage,
        phone=body.phone,
        email=body.email,
        notes=body.notes,
    )
    return build_partner(conn, partner_id)


@router.patch("/partners/{partner_id}/percentage", response_model=PartnerOut)
def patch_partner_percentage(
    partner_id: int,
    body: PartnerPercentageUpdate,
    conn: sqlite3.Connection = Depends(get_db),
) -> PartnerOut:
    update_partner_percentage(conn, partner_id, body.current_percentage)
    return build_partner(conn, partner_id)


@router.post("/partners/{partner_id}/deactivate", response_model=PartnerOut)
def deactivate(partner_id: int, conn: sqlite3.Connection = Depends(get_db)) -> PartnerOut:
    deactivate_partner(conn, partner_id)
    return build_partner(conn, partner_id)
