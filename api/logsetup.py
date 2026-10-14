"""The application log: `logs/app.log` next to the database file in use, rotating (1 MB x 5), UTF-8, plain text:
`2026-10-14 08:30:12,345 INFO rebel.app message`. Loggers live under `rebel.*`.
It records startup (database, schema), migrations applied, backups made or failed, handled errors (code, status, path:
never the message, the query string or the body) and unexpected errors with a SANITISED traceback (class and the
file/line/function of each frame, never the exception's message, which can hold a name or an amount)."""

import logging
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from db.backup import absolute_db_path

LOG_FILE = "app.log"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 5
FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
ROOT_LOGGER = "rebel"


def logs_dir_for(db_path: str | Path) -> Path:
    return absolute_db_path(db_path).parent / "logs"


def setup_logging(db_path: str | Path) -> RotatingFileHandler | None:
    """Attach the rotating file handler to the `rebel` logger. Returns it (to remove at shutdown), or None when the log
    folder cannot be used: the app runs without a file log rather than not at all."""
    folder = logs_dir_for(db_path)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(folder / LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
    except OSError:
        return None
    handler.setFormatter(logging.Formatter(FORMAT))
    handler.setLevel(logging.INFO)
    logger = logging.getLogger(ROOT_LOGGER)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return handler


def remove_logging(handler: logging.Handler | None) -> None:
    if handler is None:
        return
    logging.getLogger(ROOT_LOGGER).removeHandler(handler)
    handler.close()


def sanitized_traceback(exc: BaseException) -> str:
    """The exception's class and where it happened, without its message."""
    frames = traceback.extract_tb(exc.__traceback__)[-15:]
    where = "\n".join(
        f"  {'/'.join(Path(f.filename).parts[-2:])}:{f.lineno} in {f.name}" for f in frames
    )
    kind = f"{type(exc).__module__}.{type(exc).__qualname__}"
    return f"{kind} (message withheld)\n{where}"
