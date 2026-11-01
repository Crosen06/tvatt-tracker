import pytest

from app.kitchen.ingredients import ItemRef, match, normalize, parse_line


def names(lines):
    return [p.name if p else None for p in map(parse_line, lines)]


def test_parse_amounts_units():
    p = parse_line("2 dl vispgrädde (gärna laktosfri)")
    assert (p.name, p.optional, p.text) == ("vispgrädde", False, "2 dl vispgrädde (gärna laktosfri)")
    assert names([
        "1 gul lök, finhackad",
        "400 g krossade tomater",
        "2–3 klyftor vitlök",
        "ca 1/2 tsk salt",
        "1,5 kg potatis",
        "1 förp kokosmjölk (400 ml)",
        "3 msk olivolja",
        "2 st ägg",
    ]) == ["gul lök", "krossade tomater", "vitlök", "salt", "potatis", "kokosmjölk", "olivolja", "ägg"]


def test_parse_optional():
    assert parse_line("salt och peppar efter smak").optional is True
    assert parse_line("färsk koriander till servering").optional is True
    assert parse_line("ev. chiliflakes").optional is True
    assert parse_line("1 dl riven ost").optional is False


def test_parse_line_odd_inputs():
    assert parse_line("") is None
    assert parse_line("   ") is None
    assert parse_line("Till servering:") is None
    assert parse_line("Sås") is not None  # a one-word line is an ingredient, not a heading
    assert parse_line("1 1/2 dl mjölk").name == "mjölk"
    assert parse_line("Salt").name == "salt"
    assert parse_line("2 st ägg (ca 120 g)").name == "ägg"
    assert parse_line("½ kruka basilika").name == "basilika"
    assert parse_line("¾ dl  vatten").name == "vatten"
    assert parse_line("100 g").name == ""  # nothing left: kept, but never matches
    assert parse_line("12") is None  # no letters: not an ingredient (spec §5)


def test_normalize():
    assert normalize("  Crème  Fraîche ") == "crème fraîche"
    assert normalize("Kyckling-filé!") == "kyckling-filé"


ITEMS = [
    ItemRef(1, "Svartpeppar", ["peppar"]),
    ItemRef(2, "Tomat", []),
    ItemRef(3, "Krossade tomater", []),
    ItemRef(4, "Lök", ["gul lök"]),
    ItemRef(5, "Grädde", []),
    ItemRef(6, "Is", []),
    ItemRef(7, "Purjolök", []),
    ItemRef(8, "Ägg", []),
]


def m(name, mapping=None):
    return match(name, ITEMS, mapping or {})


def test_match_exact_and_synonym():
    assert m("peppar") == (1, False)
    assert m("svartpeppar") == (1, False)
    assert m("gul lök") == (4, False)


def test_match_inflection():
    assert m("tomater") == (2, False)
    assert m("lökar") == (4, False)
    assert m("äggen") == (8, False)


def test_match_compound():
    assert m("vispgrädde") == (5, False)
    assert m("rödlök") == (None, False)  # "lök" is shorter than 4 letters: no compound match (seed lists rödlök as a synonym)
    assert m("purjolök") == (7, False)  # exact beats compound


def test_match_phrase_longest_wins():
    assert m("krossade tomater") == (3, False)
    assert m("burk krossade tomater med basilika") == (3, False)


def test_match_mapping_first():
    assert m("tomater", {"tomater": 5}) == (5, False)
    assert m("vatten", {"vatten": None}) == (None, True)


def test_short_names_no_compound():
    assert m("ris") == (None, False)
    assert m("") == (None, False)
    assert m("basilika") == (None, False)
