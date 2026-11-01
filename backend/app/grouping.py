"""Pure wash-grouping logic: which garments can be washed together.

Rules (spec §5):
  1. Same colour group.
  2. Compatible care class: normal + synthetic -> "standard"; delicate,
     wool and hand are each their own class.
  3. With split_hot, garments tolerating >= 60° form their own band.
A group washes at its lowest max temperature and lowest max spin.
"""

from dataclasses import dataclass, field

HOT_LIMIT = 60
COLOR_ORDER = ["white", "light", "dark", "colored"]
COLOR_LABELS = {"white": "vitt", "light": "ljust", "dark": "mörkt", "colored": "kulört"}
CLASS_LABELS = {"delicate": "Fintvätt", "wool": "Ull", "hand": "Handtvätt"}


@dataclass(frozen=True)
class Item:
    id: int
    person_id: int
    max_temp: int
    color: str
    max_spin: int
    care: str
    tumble_dry: bool


@dataclass(frozen=True)
class Prog:
    id: int
    name: str
    temp: int
    care: str


@dataclass
class Group:
    key: str
    color: str
    care: str
    temp: int
    spin: int
    item_ids: list[int]
    program_id: int | None
    no_dry_ids: list[int] = field(default_factory=list)


@dataclass
class Selection:
    group: Group | None
    compatible_ids: list[int]
    conflicts: list[str]


# How gentle a program/garment care type is. A program may be used when it is at
# least as gentle as the gentlest requirement among the garments.
GENTLENESS = {"normal": 0, "synthetic": 1, "delicate": 2, "wool": 3, "hand": 3}


def program_allowed(garment_care: str, program_care: str) -> bool:
    return GENTLENESS[program_care] >= GENTLENESS[garment_care]


def care_class(care: str) -> str:
    return "standard" if care in ("normal", "synthetic") else care


def _band(item: Item, split_hot: bool) -> str:
    return "hot" if split_hot and item.max_temp >= HOT_LIMIT else "std"


def _key(item: Item, split_hot: bool) -> str:
    return f"{item.color}-{care_class(item.care)}-{_band(item, split_hot)}"


def suggest_program(care: str, temp: int, programs: list[Prog]) -> int | None:
    best: Prog | None = None
    for p in programs:
        if p.care == care and p.temp <= temp and (best is None or p.temp > best.temp):
            best = p
    return best.id if best else None


def _make_group(key: str, items: list[Item], programs: list[Prog]) -> Group:
    cls = care_class(items[0].care)
    if cls == "standard":
        care = "synthetic" if any(i.care == "synthetic" for i in items) else "normal"
    else:
        care = cls
    temp = min(i.max_temp for i in items)
    return Group(
        key=key,
        color=items[0].color,
        care=care,
        temp=temp,
        spin=min(i.max_spin for i in items),
        item_ids=sorted(i.id for i in items),
        program_id=suggest_program(care, temp, programs),
        no_dry_ids=sorted(i.id for i in items if not i.tumble_dry),
    )


def group_items(items: list[Item], programs: list[Prog], split_hot: bool = True) -> list[Group]:
    buckets: dict[str, list[Item]] = {}
    for it in items:
        buckets.setdefault(_key(it, split_hot), []).append(it)
    groups = [_make_group(k, v, programs) for k, v in buckets.items()]
    groups.sort(key=lambda g: (-len(g.item_ids), g.key))
    return groups


def _conflicts(selected: list[Item], split_hot: bool) -> list[str]:
    out: list[str] = []
    colors = sorted({i.color for i in selected}, key=COLOR_ORDER.index)
    if len(colors) > 1:
        out.append("Olika färggrupper: " + " + ".join(COLOR_LABELS[c] for c in colors))
    classes = {care_class(i.care) for i in selected}
    if len(classes) > 1:
        for cls in sorted(classes - {"standard"}):
            out.append(f"{CLASS_LABELS[cls]} måste tvättas för sig")
    if len({_band(i, split_hot) for i in selected}) > 1:
        out.append("60° och varmare tvättas för sig")
    return out


def check_selection(
    selected: list[Item], basket: list[Item], programs: list[Prog], split_hot: bool = True
) -> Selection:
    if not selected:
        return Selection(group=None, compatible_ids=[], conflicts=[])
    conflicts = _conflicts(selected, split_hot)
    if conflicts:
        return Selection(group=None, compatible_ids=[], conflicts=conflicts)
    key = _key(selected[0], split_hot)
    chosen = {i.id for i in selected}
    compatible = sorted(i.id for i in basket if i.id not in chosen and _key(i, split_hot) == key)
    return Selection(group=_make_group(key, selected, programs), compatible_ids=compatible, conflicts=[])
