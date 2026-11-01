"""Read schema.org Recipe data (JSON-LD) out of a web page (spec §7). Pure except import_url."""

import html as htmllib
import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from app.kitchen import fetch

LD_RE = re.compile(r"<script[^>]*type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
ISO_RE = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$")


class NoRecipe(Exception):
    pass


@dataclass
class ImportedRecipe:
    title: str
    servings: int | None
    minutes: int | None
    ingredients: list[str]
    steps: list[str]
    image_url: str | None
    source_url: str


def clean_text(s) -> str:
    if not isinstance(s, str):
        return ""
    s = htmllib.unescape(TAG_RE.sub(" ", htmllib.unescape(s)))
    return " ".join(s.split())


def parse_iso_duration(s) -> int | None:
    if not isinstance(s, str):
        return None
    m = ISO_RE.match(s.strip())
    if not m:
        return None
    d, h, mi, _ = (int(float(x)) if x else 0 for x in m.groups())
    total = d * 1440 + h * 60 + mi
    return total or None


def _types(obj) -> list[str]:
    t = obj.get("@type")
    return t if isinstance(t, list) else [t]


def _find_recipe(node):
    if isinstance(node, list):
        for x in node:
            if (r := _find_recipe(x)) is not None:
                return r
    elif isinstance(node, dict):
        if "Recipe" in _types(node):
            return node
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in node and (r := _find_recipe(node[key])) is not None:
                return r
    return None


def _servings(y) -> int | None:
    for v in y if isinstance(y, list) else [y]:
        if isinstance(v, (int, float)) and v > 0:
            return int(v)
        if isinstance(v, str) and (m := re.search(r"\d+", v)):
            return int(m.group()) or None
    return None


def _steps(node) -> list[str]:
    if isinstance(node, str):
        return [clean_text(line) for line in node.splitlines() if clean_text(line)]
    out: list[str] = []
    if isinstance(node, list):
        for x in node:
            out += _steps(x)
    elif isinstance(node, dict):
        if "HowToSection" in _types(node) or "itemListElement" in node:
            out += _steps(node.get("itemListElement", []))
        else:
            t = clean_text(node.get("text") or node.get("name"))
            if t:
                out.append(t)
    return out


def _image(img, base: str) -> str | None:
    if isinstance(img, list):
        img = img[0] if img else None
    if isinstance(img, dict):
        img = img.get("url") or img.get("contentUrl")
    return urljoin(base, img) if isinstance(img, str) and img.strip() else None


def parse_recipe_html(html: str, url: str) -> ImportedRecipe | None:
    for block in LD_RE.findall(html or ""):
        try:
            data = json.loads(block.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        r = _find_recipe(data)
        if r is None:
            continue
        title = clean_text(r.get("name"))
        if not title:
            continue
        ingredients = [clean_text(x) for x in (r.get("recipeIngredient") or r.get("ingredients") or []) if clean_text(x)]
        minutes = parse_iso_duration(r.get("totalTime"))
        if minutes is None:
            parts = [parse_iso_duration(r.get(k)) for k in ("prepTime", "cookTime")]
            minutes = sum(p for p in parts if p) or None
        return ImportedRecipe(
            title=title[:120],
            servings=_servings(r.get("recipeYield")),
            minutes=minutes,
            ingredients=ingredients[:80],
            steps=_steps(r.get("recipeInstructions"))[:60],
            image_url=_image(r.get("image"), url),
            source_url=url,
        )
    return None


def import_url(url: str) -> ImportedRecipe:
    html = fetch.get(url).decode("utf-8", "replace")
    r = parse_recipe_html(html, url)
    if r is None:
        raise NoRecipe()
    return r
