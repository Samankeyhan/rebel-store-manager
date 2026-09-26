import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.settings import ChannelSettingsOut, SettingsOut
from db.constants import VALID_CHANNELS
from db.settings import get_channel_settings, get_setting

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
