import sqlite3

from fastapi import APIRouter, Depends, Query

from api.deps import get_db
from api.schemas.audit import AuditPageOut
from api.schemas.common import DateStr
from db.audit import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, list_audit_log

router = APIRouter(tags=["audit log"])


@router.get("/audit-log", response_model=AuditPageOut)
def read_audit_log(
    entity_type: str | None = Query(None, description="A table name, e.g. orders"),
    entity_id: str | None = Query(None, description="The row key, with entity_type"),
    op_id: str | None = Query(None, description="One business operation's rows"),
    operation: str | None = Query(None, description="A db/ function name, e.g. record_order"),
    start_date: DateStr | None = Query(None, description="First local day, YYYY-MM-DD"),
    end_date: DateStr | None = Query(None, description="Last local day, YYYY-MM-DD (inclusive)"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
) -> AuditPageOut:
    """The append-only history of every write to accounting data, newest first.
    Read-only: the log is written by database triggers, never through the API."""
    page = list_audit_log(
        conn,
        entity_type=entity_type,
        entity_id=entity_id,
        op_id=op_id,
        operation=operation,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return AuditPageOut.model_validate({**page, "limit": limit, "offset": offset})
