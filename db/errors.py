"""Error hierarchy for db/, mapped to HTTP statuses by api/main.py.
`AppError` (base, subclasses ValueError), `NotFoundError`, `ValidationError` (optional `field`), `InsufficientStockError` (`item_name`, `needed`, `available`), `ConflictError`.

Every error carries a stable `code` (an `ErrorCode`) and a `details` dict, sent
to the client next to the English message. The UI decides what to show from the
code and details, never from the message text; messages may be reworded freely.
Each class has a default code; raise sites the UI tells apart pass a specific one."""

from enum import StrEnum


class ErrorCode(StrEnum):
    """Stable error codes. The details each specific code carries:

    MONTH_ALREADY_SETTLED            jalali_year, jalali_month, settlement_id (None if unknown)
    ORDER_NOT_PAID                   order_id, status
    ORDER_ALREADY_SETTLED            order_id, settlement_id
    DATE_IN_FUTURE                   today (YYYY-MM-DD); field says which date
    PAYMENT_METHOD_INACTIVE          payment_method_id
    PAYMENT_METHOD_NOT_FOUND         payment_method_id
    PAYMENT_METHOD_RULE_PENDING      pending_count
    PAYMENT_METHOD_DUPLICATE_NAME    -
    SETTLEMENT_MONTH_NOT_ENDED       jalali_year, jalali_month, month_end
    SETTLEMENT_NOTHING_PENDING       jalali_year, jalali_month
    SETTLEMENT_RACED                 -
    SETTLEMENT_CONFLICT              -
    SETTLEMENT_DATE_BEFORE_MONTH_END jalali_year, jalali_month, month_end
    SETTLEMENT_DATE_BEFORE_PAID      latest_paid_date
    SETTLEMENT_WHOLE_MONTHS_ONLY     -
    SETTLEMENT_ORDER_WRONG_METHOD    order_id
    SETTLEMENT_NOT_MONTHLY           -
    DISTRIBUTION_PERIOD_OVERLAP      distribution_id, period_start, period_end
    DISTRIBUTION_NO_ACTIVE_PARTNERS  -
    DISTRIBUTION_PERCENT_SUM         -
    DISTRIBUTION_EXCEEDS_UNDISTRIBUTED -
    DISTRIBUTION_PERIOD_ORDER        -
    CATEGORY_IN_USE                  item_count
    CATEGORY_HAS_SUBCATEGORIES       -
    CATEGORY_PARENT_INACTIVE         -
    CATEGORY_DUPLICATE_NAME          -
    PRODUCT_NO_RECIPE                product_id, product_name
    PRODUCT_NO_UNIT_COST             product_id, product_name
    SUPPLIER_NOT_FOUND               supplier_id

    The five class defaults (APP_ERROR, NOT_FOUND, VALIDATION_FAILED,
    CONFLICT, INSUFFICIENT_STOCK) carry no details, except INSUFFICIENT_STOCK:
    item_name, needed, available.
    """

    # Class defaults
    APP_ERROR = "APP_ERROR"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CONFLICT = "CONFLICT"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"

    # Paid date / settlement shared
    MONTH_ALREADY_SETTLED = "MONTH_ALREADY_SETTLED"
    ORDER_NOT_PAID = "ORDER_NOT_PAID"
    ORDER_ALREADY_SETTLED = "ORDER_ALREADY_SETTLED"
    DATE_IN_FUTURE = "DATE_IN_FUTURE"

    # Payment methods
    PAYMENT_METHOD_INACTIVE = "PAYMENT_METHOD_INACTIVE"
    PAYMENT_METHOD_NOT_FOUND = "PAYMENT_METHOD_NOT_FOUND"
    PAYMENT_METHOD_RULE_PENDING = "PAYMENT_METHOD_RULE_PENDING"
    PAYMENT_METHOD_DUPLICATE_NAME = "PAYMENT_METHOD_DUPLICATE_NAME"

    # Settlements
    SETTLEMENT_MONTH_NOT_ENDED = "SETTLEMENT_MONTH_NOT_ENDED"
    SETTLEMENT_NOTHING_PENDING = "SETTLEMENT_NOTHING_PENDING"
    SETTLEMENT_RACED = "SETTLEMENT_RACED"
    SETTLEMENT_CONFLICT = "SETTLEMENT_CONFLICT"
    SETTLEMENT_DATE_BEFORE_MONTH_END = "SETTLEMENT_DATE_BEFORE_MONTH_END"
    SETTLEMENT_DATE_BEFORE_PAID = "SETTLEMENT_DATE_BEFORE_PAID"
    SETTLEMENT_WHOLE_MONTHS_ONLY = "SETTLEMENT_WHOLE_MONTHS_ONLY"
    SETTLEMENT_ORDER_WRONG_METHOD = "SETTLEMENT_ORDER_WRONG_METHOD"
    SETTLEMENT_NOT_MONTHLY = "SETTLEMENT_NOT_MONTHLY"

    # Distributions
    DISTRIBUTION_PERIOD_OVERLAP = "DISTRIBUTION_PERIOD_OVERLAP"
    DISTRIBUTION_NO_ACTIVE_PARTNERS = "DISTRIBUTION_NO_ACTIVE_PARTNERS"
    DISTRIBUTION_PERCENT_SUM = "DISTRIBUTION_PERCENT_SUM"
    DISTRIBUTION_EXCEEDS_UNDISTRIBUTED = "DISTRIBUTION_EXCEEDS_UNDISTRIBUTED"
    DISTRIBUTION_PERIOD_ORDER = "DISTRIBUTION_PERIOD_ORDER"

    # Categories
    CATEGORY_IN_USE = "CATEGORY_IN_USE"
    CATEGORY_HAS_SUBCATEGORIES = "CATEGORY_HAS_SUBCATEGORIES"
    CATEGORY_PARENT_INACTIVE = "CATEGORY_PARENT_INACTIVE"
    CATEGORY_DUPLICATE_NAME = "CATEGORY_DUPLICATE_NAME"

    # Products / suppliers
    PRODUCT_NO_RECIPE = "PRODUCT_NO_RECIPE"
    PRODUCT_NO_UNIT_COST = "PRODUCT_NO_UNIT_COST"
    SUPPLIER_NOT_FOUND = "SUPPLIER_NOT_FOUND"


