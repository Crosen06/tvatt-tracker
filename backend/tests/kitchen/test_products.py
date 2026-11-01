import json

import pytest

from app.kitchen import fetch, products
from app.kitchen.products import Product, guess_category, parse_off, valid_gtin


@pytest.mark.parametrize("code", ["4006381333931", "96385074", "036000291452"])
def test_valid_gtin(code):
    assert valid_gtin(code)
    bad = code[:-1] + str((int(code[-1]) + 1) % 10)
    assert not valid_gtin(bad)


@pytest.mark.parametrize("code", ["", "abc", "12345678901", "40063813339a", "0000000000000x", "1" * 14])
def test_invalid_gtin_shapes(code):
    assert not valid_gtin(code)


def test_parse_off_names():
    p = parse_off({"status": 1, "product": {
        "product_name_sv": "Mellanmjölk 1,5%", "product_name": "Milk", "brands": "Arla Ko,Arla",
        "quantity": "1 l", "categories_tags": ["en:dairies", "en:milks"]}})
    assert p == Product(name="Arla Ko Mellanmjölk 1,5% 1 l", brand="Arla Ko", quantity="1 l", category="Kyl", short_name="Mellanmjölk 1,5%")
    p = parse_off({"status": 1, "product": {"product_name": "Pasta Penne", "brands": "Barilla", "quantity": ""}})
    assert p.name == "Barilla Pasta Penne" and p.category == "Skafferi"
    p = parse_off({"status": 1, "product": {"product_name": "Arla Mjölk", "brands": "Arla"}})
    assert p.name == "Arla Mjölk"  # brand already in the name


def test_parse_off_not_found():
    assert parse_off({"status": 0, "status_verbose": "product not found"}) is None
    assert parse_off({"status": 1, "product": {"product_name": "  "}}) is None
    assert parse_off({}) is None
    assert parse_off("nonsense") is None


@pytest.mark.parametrize("tags,cat", [
    (["en:dairies"], "Kyl"), (["en:cheeses"], "Kyl"), (["en:yogurts"], "Kyl"), (["en:frozen-foods"], "Frys"),
    (["en:breads"], "Bröd"), (["en:beverages"], "Dryck"), (["en:vegetables"], "Frukt & grönt"),
    (["en:fruits"], "Frukt & grönt"), (["en:condiments"], "Kryddor"), (["en:spices"], "Kryddor"), ([], "Skafferi"),
    (["en:frozen-foods", "en:vegetables"], "Frys"),
])
def test_guess_category(tags, cat):
    assert guess_category(tags) == cat


def test_lookup_uses_fetch(monkeypatch):
    seen = {}

    def get(url, **kw):
        seen["url"], seen["timeout"] = url, kw.get("timeout")
        return json.dumps({"status": 1, "product": {"product_name": "Krossade tomater", "brands": "Mutti"}}).encode()

    monkeypatch.setattr(fetch, "get", get)
    assert products.lookup("4006381333931").name == "Mutti Krossade tomater"
    assert seen["url"].startswith("https://world.openfoodfacts.org/api/v2/product/4006381333931.json?fields=")
    assert seen["timeout"] == 5
    monkeypatch.setattr(fetch, "get", lambda url, **kw: b"not json")
    with pytest.raises(fetch.FetchError):
        products.lookup("4006381333931")
