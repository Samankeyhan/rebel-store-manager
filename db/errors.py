class AppError(ValueError):
    """Base class for all application errors raised by db/."""


class NotFoundError(AppError):
    """A referenced record does not exist."""


class ValidationError(AppError):
    """Bad input."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


class InsufficientStockError(ValidationError):
    """Not enough stock to satisfy a requested quantity."""

    def __init__(self, message: str, item_name: str, needed, available):
        super().__init__(message)
        self.item_name = item_name
        self.needed = needed
        self.available = available


class ConflictError(AppError):
    """Duplicates, or an invalid state transition (e.g. returning an already-refunded order)."""
