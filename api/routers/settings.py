import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.settings import (
    ChannelSettingsOut,
    ChannelSettingsUpdate,
    SettingsOut,
    SettingUpdate,
)
from db.constants import VALID_CHANNELS
from db.settings import (
    get_channel_settings,
    get_setting,
    set_setting,
    update_channel_settings,
)

router = APIRouter(tags=["settings"])


def build_settings(conn: sqlite3.Connection) -> SettingsOut:
    channels = {
        channel: ChannelSettingsOut.model_validate(get_channel_settings(conn, channel))
        for channel in VALID_CHANNELS
    }
    return SettingsOut(
        default_shipping_charge=int(get_setting(conn, "default_shipping_charge")),
        postage_estimate_window=int(get_setting(conn, "postage_estimate_window")),
        default_postage_estimate=int(get_setting(conn, "default_postage_estimate")),
        timezone=get_setting(conn, "timezone"),
        channels=channels,
    )


@router.get("/settings", response_model=SettingsOut)
def read_settings(conn: sqlite3.Connection = Depends(get_db)) -> SettingsOut:
    return build_settings(conn)


# Registered before /settings/{key}; different methods, but keeps the literal
# "channels" path unambiguous to readers.
@router.patch("/settings/channels/{channel}", response_model=ChannelSettingsOut)
def patch_channel_settings(
    channel: str,
    body: ChannelSettingsUpdate,
    conn: sqlite3.Connection = Depends(get_db),
) -> ChannelSettingsOut:
    """Only the fields present in the body change. An explicit null
    default_packaging_kit_id clears the channel's default kit; omitting it
    leaves it as is."""
    update_channel_settings(conn, channel, **body.model_dump(exclude_unset=True))
    return ChannelSettingsOut.model_validate(get_channel_settings(conn, channel))


@router.put("/settings/{key}", response_model=SettingsOut)
def put_setting(
    key: str, body: SettingUpdate, conn: sqlite3.Connection = Depends(get_db)
) -> SettingsOut:
    """Set one of: default_shipping_charge, postage_estimate_window,
    default_postage_estimate, timezone. Any other key is a 422 (field "key")."""
    set_setting(conn, key, body.value)
    return build_settings(conn)
