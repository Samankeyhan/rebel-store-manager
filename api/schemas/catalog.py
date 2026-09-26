from pydantic import BaseModel, ConfigDict

from api.schemas.materials import MaterialOut
from api.schemas.packaging import KitDetailOut
from api.schemas.products import ProductOut
from api.schemas.settings import SettingsOut


class CatalogOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    products: list[ProductOut]
    materials: list[MaterialOut]
    kits: list[KitDetailOut]
    settings: SettingsOut
    postage_estimate: int
