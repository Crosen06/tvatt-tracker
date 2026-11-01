"""Pydantic models and allowed tag values (spec §4)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Temp = Literal[20, 30, 40, 50, 60, 90]
Color = Literal["white", "light", "dark", "colored"]
Spin = Literal[0, 400, 600, 800, 1000, 1200, 1400]
Care = Literal["normal", "synthetic", "delicate", "wool", "hand"]
HexColor = str


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PersonIn(Strict):
    name: str = Field(min_length=1, max_length=40)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class PersonPatch(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class ProgramIn(Strict):
    name: str = Field(min_length=1, max_length=40)
    duration_min: int = Field(ge=1, le=600)
    temp: Temp
    care: Care


class ProgramPatch(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    duration_min: int | None = Field(default=None, ge=1, le=600)
    temp: Temp | None = None
    care: Care | None = None


class SettingsPatch(Strict):
    split_hot: bool | None = None
    auto_list: bool | None = None


class GarmentIn(Strict):
    person_id: int
    name: str = Field(min_length=1, max_length=60)
    max_temp: Temp
    color: Color
    max_spin: Spin
    care: Care
    tumble_dry: bool


class GarmentPatch(Strict):
    person_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=60)
    max_temp: Temp | None = None
    color: Color | None = None
    max_spin: Spin | None = None
    care: Care | None = None
    tumble_dry: bool | None = None


class BasketIn(Strict):
    in_basket: bool


class CheckIn(Strict):
    garment_ids: list[int]


class WashIn(Strict):
    program_id: int
    garment_ids: list[int] = Field(min_length=1)
    temp: Temp | None = None  # informational; the wash runs at the program's temperature
    spin: Spin | None = None  # defaults to the lowest max spin of the garments
