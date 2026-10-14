from fastapi import APIRouter

from api.deps import db_path
from api.schemas.errors import ErrorEnvelope
from api.schemas.backups import BackupCreated, BackupsOut, BackupStatus
from db.backup import DEFAULT_KEEP, backups_dir_for, list_backups, make_backup, read_status

router = APIRouter(tags=["backups"])

RECENT = 10


@router.get("/backups", response_model=BackupsOut)
def read_backups() -> BackupsOut:
    """The backups folder of the served database: where it is, how many daily backups it holds, the outcome of the
    last attempt and the newest ten. Restoring is manual (docs/RUNNING.md)."""
    folder = backups_dir_for(db_path())
    items = list_backups(folder)
    status = read_status(folder)
    return BackupsOut(
        folder=str(folder),
        keep=DEFAULT_KEEP,
        count=len(items),
        last=BackupStatus.model_validate(status) if status else None,
        items=items[:RECENT],
    )


@router.post(
    "/backups",
    response_model=BackupCreated,
    status_code=201,
    responses={500: {"model": ErrorEnvelope, "description": "BACKUP_FAILED (details.reason)"}},
)
def create_backup() -> BackupCreated:
    """Back the database up now (online backup, verified, rotated). A failure is 500 BACKUP_FAILED, details {reason}."""
    result = make_backup(db_path())
    return BackupCreated(
        name=result["name"], size=result["size"], created_at=result["created_at"], keep=DEFAULT_KEEP, count=result["kept"]
    )
