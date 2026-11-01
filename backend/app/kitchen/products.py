"""Barcodes: checksum validation and product lookup in Open Food Facts (spec §8)."""

import json
from dataclasses import dataclass

from app.kitchen import fetch

OFF_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json?fields=product_name,product_name_sv,brands,quantity,categories_tags"

# First matching tag wins; order matters (frozen vegetables are Frys, not Frukt & grönt).
CATEGORY_TAGS = [
    ("Frys", ("frozen",)),
    ("Kyl", ("dairies", "dairy", "cheeses", "yogurts", "milks", "butters", "creams", "meats", "poultry", "fishes", "eggs")),
    ("Bröd", ("breads", "crispbreads", "bakery")),
    ("Dryck", ("beverages", "drinks", "waters", "juices", "sodas", "coffees", "teas")),
    ("Frukt & grönt", ("vegetables", "fruits", "fresh-vegetables", "fresh-fruits")),
    ("Kryddor", ("condiments", "spices", "sauces", "herbs", "seasonings")),
]


@dataclass
class Product:
    name: str
    brand: str | None
    quantity: str | None
    category: str
    short_name: str = ""  # the product name alone, a good start for naming a new item


def valid_gtin(code: str) -> bool:
    """EAN-8, UPC-A (12) and EAN-13 checksum."""
    if not isinstance(code, str) or not code.isascii() or not code.isdigit() or len(code) not in (8, 12, 13):
        return False
    digits = [int(c) for c in code]
    body, check = digits[:-1], digits[-1]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def guess_category(tags) -> str:
    tags = [t.split(":", 1)[-1] for t in tags or [] if isinstance(t, str)]
    for category, words in CATEGORY_TAGS:
        if any(t == w or t.startswith(w) for t in tags for w in words):
            return category
    return "Skafferi"


def parse_off(data) -> Product | None:
    if not isinstance(data, dict) or data.get("status") != 1 or not isinstance(data.get("product"), dict):
        return None
    p = data["product"]
    name = " ".join(str(p.get("product_name_sv") or p.get("product_name") or "").split())
    if not name:
        return None
    brand = (str(p.get("brands") or "").split(",")[0].strip()) or None
    quantity = " ".join(str(p.get("quantity") or "").split()) or None
    full = name
    if brand and brand.lower() not in name.lower():
        full = f"{brand} {full}"
    if quantity and quantity.lower() not in name.lower():
        full = f"{full} {quantity}"
    return Product(name=full[:80], brand=brand, quantity=quantity, category=guess_category(p.get("categories_tags")), short_name=name[:40])


def lookup(code: str) -> Product | None:
    raw = fetch.get(OFF_URL.format(code=code), timeout=5, max_bytes=500_000, accept="application/json")
    try:
        data = json.loads(raw)
    except ValueError:
        raise fetch.FetchError("Open Food Facts svarade konstigt. Försök igen senare.")
    return parse_off(data)
