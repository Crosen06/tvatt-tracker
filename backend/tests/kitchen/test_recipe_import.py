from pathlib import Path

import pytest

from app.kitchen import fetch, recipe_import
from app.kitchen.recipe_import import parse_iso_duration, parse_recipe_html

FIX = Path(__file__).parent / "fixtures"


def page(name):
    return (FIX / name).read_text()


def test_import_variants():
    r = parse_recipe_html(page("ica_recipe.html"), "https://www.ica.se/recept/kramig-kycklinggryta-722668/")
    assert r.title == "Krämig kycklinggryta med curry"
    assert (r.servings, r.minutes) == (4, 45)
    assert r.image_url == "https://assets.example.se/kycklinggryta.jpg"
    assert r.ingredients[0] == "600 g kycklinglårfilé" and len(r.ingredients) == 7
    assert r.steps == ["Skär kycklingen i bitar.", "Fräs lök och vitlök & curry.", "Tillsätt kokosmjölk och grädde. Låt puttra 20 minuter."]
    assert r.source_url == "https://www.ica.se/recept/kramig-kycklinggryta-722668/"

    g = parse_recipe_html(page("graph_recipe.html"), "https://mat.example.se/recept/pasta")
    assert g.title == "Pasta & pesto"
    assert (g.servings, g.minutes) == (4, 90)
    assert g.image_url == "https://mat.example.se/bilder/pasta.jpg"
    assert g.steps == ["Koka pastan.", "Blanda med pesto.", "Servera."]
    assert g.ingredients == ["400 g pasta", "1 burk pesto", "Till servering:", "riven parmesan"]

    s = parse_recipe_html(page("sections_recipe.html"), "https://x.example.se/lasagne")
    assert (s.servings, s.minutes) == (6, 60)
    assert s.steps == ["Bryn färsen.", "Tillsätt tomaterna.", "Varva sås och plattor."]
    assert s.image_url == "https://img.example.se/lasagne.jpg"


def test_no_recipe_returns_none():
    assert parse_recipe_html(page("no_recipe.html"), "https://x.se/") is None
    assert parse_recipe_html("", "https://x.se/") is None
    assert parse_recipe_html("<html>" * 1000, "https://x.se/") is None


def test_iso_durations():
    assert parse_iso_duration("PT1H30M") == 90
    assert parse_iso_duration("PT45M") == 45
    assert parse_iso_duration("P0DT2H") == 120
    assert parse_iso_duration("PT0M") is None
    assert parse_iso_duration("ungefär en timme") is None
    assert parse_iso_duration(None) is None


def test_import_url_uses_fetch(monkeypatch):
    monkeypatch.setattr(fetch, "get", lambda url, **kw: page("ica_recipe.html").encode())
    r = recipe_import.import_url("https://www.ica.se/recept/x-1/")
    assert r.title.startswith("Krämig")
    monkeypatch.setattr(fetch, "get", lambda url, **kw: page("no_recipe.html").encode())
    with pytest.raises(recipe_import.NoRecipe):
        recipe_import.import_url("https://www.ica.se/recept/x-1/")
