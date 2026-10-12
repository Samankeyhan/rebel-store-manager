"""`ErrorBody.details` is typed per error code in OpenAPI (api/schemas/errors.py): every ErrorCode has a details
model, the raise sites in db/ agree with the models, and the discriminated union covers every code."""

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError as PydanticValidationError

from api.main import app
from api.schemas.errors import ERROR_BODIES, ERROR_DETAILS, ErrorEnvelope, NoDetails
from db.errors import ErrorCode

DB = Path(__file__).resolve().parent.parent / "db"
_ENVELOPE = TypeAdapter(ErrorEnvelope)


def test_every_error_code_has_a_details_model():
    """Adding an ErrorCode without choosing its details model (NoDetails if it carries none) fails here."""
    assert set(ERROR_DETAILS) == set(ErrorCode)


def _scan_raise_sites():
    """(file, line, code, literal details keys) for every `XError(..., code=ErrorCode.X, ...)` in db/."""
    sites = []
    for path in sorted(DB.glob("*.py")):
        if path.name == "errors.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", "").endswith("Error")):
                continue  # only the error constructors (not helpers that take a `code=` argument)
            keywords = {k.arg: k.value for k in node.keywords if k.arg}
            code = keywords.get("code")
            if not (isinstance(code, ast.Attribute) and isinstance(code.value, ast.Name) and code.value.id == "ErrorCode"):
                continue
            details = keywords.get("details")
            if details is None:
                keys = frozenset()
            elif isinstance(details, ast.Dict) and all(isinstance(k, ast.Constant) for k in details.keys):
                keys = frozenset(k.value for k in details.keys)
            else:
                continue  # details built elsewhere (a variable, exc.details): covered by the runtime tests
            sites.append((path.name, node.lineno, ErrorCode[code.attr], keys))
    return sites


SITES = _scan_raise_sites()


def test_the_scan_found_the_raise_sites():
    assert len(SITES) > 30
    assert {s[2] for s in SITES} >= {ErrorCode.AMOUNT_TOO_LARGE, ErrorCode.CATEGORY_IN_USE, ErrorCode.DATE_IN_FUTURE}


@pytest.mark.parametrize("file, line, code, keys", SITES, ids=[f"{s[0]}:{s[1]}" for s in SITES])
def test_a_raise_site_carries_exactly_the_keys_its_model_declares(file, line, code, keys):
    model = ERROR_DETAILS[code]
    declared = set(model.model_fields)
    required = {name for name, field in model.model_fields.items() if field.is_required()}
    assert keys <= declared, f"{file}:{line} {code}: details has keys the model lacks: {sorted(keys - declared)}"
    assert required <= keys, f"{file}:{line} {code}: details lacks required keys: {sorted(required - keys)}"


def test_the_openapi_union_is_discriminated_on_code_and_maps_every_code():
    schemas = app.openapi()["components"]["schemas"]
    union = schemas["ErrorEnvelope"]["properties"]["error"]
    assert union["discriminator"]["propertyName"] == "code"
    assert set(union["discriminator"]["mapping"]) == {c.value for c in ErrorCode}
    assert sorted(schemas["ErrorCode"]["enum"]) == sorted(c.value for c in ErrorCode)
    for body in ERROR_BODIES:
        assert body.__name__ in schemas


def test_a_details_model_rejects_a_key_it_does_not_declare():
    with pytest.raises(PydanticValidationError):
        _ENVELOPE.validate_python({"error": {
            "type": "ConflictError", "code": "NAME_DUPLICATE", "message": "x", "field": None,
            "details": {"entity": "product", "existing_id": 1, "surprise": 1}}})
    with pytest.raises(PydanticValidationError):
        _ENVELOPE.validate_python({"error": {
            "type": "NotFoundError", "code": "NOT_FOUND", "message": "x", "field": None, "details": {"a": 1}}})


# ---------------------------------------------------- real responses validate against the models


def _validate(response):
    body = response.json()
    _ENVELOPE.validate_python(body)
    return body["error"]


def test_real_errors_validate_against_the_typed_envelope(tmp_path, monkeypatch):
    from api.deps import get_db
    from db.connection import get_connection, init_db

    db_path = str(tmp_path / "typed.db")
    init_db(db_path)

    def override():
        conn = get_connection(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override
    try:
        client = TestClient(app)
        assert client.post("/suppliers", json={"name": "A"}).status_code == 201
        assert client.post("/expense-categories", json={"name": "E"}).status_code == 201
        errors = {
            "dup": _validate(client.post("/suppliers", json={"name": "A"})),
            "money": _validate(client.post("/expenses", json={"expense_category_id": 1, "amount": 2**64})),
            "quantity": _validate(client.post("/production", json={"product_id": 1, "quantity_produced": 0})),
            "missing": _validate(client.post("/suppliers", json={})),
            "not_found": _validate(client.get("/products/999")),
            "kit": _validate(client.get("/packaging/kits/999")),
        }
        assert errors["dup"]["code"] == "NAME_DUPLICATE" and errors["dup"]["details"]["existing_id"] == 1
        assert errors["money"]["code"] == "AMOUNT_TOO_LARGE" and errors["money"]["details"]["max"] == 2**53 - 1
        assert errors["quantity"]["code"] == "QUANTITY_OUT_OF_RANGE"
        assert errors["missing"]["details"]["errors"][0]["loc"] == ["body", "name"]
        assert errors["not_found"]["details"] == {}
        assert errors["kit"]["details"] == {"packaging_kit_id": 999}
    finally:
        app.dependency_overrides.clear()


def test_no_details_is_the_empty_model():
    assert NoDetails.model_fields == {}
