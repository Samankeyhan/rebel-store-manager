from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr


class ChannelSettingsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    applies_shipping_charge: int
    applies_postage: int
    default_packaging_kit_id: int | None


class SettingsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_shipping_charge: int
    postage_estimate_window: int
    default_postage_estimate: int
    timezone: str
    channels: dict[str, ChannelSettingsOut]


class SettingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: StrictInt | StrictStr


class ChannelSettingsUpdate(BaseModel):
    """Only the fields present in the body change. An explicit null
    default_packaging_kit_id clears the channel's default kit."""

    model_config = ConfigDict(extra="forbid")

    applies_shipping_charge: int | None = None
    applies_postage: int | None = None
    default_packaging_kit_id: int | None = None
