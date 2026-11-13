# api/ rules

- Routers call `db/` functions and shape the result. No SQL, no money math, no new logic (composing existing `db/` calls is fine). Missing computation → add it to `db/`.
- Money is integer Rial on the wire, in requests and responses; the display currency never reaches the API.
- Schemas (`api/schemas/`): field names match `db/` dict keys; request models `<Thing>Create`/`<Thing>Update` with `extra="forbid"`; money fields typed `Money` (strict int Rial, so float/string/bool → 422).
- Boolean-ish fields stay int 0/1 in responses. Intentional; don't convert to bool.
- Writes return the resource re-fetched via the GET getter. Create 201, update/action 200. DELETE of a recipe/kit item returns 200 with the updated recipe/kit.
- Partial updates (PATCH): `model_dump(exclude_unset=True)`; omitted = unchanged, explicit `null` = clear, except for fields that are NOT NULL: `PATCH /payment-methods` `fee_bps` and `fee_fixed` cannot be cleared with `null` (422, field set); only `fee_cap` can.
- `POST /orders`:
  - `packaging_kit_id`: `"default"`/omitted = channel default, `null` = none, int = that one (strict int).
  - `payment_method_id`: `"default"`/omitted = channel default, int = that one (strict int). A sale always has one: `null`, or a channel with no default, is 422 `PAYMENT_METHOD_REQUIRED` (every status, DRAFT too). Orders from before the rule may have none.
  - `POST /orders/bulk-status`: PAID → COMPLETED for 1..200 orders, one transaction and audit operation; any non-PAID order is a 409 `ORDER_BULK_NOT_ELIGIBLE` for the whole call.
  - `shipping_charge`, `postage_cost`, `transaction_fee`: `null`/omitted = default/computed; `0` is a real override.
  - `paid_date` only for PAID/COMPLETED. Also on `POST /orders/{id}/status`; moved via `PATCH /orders/{id}/paid-date`.
  - `PATCH /orders/{id}` (light edit, `OrderEdit`): only the sent fields change; `payment_method_id` and `paid_date` cannot be `null`; `transaction_fee` only with `payment_method_id` or `shipping_charge`. `POST /orders/{id}/edit-preview` takes the same body, writes nothing and returns before/after plus `blockers`.
- `POST /settlements`: `order_ids` for IMMEDIATE/DAYS_AFTER; `jalali_year` + `jalali_month` for DAY_OF_NEXT_MONTH (`order_ids` there is a 422). `difference` comes from `db/`.
- `PUT /settings/{key}`: only `VALID_SETTING_KEYS`, enforced in `db.settings.set_setting`.
- Tests: `with TestClient(app)` runs `init_db` on `$REBEL_DB`; the autouse fixture in `tests/conftest.py` points it at a temp file. Keep it.
- Money fields use `Money` (strict int, bounded ±`MAX_MONEY`); quantities use `WholeQuantity` / `PositiveQuantity` / `Quantity` / `QuantityChange` (`api/schemas/common.py`). Never a bare `int`/`float` for either. Every error, including FastAPI's own 422, is the `{"error": {...}}` envelope (`api/validation.py`); a new `ErrorCode` also needs its details model (`api/schemas/errors.py`).
- Logging: `api/logsetup.py` writes `logs/app.log` next to the database. Log codes, status and path only: never a body, a name, an amount, a query string or an exception message (`sanitized_traceback`). Unexpected errors become a plain 500 envelope (`catch_unexpected_errors`).
