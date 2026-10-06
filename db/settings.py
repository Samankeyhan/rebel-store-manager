import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from db.connection import transaction
from db.constants import VALID_CHANNELS
from db.currency import DISPLAY_CURRENCIES
from db.errors import NotFoundError, ValidationError
from db.payment_methods import get_payment_method

_UNSET = object()

VALID_SETTING_KEYS = (
    "default_shipping_charge",
    "postage_estimate_window",
    "default_postage_estimate",
    "timezone",
    "display_currency",
)

_NON_NEGATIVE_INT_KEYS = {"default_shipping_charge", "default_postage_estimate"}
_POSITIVE_INT_KEYS = {"postage_estimate_window"}


def _validate_setting_value(key: str, value: str) -> None:
    if key in _NON_NEGATIVE_INT_KEYS or key in _POSITIVE_INT_KEYS:
        try:
            amount = int(value)
        except (TypeError, ValueError):
            raise ValidationError(
                f"Setting '{key}' must be an integer, got {value!r}", field="value"
            ) from None
        if key in _NON_NEGATIVE_INT_KEYS and amount < 0:
            raise ValidationError(
                f"Setting '{key}' must be >= 0, got {amount}", field="value"
            )
        if key in _POSITIVE_INT_KEYS and amount <= 0:
            raise ValidationError(
                f"Setting '{key}' must be > 0, got {amount}", field="value"
            )
    elif key == "timezone":
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValidationError(
                f"Setting 'timezone' must be a valid IANA timezone name, got {value!r}",
                field="value",
            ) from None
    elif key == "display_currency":
        # Exact and case-sensitive: the frontend compares the stored string.
        if value not in DISPLAY_CURRENCIES:
            valid = ", ".join(DISPLAY_CURRENCIES)
            raise ValidationError(
                f"Setting 'display_currency' must be one of: {valid}, got {value!r}",
                field="value",
            )


def get_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    return row["value"]


def set_setting(conn: sqlite3.Connection, key: str, value) -> None:
    # An unknown key (e.g. a typo) would otherwise be saved silently while the
    # real setting never changes.
    if key not in VALID_SETTING_KEYS:
        valid = ", ".join(VALID_SETTING_KEYS)
        raise ValidationError(
            f"Unknown setting '{key}'. Must be one of: {valid}", field="key"
        )
    value_str = str(value)
    _validate_setting_value(key, value_str)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value_str),
        )


def _validate_channel(channel: str) -> None:
    if channel not in VALID_CHANNELS:
        valid = ", ".join(VALID_CHANNELS)
        raise ValidationError(
            f"Invalid channel '{channel}'. Must be one of: {valid}", field="channel"
        )


def get_channel_settings(conn: sqlite3.Connection, channel: str) -> dict:
    _validate_channel(channel)
    row = conn.execute(
        "SELECT * FROM channel_settings WHERE channel = ?", (channel,)
    ).fetchone()
    if row is None:
        raise NotFoundError(f"No channel_settings row for channel '{channel}'")
    return dict(row)


def update_channel_settings(
    conn: sqlite3.Connection,
    channel: str,
    applies_shipping_charge: int | None = None,
    applies_postage: int | None = None,
    default_packaging_kit_id=_UNSET,
    default_payment_method_id=_UNSET,
) -> None:
    """Omitted fields are unchanged; default_packaging_kit_id and
    default_payment_method_id may be set to None to clear them. A new default
    payment method must be active; deactivating a method that is already a
    channel's default is not blocked (record_order then refuses it)."""
    _validate_channel(channel)
    get_channel_settings(conn, channel)  # raises NotFoundError if missing

    fields: dict = {}

    if applies_shipping_charge is not None:
        if applies_shipping_charge not in (0, 1):
            raise ValidationError(
                "applies_shipping_charge must be 0 or 1", field="applies_shipping_charge"
            )
        fields["applies_shipping_charge"] = applies_shipping_charge

    if applies_postage is not None:
        if applies_postage not in (0, 1):
            raise ValidationError(
                "applies_postage must be 0 or 1", field="applies_postage"
            )
        fields["applies_postage"] = applies_postage

    if default_packaging_kit_id is not _UNSET:
        if default_packaging_kit_id is not None:
            kit = conn.execute(
                "SELECT id FROM packaging_kits WHERE id = ? AND is_active = 1",
                (default_packaging_kit_id,),
            ).fetchone()
            if kit is None:
                raise NotFoundError(
                    f"Packaging kit with id {default_packaging_kit_id} does not "
                    f"exist or is not active"
                )
        fields["default_packaging_kit_id"] = default_packaging_kit_id

    if default_payment_method_id is not _UNSET:
        if default_payment_method_id is not None:
            # raises NotFoundError if missing
            method = get_payment_method(conn, default_payment_method_id)
            if not method["is_active"]:
                raise ValidationError(
                    f"Payment method '{method['name']}' is not active and cannot be "
                    f"a channel's default payment method",
                    field="default_payment_method_id",
                )
        fields["default_payment_method_id"] = default_payment_method_id

    if not fields:
        return

    set_clause = ", ".join(f"{name} = ?" for name in fields)
    params = list(fields.values()) + [channel]
    with transaction(conn):
        conn.execute(
            f"UPDATE channel_settings SET {set_clause} WHERE channel = ?", params
        )
