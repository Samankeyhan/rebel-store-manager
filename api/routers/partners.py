import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.partners import PartnerOut, PartnerPayoutOut, PartnerTotalOut
from db.errors import NotFoundError
from db.distributions import get_partner_payout_history, get_partner_totals
from db.partners import get_partner, list_partners

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
