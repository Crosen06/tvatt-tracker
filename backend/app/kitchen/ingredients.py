"""Parse recipe ingredient lines and match them to pantry items (spec §5). Pure functions."""

import re
from dataclasses import dataclass

UNITS = (
    "g kg hg mg l dl cl ml msk tsk krm st förp förpackning förpackningar paket pkt burk burkar "
    "flaska flaskor klyfta klyftor skiva skivor knippe knippen kruka krukor påse påsar nypa nypor "
    "port portion portioner bit bitar"
).split()
ENDINGS = ("", "ar", "er", "or", "n", "en", "et", "na", "arna", "erna", "orna")
COMPOUND_MIN = 4

OPTIONAL_RE = re.compile(r"(efter smak|till servering|till garnering|valfri(?:tt)?|gärna|eventuellt|\bev\.)")
AMOUNT_RE = re.compile(
    r"^(?:ca\.?|cirka|ungefär|\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?|\d+/\d+|[½¼¾⅓⅔⅛])(?:\s+|$)"
)
UNIT_RE = re.compile(r"^(?:" + "|".join(sorted(UNITS, key=len, reverse=True)) + r")\.?(?:\s+|$)")
PAREN_RE = re.compile(r"\([^)]*\)")
CLEAN_RE = re.compile(r"[^\w\s-]", re.UNICODE)


@dataclass
class ParsedLine:
    text: str
    name: str
    optional: bool


@dataclass
class ItemRef:
    id: int
    name: str
    match_words: list[str]


def normalize(s: str) -> str:
    s = CLEAN_RE.sub(" ", s.lower().replace("_", " "))
    return " ".join(s.split())


def parse_line(line: str) -> ParsedLine | None:
    text = " ".join((line or "").split())
    if not text or text.endswith(":") or not re.search(r"[^\W\d_]", text):
        return None
    s = PAREN_RE.sub(" ", text.lower())
    optional = bool(OPTIONAL_RE.search(s))
    s = re.split(r",(?!\d)", s)[0]  # "1,5 kg" is a decimal, "lök, hackad" is a remark
    s = OPTIONAL_RE.sub(" ", s)
    s = " ".join(s.split())
    # Fold "1 1/2", "2-3", "ca 1/2" etc. by stripping leading amounts until none is left.
    while (m := AMOUNT_RE.match(s)) and m.end() > 0:
        s = s[m.end():]
    s = UNIT_RE.sub("", s, count=1)
    return ParsedLine(text=text, name=normalize(s), optional=optional)


def _word_hit(word: str, name: str) -> bool:
    if word.startswith(name) and word[len(name):] in ENDINGS:
        return True
    return len(name) >= COMPOUND_MIN and len(word) > len(name) and word.endswith(name)


def match(name: str, items: list[ItemRef], mapping: dict[str, int | None]) -> tuple[int | None, bool]:
    """Return (item_id, ignored). ignored is True when the mapping says "no item, don't count it"."""
    n = normalize(name)
    if not n:
        return None, False
    if n in mapping:
        return mapping[n], mapping[n] is None
    names = [(normalize(w), it.id) for it in items for w in [it.name, *it.match_words] if normalize(w)]
    for w, iid in names:
        if w == n:
            return iid, False
    words = n.split()
    padded = f" {n} "
    best: tuple[int, int] | None = None  # (length, item_id)
    for w, iid in names:
        hit = f" {w} " in padded if " " in w else any(_word_hit(x, w) for x in words)
        if hit and (best is None or len(w) > best[0]):
            best = (len(w), iid)
    return (best[1], False) if best else (None, False)
