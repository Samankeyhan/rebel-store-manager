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
    PAYMENT_METHOD_DUPLICATE_NAME    entity, existing_id
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
    PERIOD_ALREADY_DISTRIBUTED       distribution_id, period_end (the LATEST distribution's), date (the day that
                                     hit it: on or before period_end)
    CATEGORY_IN_USE                  item_count
    CATEGORY_HAS_SUBCATEGORIES       -
    CATEGORY_PARENT_INACTIVE         -
    CATEGORY_DUPLICATE_NAME          entity, existing_id
    NAME_DUPLICATE                   entity (product, material, supplier, partner, packaging_kit,
                                     expense_category), existing_id (None if unknown): the name's
                                     spelling-normalized key already exists (db/names.py)
    PRODUCT_NO_RECIPE                product_id, product_name
    PRODUCT_NO_UNIT_COST             product_id, product_name
    MATERIAL_NO_UNIT_COST            material_id, material_name: a service waste needs the material's unit cost first («ثبت بها»)
    COST_ALREADY_SET                 item_type (MATERIAL | PRODUCT), item_id, item_name, unit_cost (the cost it has)
    SUPPLIER_NOT_FOUND               supplier_id
    AMOUNT_TOO_LARGE                max (MAX_MONEY, db/constants.py); the amount's size is over it,
                                     above or below zero; field says which amount
    QUANTITY_NOT_WHOLE               -
    QUANTITY_OUT_OF_RANGE            min, max (None when that side has no bound)
    PAID_DATE_NOT_ALLOWED            -
    PACKAGING_KIT_NOT_FOUND          packaging_kit_id
    PACKAGING_KIT_INACTIVE           packaging_kit_id
    BACKUP_FAILED                    reason (disk_full | locked | integrity | folder | unknown)
    STOCKTAKE_STALE                  items: [{item_type, item_id, item_name, expected, actual}] whose live
                                     stock differs from the system_quantity the count was made against
    ORDER_ALREADY_VOIDED             order_id, voided_at (UTC), replaced_by_order_id (None when not corrected)
    ORDER_HAS_RETURN                 order_id, status (CANCELLED | REFUNDED): a return was recorded; no void
    ORDER_NOT_COMMITTED              order_id, status: a DRAFT committed nothing, so there is nothing to void
    STOCKTAKE_AFTER_SALE             order_id, item_type, item_id, item_name, stocktake_date (local day): a count
                                     recorded after the sale already took this item's stock as it was
    VOID_REASON_REQUIRED             - (field reason)
    SUPPLIER_REQUIRED_FOR_CREDIT     - (field supplier_id): a purchase not paid in full needs a supplier
    SUPPLIER_PAYMENT_EXCEEDS_DUE     purchase_id (the purchase invoice), outstanding: an allocation is larger than what
                                     the purchase still owes
    SUPPLIER_PAYMENT_EXCEEDS_BALANCE supplier_id (None: purchases with no supplier), outstanding: a payment larger than
                                     everything owed to that supplier (no advances)
    SUPPLIER_PAYMENT_SUPPLIER_MISMATCH purchase_id, supplier_id (the purchase's): it is not that supplier's purchase
    SUPPLIER_PAYMENT_ALLOCATION_MISMATCH amount, allocated: the allocations do not add up to the payment
    SUPPLIER_PAYMENT_BEFORE_PURCHASE purchase_id, purchase_date (local day): a payment day before the day of a purchase
                                     it pays
    SUPPLIER_PAYMENT_NOT_FOUND       payment_id
    PURCHASE_NOT_FOUND               purchase_id (the purchase invoice)
    PURCHASE_DUPLICATE_ITEM          index (0-based line), item_type (MATERIAL | PRODUCT), item_id (field
                                     lines.N.item_id): the same item is already on this purchase
    SERVICE_PURCHASE_NEEDS_TOTAL     index, material_id, material_name (field lines.N.total_paid): a service line of
                                     total 0 would erase the service's price

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
    PERIOD_ALREADY_DISTRIBUTED = "PERIOD_ALREADY_DISTRIBUTED"

    # Categories
    CATEGORY_IN_USE = "CATEGORY_IN_USE"
    CATEGORY_HAS_SUBCATEGORIES = "CATEGORY_HAS_SUBCATEGORIES"
    CATEGORY_PARENT_INACTIVE = "CATEGORY_PARENT_INACTIVE"
    CATEGORY_DUPLICATE_NAME = "CATEGORY_DUPLICATE_NAME"

    # Products / suppliers
    PRODUCT_NO_RECIPE = "PRODUCT_NO_RECIPE"
    PRODUCT_NO_UNIT_COST = "PRODUCT_NO_UNIT_COST"
    COST_ALREADY_SET = "COST_ALREADY_SET"
    MATERIAL_NO_UNIT_COST = "MATERIAL_NO_UNIT_COST"
    SUPPLIER_NOT_FOUND = "SUPPLIER_NOT_FOUND"

    # Names
    NAME_DUPLICATE = "NAME_DUPLICATE"

    # Limits and input shape
    AMOUNT_TOO_LARGE = "AMOUNT_TOO_LARGE"
    QUANTITY_NOT_WHOLE = "QUANTITY_NOT_WHOLE"
    QUANTITY_OUT_OF_RANGE = "QUANTITY_OUT_OF_RANGE"
    PAID_DATE_NOT_ALLOWED = "PAID_DATE_NOT_ALLOWED"

    # Packaging kits
    PACKAGING_KIT_NOT_FOUND = "PACKAGING_KIT_NOT_FOUND"
    PACKAGING_KIT_INACTIVE = "PACKAGING_KIT_INACTIVE"

    # Stocktake
    STOCKTAKE_STALE = "STOCKTAKE_STALE"

    # Voided orders and corrections
    ORDER_ALREADY_VOIDED = "ORDER_ALREADY_VOIDED"
    ORDER_HAS_RETURN = "ORDER_HAS_RETURN"
    ORDER_NOT_COMMITTED = "ORDER_NOT_COMMITTED"
    STOCKTAKE_AFTER_SALE = "STOCKTAKE_AFTER_SALE"
    VOID_REASON_REQUIRED = "VOID_REASON_REQUIRED"

    # Supplier payables
    SUPPLIER_REQUIRED_FOR_CREDIT = "SUPPLIER_REQUIRED_FOR_CREDIT"
    SUPPLIER_PAYMENT_EXCEEDS_DUE = "SUPPLIER_PAYMENT_EXCEEDS_DUE"
    SUPPLIER_PAYMENT_EXCEEDS_BALANCE = "SUPPLIER_PAYMENT_EXCEEDS_BALANCE"
    SUPPLIER_PAYMENT_SUPPLIER_MISMATCH = "SUPPLIER_PAYMENT_SUPPLIER_MISMATCH"
    SUPPLIER_PAYMENT_ALLOCATION_MISMATCH = "SUPPLIER_PAYMENT_ALLOCATION_MISMATCH"
    SUPPLIER_PAYMENT_BEFORE_PURCHASE = "SUPPLIER_PAYMENT_BEFORE_PURCHASE"
    SUPPLIER_PAYMENT_NOT_FOUND = "SUPPLIER_PAYMENT_NOT_FOUND"
    PURCHASE_NOT_FOUND = "PURCHASE_NOT_FOUND"

    # Purchase invoices
    PURCHASE_DUPLICATE_ITEM = "PURCHASE_DUPLICATE_ITEM"
    SERVICE_PURCHASE_NEEDS_TOTAL = "SERVICE_PURCHASE_NEEDS_TOTAL"

    # Backups
    BACKUP_FAILED = "BACKUP_FAILED"


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


class BackupError(AppError):
    """A database backup could not be made (a server-side failure, not bad input: the API answers 500 with the
    usual envelope). `reason` is one of disk_full, locked, integrity, folder, unknown."""

    default_code = ErrorCode.BACKUP_FAILED

    def __init__(self, message: str, reason: str = "unknown"):
        super().__init__(message, details={"reason": reason})
        self.reason = reason
