from typing import Literal

from pydantic import BaseModel, ConfigDict

CategoryKind = Literal["PRODUCT", "MATERIAL"]


class CategoryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    kind: str
    name: str
    parent_id: int | None
    parent_name: str | None
    is_active: int
    created_at: str
    updated_at: str | None


class CategoryTreeOut(CategoryOut):
    children: list[CategoryOut]


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: CategoryKind
    name: str
    parent_id: int | None = None


class CategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    is_active: bool | None = None


class CategoryAssign(BaseModel):
    """Body of PATCH /products/{id}/category and /materials/{id}/category."""

    model_config = ConfigDict(extra="forbid")

    category_id: int
