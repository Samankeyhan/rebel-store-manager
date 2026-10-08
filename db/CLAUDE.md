# db/ rules

- `db/` owns all SQL and business logic; no `print()`/`input()`. `pdf/` and `api/` only call `db/` functions. Need a new query → add it here.
- Every write: `with transaction(conn):` (nests via savepoints). Never `commit()`, `rollback()` or `BEGIN` directly.
- "Today" only via `timeutil.today_local(conn)`, never `date.today()`/`datetime.now()`. Tests monkeypatch `today_local` in the module under test. All timezone work in `timeutil`; Jalali math in `jalali.py`.
- Money is integer Rial, never float; all money rounding is half-even to the Rial. `round()` is half-even; reconcile leftovers so totals sum exactly (see `distributions._compute_share_amounts`). Quantities may be REAL; money never.
- Raise errors from `errors.py` (`NotFoundError`, `ValidationError(field=)`, `InsufficientStockError`, `ConflictError`); the API maps them to HTTP.
- Boolean-ish columns stay int 0/1.
- Low-stock `threshold` is always caller-supplied; there is no per-material minimum column yet. A minimum-stock column is a planned task; ask first.
- Categories: `validate_assignable` decides placement. `products.category` is legacy; don't read it.
- `orders.record_order`: `None` shipping/postage = channel default (0 is a real zero); `transaction_fee=None` = computed from the payment method.
- Partner distributions are payouts, not expenses: distributions may read `get_profit_and_loss` but never write `orders`/`order_items`/`expenses`; no report queries `partners`/`profit_distributions`/`distribution_shares`.
- Display currency conversion (Rial → Toman) happens only in `currency.py` (guarded by `tests/test_no_money_scaling.py`); every other module works in integer Rial.