DEFAULT_CODES = frozenset({
    ErrorCode.APP_ERROR,
    ErrorCode.NOT_FOUND,
    ErrorCode.VALIDATION_FAILED,
    ErrorCode.CONFLICT,
    ErrorCode.INSUFFICIENT_STOCK,
})


class AppError(ValueError):
    """Base class for all application errors raised by db/."""

    default_code = ErrorCode.APP_ERROR

    def __init__(self, message: str, *, code: ErrorCode | None = None, details: dict | None = None):
        super().__init__(message)
        self.code = code or self.default_code
        self.details = dict(details or {})


class NotFoundError(AppError):
    """A referenced record does not exist."""

    default_code = ErrorCode.NOT_FOUND


class ValidationError(AppError):
    """Bad input."""

    default_code = ErrorCode.VALIDATION_FAILED

    def __init__(
        self,
        message: str,
        field: str | None = None,
        *,
        code: ErrorCode | None = None,
        details: dict | None = None,
    ):
        super().__init__(message, code=code, details=details)
        self.field = field


class InsufficientStockError(ValidationError):
    """Not enough stock to satisfy a requested quantity."""

    default_code = ErrorCode.INSUFFICIENT_STOCK

    def __init__(self, message: str, item_name: str, needed, available):
        super().__init__(
            message,
            details={"item_name": item_name, "needed": needed, "available": available},
        )
        self.item_name = item_name
        self.needed = needed
        self.available = available


class ConflictError(AppError):
    """Duplicates, or an invalid state transition (e.g. returning an already-refunded order)."""

    default_code = ErrorCode.CONFLICT
