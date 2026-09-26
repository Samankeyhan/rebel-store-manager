from pydantic import BaseModel, ConfigDict


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
