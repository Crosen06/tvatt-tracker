"""Pydantic models and allowed tag values (spec §4)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


# ---------- kitchen ----------

Category = Literal["Kyl", "Frys", "Skafferi", "Frukt & grönt", "Bröd", "Kryddor", "Dryck", "Hushåll"]
Status = Literal["in_stock", "low", "out"]


def _clean_name(v: str | None) -> str | None:
    if v is None:
        return v
    v = " ".join(v.split())
    if not v:
        raise ValueError("blank")
    return v


def _clean_words(v: list[str]) -> list[str]:
    out = []
    for w in v:
        w = " ".join(w.split()).lower()
        if w and w not in out:
            out.append(w)
    return out[:20]


class ItemIn(Strict):
    name: str = Field(max_length=40)
    category: Category
    staple: bool = False
    counted: bool = False
    match_words: list[str] = Field(default_factory=list)
    status: Status = "out"
    count: int | None = Field(default=None, ge=0, le=999)

    _n = field_validator("name")(lambda cls, v: _clean_name(v))
    _w = field_validator("match_words")(lambda cls, v: _clean_words(v))


class ItemPatch(Strict):
    name: str | None = Field(default=None, max_length=40)
    category: Category | None = None
    staple: bool | None = None
    counted: bool | None = None
    match_words: list[str] | None = None
    status: Status | None = None
    count: int | None = Field(default=None, ge=0, le=999)
    count_delta: int | None = Field(default=None, ge=-99, le=99)  # relative, so quick taps don't overwrite each other

    _n = field_validator("name")(lambda cls, v: _clean_name(v))
    _w = field_validator("match_words")(lambda cls, v: None if v is None else _clean_words(v))

    @model_validator(mode="after")
    def _count_or_delta(self):
        if self.count is not None and self.count_delta is not None:
            raise ValueError("count or count_delta")
        return self


class ShoppingIn(Strict):
    item_id: int | None = None
    text: str | None = Field(default=None, max_length=60)
    note: str | None = Field(default=None, max_length=60)

    _t = field_validator("text")(lambda cls, v: _clean_name(v))

    @model_validator(mode="after")
    def _one_of(self):
        if (self.item_id is None) == (self.text is None):
            raise ValueError("item_id or text")
        return self


class UnpackIn(Strict):
    entry_ids: list[int] = Field(max_length=500)


MAX_SERVINGS = 200
MAX_MINUTES = 7 * 24 * 60  # a week: sourdough and long marinades are real recipes


def _opt_int(v):
    if isinstance(v, str):
        v = v.strip()
        if v == "":
            return None
        if not v.isdigit():
            raise ValueError("not a number")
        return int(v)
    return v


class RecipeIn(Strict):
    title: str = Field(max_length=120)
    servings: int | None = Field(default=None, ge=1, le=MAX_SERVINGS)
    minutes: int | None = Field(default=None, ge=1, le=MAX_MINUTES)
    ingredients: str = Field(default="", max_length=8000)
    steps: str = Field(default="", max_length=20000)

    _t = field_validator("title")(lambda cls, v: _clean_name(v))
    _n = field_validator("servings", "minutes", mode="before")(lambda cls, v: _opt_int(v))


class RecipePatch(Strict):
    title: str | None = Field(default=None, max_length=120)
    servings: int | None = Field(default=None, ge=1, le=MAX_SERVINGS)
    minutes: int | None = Field(default=None, ge=1, le=MAX_MINUTES)
    ingredients: str | None = Field(default=None, max_length=8000)
    steps: str | None = Field(default=None, max_length=20000)

    _t = field_validator("title")(lambda cls, v: _clean_name(v))
    _n = field_validator("servings", "minutes", mode="before")(lambda cls, v: _opt_int(v))


class LinkIn(Strict):
    item_id: int | None = None
    ignored: bool | None = None

    @model_validator(mode="after")
    def _one_of(self):
        if (self.item_id is None) == (self.ignored is None):
            raise ValueError("item_id or ignored")
        return self


class CookedUpdate(Strict):
    item_id: int
    status: Status


class CookedIn(Strict):
    updates: list[CookedUpdate] = Field(default_factory=list, max_length=80)


class ImportIn(Strict):
    url: str = Field(min_length=8, max_length=2000, pattern=r"^https?://\S+$")


class NewItemIn(Strict):
    name: str = Field(max_length=40)
    category: Category

    _n = field_validator("name")(lambda cls, v: _clean_name(v))


class BarcodeIn(Strict):
    code: str = Field(pattern=r"^\d{8}$|^\d{12,13}$")
    item_id: int | None = None
    new_item: NewItemIn | None = None
    product_name: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _one_of(self):
        if (self.item_id is None) == (self.new_item is None):
            raise ValueError("item_id or new_item")
        return self


class VisionCaptureIn(Strict):
    item_id: int


class VisionConfirmIn(Strict):
    token: str = Field(min_length=1, max_length=64)
    item_id: int
