"""Schemas for spare-parts / commercial lookups (Business Agent)."""

from pydantic import BaseModel, Field

from .common import ScopedContext


class ListSparePartsInput(ScopedContext):
    query: str = Field(
        ...,
        min_length=1,
        description='Part name, code, or unit (e.g. capping head, gripper).',
    )
    limit: int = Field(default=10, ge=1, le=50)


class SparePartItem(BaseModel):
    part_number: str
    name: str
    unit_code: str | None = None
    description: str | None = None
    availability: str | None = None


class ListSparePartsOutput(BaseModel):
    stub: bool = True
    query: str
    parts: list[SparePartItem]
    note: str = 'list_spare_parts is a stub until commerce catalog is connected.'
