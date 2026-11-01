"""Search ica.se for recipes and preview them (spec §7).

The search page's structure can't be inspected from the development environment, so three
strategies are tried in order: JSON-LD ItemList, embedded JSON (e.g. __NEXT_DATA__), plain links.
"""

import html as htmllib
import json
import re
import threading
import time
from collections import OrderedDict
from urllib.parse import quote_plus, urljoin

from app.kitchen import fetch, recipe_import
from app.kitchen.recipe_import import LD_RE, clean_text

BASE = "https://www.ica.se"
MAX_RESULTS = 20
RECIPE_PATH = re.compile(r"^/recept/[a-z0-9åäö-]+-\d+/?$")
JSON_SCRIPT_RE = re.compile(r"<script[^>]*type\s*=\s*[\"']application/json[\"'][^>]*>(.*?)</script>", re.S | re.I)
LINK_RE = re.compile(r"<a\b[^>]*href\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.S | re.I)
IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
ATTR_RE = r"\b{}\s*=\s*[\"']([^\"']*)[\"']"
TITLE_KEYS = ("title", "name", "heading", "headline")
URL_KEYS = ("url", "absoluteUrl", "href", "link", "path", "slug")
IMAGE_KEYS = ("image", "imageUrl", "imageURL", "img", "thumbnail", "picture")


def search_url(q: str) -> str:
    return f"{BASE}/recept/?q={quote_plus(q.strip())}"


def _absolute(href: str) -> str | None:
    if not isinstance(href, str):
        return None
    url = urljoin(BASE + "/", htmllib.unescape(href.strip()))
    if not url.startswith(BASE + "/"):
        return None
    path = url[len(BASE):].split("?")[0].split("#")[0]
    if not RECIPE_PATH.match(path):
        return None
    return BASE + (path if path.endswith("/") else path + "/")


def is_recipe_url(url: str) -> bool:
    return isinstance(url, str) and url.startswith(BASE + "/") and _absolute(url) is not None


def _image_value(v) -> str | None:
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, dict):
        v = v.get("url") or v.get("src") or v.get("href")
    return v if isinstance(v, str) and v.startswith("http") else None


def _url_value(v) -> str | None:
    if isinstance(v, dict):
        v = v.get("href") or v.get("url")
    return _absolute(v)


def _add(out: list, seen: set, url, title, image) -> None:
    if url and url not in seen and len(out) < MAX_RESULTS:
        seen.add(url)
        out.append({"url": url, "title": clean_text(title) or "Recept", "image": image})


def _from_itemlist(html: str) -> list[dict]:
    out, seen = [], set()
    for block in LD_RE.findall(html):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for node in data if isinstance(data, list) else [data]:
            if not isinstance(node, dict) or "ItemList" not in str(node.get("@type")):
                continue
            for el in node.get("itemListElement") or []:
                if not isinstance(el, dict):
                    continue
                item = el.get("item") if isinstance(el.get("item"), dict) else el
                _add(out, seen, _absolute(item.get("url") or el.get("url")), item.get("name") or el.get("name"), _image_value(item.get("image")))
    return out


def _walk(node, out, seen) -> None:
    if len(out) >= MAX_RESULTS:
        return
    if isinstance(node, dict):
        url = next((u for k in URL_KEYS if (u := _url_value(node.get(k)))), None)
        title = next((node[k] for k in TITLE_KEYS if isinstance(node.get(k), str)), None)
        if url and title:
            image = next((i for k in IMAGE_KEYS if (i := _image_value(node.get(k)))), None)
            _add(out, seen, url, title, image)
            return
        for v in node.values():
            _walk(v, out, seen)
    elif isinstance(node, list):
        for v in node:
            _walk(v, out, seen)


def _from_json(html: str) -> list[dict]:
    out, seen = [], set()
    for block in JSON_SCRIPT_RE.findall(html):
        try:
            _walk(json.loads(block.strip()), out, seen)
        except ValueError:
            continue
    return out


def _from_links(html: str) -> list[dict]:
    out, seen = [], set()
    for href, inner in LINK_RE.findall(html):
        url = _absolute(href)
        if not url:
            continue
        img = IMG_RE.search(inner)
        image = title = None
        if img:
            src = re.search(ATTR_RE.format("src"), img.group())
            alt = re.search(ATTR_RE.format("alt"), img.group())
            image = _image_value(htmllib.unescape(src.group(1))) if src else None
            title = alt.group(1) if alt else None
        _add(out, seen, url, clean_text(inner) or title, image)
    return out


def parse_search(html: str) -> list[dict]:
    for strategy in (_from_itemlist, _from_json, _from_links):
        if results := strategy(html or ""):
            return results
    return []


def search(q: str) -> list[dict]:
    return parse_search(fetch.get(search_url(q)).decode("utf-8", "replace"))


class PreviewCache:
    """Small LRU cache of imported recipes so scrolling the result list doesn't refetch pages."""

    def __init__(self, maxsize: int = 50, ttl: float = 1800, clock=time.monotonic):
        self.maxsize, self.ttl, self.clock = maxsize, ttl, clock
        self._data: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._data)

    def get(self, url: str) -> recipe_import.ImportedRecipe:
        now = self.clock()
        with self._lock:
            hit = self._data.get(url)
            if hit and now - hit[0] < self.ttl:
                self._data.move_to_end(url)
                return hit[1]
        recipe = recipe_import.import_url(url)
        with self._lock:
            self._data[url] = (now, recipe)
            self._data.move_to_end(url)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)
        return recipe


preview_cache = PreviewCache()
