from pydantic import BaseModel, ConfigDict


class BackupItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    size: int
    # UTC "YYYY-MM-DD HH:MM:SS" (the file's modification time); show it in the store time zone.
    created_at: str


class BackupStatus(BaseModel):
    """The outcome of the last backup attempt (kept in backup-status.json in the backups folder)."""

    model_config = ConfigDict(extra="forbid")

    at: str
    ok: bool
    name: str | None
    # disk_full | locked | integrity | folder | unknown, when it failed.
    reason: str | None
    message: str | None


class BackupsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder: str
    # How many daily backups are kept; older ones are deleted after a new one is verified.
    keep: int
    count: int
    last: BackupStatus | None
    # The newest ten.
    items: list[BackupItem]


class BackupCreated(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    size: int
    created_at: str
    keep: int
    count: int
