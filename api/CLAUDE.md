# api/ rules

- Routers call `db/` functions and shape the result. No SQL, no money math, no new logic (composing existing `db/` calls is fine). Missing computation → add it to `db/`.
- Money is integer Rial on the wire, in requests and responses; the display currency never reaches the API.
- Schemas (`api/schemas/`): field names match `db/` dict keys; request models `<Thing>Create`/`<Thing>Update` with `extra="forbid"`; money fields typed `Money` (strict int Rial, so float/string/bool → 422).
- Boolean-ish fields stay int 0/1 in responses. Intentional; don't convert to bool.
- Writes return the resource re-fetched via the GET getter. Create 201, update/action 200. DELETE of a recipe/kit item returns 200 with the updated recipe/kit.
- Partial updates (PATCH): `model_dump(exclude_unset=True)`; omitted = unchanged, explicit `null` = clear.
- `POST /orders`:
  - `packaging_kit_id` and `payment_method_id`: `"default"`/omitted = channel default, `null` = none, int = that one (strict int).
  - `shipping_charge`, `postage_cost`, `transaction_fee`: `null`/omitted = default/computed; `0` is a real override.
  - `paid_date` only for PAID/COMPLETED. Also on `POST /orders/{id}/status`; moved via `PATCH /orders/{id}/paid-date`.
- `POST /settlements`: `order_ids` for IMMEDIATE/DAYS_AFTER; `jalali_year` + `jalali_month` for DAY_OF_NEXT_MONTH (`order_ids` there is a 422). `difference` comes from `db/`.
- `PUT /settings/{key}`: only `VALID_SETTING_KEYS`, enforced in `db.settings.set_setting`.
- Tests: `with TestClient(app)` runs `init_db` on `$REBEL_DB`; the autouse fixture in `tests/conftest.py` points it at a temp file. Keep it.
