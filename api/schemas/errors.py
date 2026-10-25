"""The error envelope {"error": {type, code, message, field, details}} with `details` typed per error code.

`ERROR_DETAILS` maps EVERY `ErrorCode` to the model of its `details` (`NoDetails` for a code that carries none).
`ErrorBody` is a union discriminated on `code`: one body model per distinct details model, so OpenAPI (and the generated
frontend types) say exactly which keys a given code carries. The ErrorCode enum itself is added to the OpenAPI components
by `api/main.py` (the per-body `code` Literals do not reference it).
Adding an ErrorCode without an entry here fails `tests/test_error_details_schema.py`; so does a raise site whose literal
`details` keys differ from the model."""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, create_model

from db.errors import ErrorCode


class _Details(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorItem(BaseModel):
    """One request-validation error: where, what, which pydantic error type (never the input)."""

    model_config = ConfigDict(extra="forbid")

    loc: list[str | int]
    msg: str
    type: str


class NoDetails(_Details):
    """The code carries no details: `details` is {}."""


class ValidationFailedDetails(_Details):
    # Only for a request-shape error (type RequestValidationError); a db/ refusal has {}.
    errors: list[ErrorItem] | None = None


class AmountTooLargeDetails(_Details):
    max: int
    errors: list[ErrorItem] | None = None


class QuantityOutOfRangeDetails(_Details):
    # The bound that was crossed; the other side is null.
    min: float | None
    max: float | None
    errors: list[ErrorItem] | None = None


class MonthSettledDetails(_Details):
    jalali_year: int
    jalali_month: int
    settlement_id: int | None


class JalaliMonthDetails(_Details):
    jalali_year: int
    jalali_month: int


class MonthEndDetails(_Details):
    jalali_year: int
    jalali_month: int
    month_end: str


class OrderNotPaidDetails(_Details):
    order_id: int
    status: str


class OrderSettledDetails(_Details):
    order_id: int
    settlement_id: int | None


class OrderRefDetails(_Details):
    order_id: int


class DateInFutureDetails(_Details):
    today: str


class LatestPaidDetails(_Details):
    latest_paid_date: str | None


class PaymentMethodRefDetails(_Details):
    payment_method_id: int


class RulePendingDetails(_Details):
    pending_count: int


class DistributionOverlapDetails(_Details):
    distribution_id: int
    period_start: str
    period_end: str


class PeriodDistributedDetails(_Details):
    distribution_id: int
    period_end: str
    date: str


class CategoryInUseDetails(_Details):
    item_count: int


class ProductRefDetails(_Details):
    product_id: int
    product_name: str


class MaterialRefDetails(_Details):
    material_id: int
    material_name: str


class CostRefDetails(_Details):
    item_type: str
    item_id: int
    item_name: str
    unit_cost: int


class SupplierRefDetails(_Details):
    supplier_id: int


class KitRefDetails(_Details):
    packaging_kit_id: int


class InsufficientStockDetails(_Details):
    item_name: str
    needed: float
    available: float


class StaleItem(BaseModel):
    """An item whose live stock differs from the quantity the count was made against."""

    model_config = ConfigDict(extra="forbid")

    item_type: str
    item_id: int
    item_name: str
    expected: float
    actual: float


class StocktakeStaleDetails(_Details):
    items: list[StaleItem]


class OrderVoidedDetails(_Details):
    order_id: int
    voided_at: str
    replaced_by_order_id: int | None


class StocktakeAfterSaleDetails(_Details):
    order_id: int
    item_type: str
    item_id: int
    item_name: str
    stocktake_date: str


class BackupFailedDetails(_Details):
    # disk_full | locked | integrity | folder | unknown
    reason: str


class NameDuplicateDetails(_Details):
    entity: str
    existing_id: int | None


class SupplierRequiredForCreditDetails(_Details):
    """Carries nothing (field supplier_id): a purchase not paid in full needs a supplier. Its own model, so the generated
    types name it."""


class PurchaseRefDetails(_Details):
    # the purchase invoice
    purchase_id: int


class PurchaseDueDetails(_Details):
    purchase_id: int
    outstanding: int


class SupplierBalanceDetails(_Details):
    # None: purchases that have no supplier
    supplier_id: int | None
    outstanding: int


class PurchaseSupplierDetails(_Details):
    purchase_id: int
    # the purchase's own supplier
    supplier_id: int | None


class AllocationMismatchDetails(_Details):
    amount: int
    allocated: int


class PaymentBeforePurchaseDetails(_Details):
    purchase_id: int
    # the purchase's local day
    purchase_date: str


class SupplierPaymentRefDetails(_Details):
    payment_id: int


class PurchaseDuplicateItemDetails(_Details):
    # the 0-based line that repeats an item
    index: int
    # MATERIAL | PRODUCT
    item_type: str
    item_id: int


class ServicePurchaseNeedsTotalDetails(_Details):
    index: int
    material_id: int
    material_name: str


class PurchaseAlreadyCancelledDetails(_Details):
    purchase_id: int
    cancelled_at: str | None
    replaced_by_purchase_id: int | None


class PurchaseHasPaymentsDetails(_Details):
    purchase_id: int
    paid: int
    payment_ids: list[int]
    # 1 when a payment also pays another purchase
    shared: int


class PurchaseLineDetails(_Details):
    purchase_id: int
    # 0-based, materials and services by line id, then products by line id
    line_index: int
    # MATERIAL | PRODUCT
    item_type: str
    item_id: int
    item_name: str


class PurchaseStockUsedDetails(PurchaseLineDetails):
    current_stock: float
    quantity_bought: float


class StocktakeAfterPurchaseDetails(PurchaseLineDetails):
    # local day
    stocktake_date: str


class LaterCostEvent(_Details):
    # PURCHASE, PRODUCTION_OUTPUT, RETURN, ADJUSTMENT
    reason: str
    # None for a later service purchase (it has no movement)
    movement_id: int | None
    date: str
    purchase_id: int | None
    invoice_number: str | None


class PurchaseCostChangedDetails(PurchaseLineDetails):
    later: list[LaterCostEvent]
    # 1 when the cost changed with no later movement (a set cost)
    cost_changed_without_movement: int


class PurchaseCorrectionBelowPaidDetails(_Details):
    purchase_id: int
    paid: int
    new_total: int


C = ErrorCode

# Every ErrorCode -> the model of its details.
ERROR_DETAILS: dict[ErrorCode, type[_Details]] = {
    **{code: NoDetails for code in (
        C.APP_ERROR, C.NOT_FOUND, C.CONFLICT,
        C.SETTLEMENT_RACED, C.SETTLEMENT_CONFLICT, C.SETTLEMENT_WHOLE_MONTHS_ONLY, C.SETTLEMENT_NOT_MONTHLY,
        C.DISTRIBUTION_NO_ACTIVE_PARTNERS, C.DISTRIBUTION_PERCENT_SUM, C.DISTRIBUTION_EXCEEDS_UNDISTRIBUTED,
        C.DISTRIBUTION_PERIOD_ORDER,
        C.CATEGORY_HAS_SUBCATEGORIES, C.CATEGORY_PARENT_INACTIVE,
        C.PAID_DATE_NOT_ALLOWED, C.VOID_REASON_REQUIRED,
    )},
    C.VALIDATION_FAILED: ValidationFailedDetails,
    C.QUANTITY_NOT_WHOLE: ValidationFailedDetails,
    C.AMOUNT_TOO_LARGE: AmountTooLargeDetails,
    C.QUANTITY_OUT_OF_RANGE: QuantityOutOfRangeDetails,
    C.INSUFFICIENT_STOCK: InsufficientStockDetails,
    C.MONTH_ALREADY_SETTLED: MonthSettledDetails,
    C.SETTLEMENT_NOTHING_PENDING: JalaliMonthDetails,
    C.SETTLEMENT_MONTH_NOT_ENDED: MonthEndDetails,
    C.SETTLEMENT_DATE_BEFORE_MONTH_END: MonthEndDetails,
    C.ORDER_NOT_PAID: OrderNotPaidDetails,
    C.ORDER_ALREADY_SETTLED: OrderSettledDetails,
    C.SETTLEMENT_ORDER_WRONG_METHOD: OrderRefDetails,
    C.DATE_IN_FUTURE: DateInFutureDetails,
    C.SETTLEMENT_DATE_BEFORE_PAID: LatestPaidDetails,
    C.PAYMENT_METHOD_INACTIVE: PaymentMethodRefDetails,
    C.PAYMENT_METHOD_NOT_FOUND: PaymentMethodRefDetails,
    C.PAYMENT_METHOD_RULE_PENDING: RulePendingDetails,
    C.DISTRIBUTION_PERIOD_OVERLAP: DistributionOverlapDetails,
    C.PERIOD_ALREADY_DISTRIBUTED: PeriodDistributedDetails,
    C.CATEGORY_IN_USE: CategoryInUseDetails,
    C.PRODUCT_NO_RECIPE: ProductRefDetails,
    C.PRODUCT_NO_UNIT_COST: ProductRefDetails,
    C.COST_ALREADY_SET: CostRefDetails,
    C.MATERIAL_NO_UNIT_COST: MaterialRefDetails,
    C.SUPPLIER_NOT_FOUND: SupplierRefDetails,
    C.PACKAGING_KIT_NOT_FOUND: KitRefDetails,
    C.PACKAGING_KIT_INACTIVE: KitRefDetails,
    C.STOCKTAKE_STALE: StocktakeStaleDetails,
    C.ORDER_ALREADY_VOIDED: OrderVoidedDetails,
    C.ORDER_HAS_RETURN: OrderNotPaidDetails,
    C.ORDER_NOT_COMMITTED: OrderNotPaidDetails,
    C.STOCKTAKE_AFTER_SALE: StocktakeAfterSaleDetails,
    C.BACKUP_FAILED: BackupFailedDetails,
    C.NAME_DUPLICATE: NameDuplicateDetails,
    C.CATEGORY_DUPLICATE_NAME: NameDuplicateDetails,
    C.PAYMENT_METHOD_DUPLICATE_NAME: NameDuplicateDetails,
    C.SUPPLIER_REQUIRED_FOR_CREDIT: SupplierRequiredForCreditDetails,
    C.SUPPLIER_PAYMENT_EXCEEDS_DUE: PurchaseDueDetails,
    C.SUPPLIER_PAYMENT_EXCEEDS_BALANCE: SupplierBalanceDetails,
    C.SUPPLIER_PAYMENT_SUPPLIER_MISMATCH: PurchaseSupplierDetails,
    C.SUPPLIER_PAYMENT_ALLOCATION_MISMATCH: AllocationMismatchDetails,
    C.SUPPLIER_PAYMENT_BEFORE_PURCHASE: PaymentBeforePurchaseDetails,
    C.SUPPLIER_PAYMENT_NOT_FOUND: SupplierPaymentRefDetails,
    C.PURCHASE_NOT_FOUND: PurchaseRefDetails,
    C.PURCHASE_DUPLICATE_ITEM: PurchaseDuplicateItemDetails,
    C.SERVICE_PURCHASE_NEEDS_TOTAL: ServicePurchaseNeedsTotalDetails,
    C.PURCHASE_ALREADY_CANCELLED: PurchaseAlreadyCancelledDetails,
    C.PURCHASE_HAS_PAYMENTS: PurchaseHasPaymentsDetails,
    C.PURCHASE_STOCK_USED: PurchaseStockUsedDetails,
    C.STOCKTAKE_AFTER_PURCHASE: StocktakeAfterPurchaseDetails,
    C.PURCHASE_COST_CHANGED_SINCE: PurchaseCostChangedDetails,
    C.PURCHASE_COST_HISTORY_UNKNOWN: PurchaseLineDetails,
    C.PURCHASE_CORRECTION_BELOW_PAID: PurchaseCorrectionBelowPaidDetails,
}


class _ErrorBodyBase(BaseModel):
    """An app error. The client decides what to show from `code` and `details`; `message` is English text for logs only."""

    model_config = ConfigDict(extra="forbid")

    type: str
    message: str
    field: str | None = None


def _body_models() -> list[type[BaseModel]]:
    by_details: dict[type[_Details], list[ErrorCode]] = {}
    for code in ErrorCode:  # enum order, so the schema is stable
        by_details.setdefault(ERROR_DETAILS[code], []).append(code)
    models = []
    for details, codes in by_details.items():
        name = "ErrorBodyEmpty" if details is NoDetails else "ErrorBody" + details.__name__.removesuffix("Details")
        models.append(
            create_model(
                name,
                __base__=_ErrorBodyBase,
                code=(Literal[tuple(str(c) for c in codes)], ...),
                details=(details, ...),
            )
        )
    return models


ERROR_BODIES = _body_models()
ErrorBody = Annotated[Union[tuple(ERROR_BODIES)], Field(discriminator="code")]


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorBody
