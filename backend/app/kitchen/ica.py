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
LINK_RE = re.compile(r"(<a\b[^>]*>)(.*?)</a>", re.S | re.I)
IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
TITLE_KEYS = ("title", "name", "heading", "headline")
URL_KEYS = ("url", "absoluteUrl", "href", "link", "path", "slug")
PLACEHOLDER_RE = re.compile(r"(placeholder|blank|spacer|transparent|fallback|default)[^/]*$|\.svg$|\.gif$", re.I)
LAZY_SRC_ATTRS = ("data-src", "data-lazy-src", "data-original", "src")
IMAGE_KEYS = ("image", "imageUrl", "imageURL", "img", "thumbnail", "picture")


def search_url(q: str) -> str:
    return f"{BASE}/recept/?q={quote_plus(' '.join(q.lower().split()))}"


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
    if not isinstance(v, str) or not v.startswith("http"):
        return None
    # Lazy-loading pages put a generic placeholder in src until the real picture is scrolled in.
    return None if PLACEHOLDER_RE.search(v.split("?")[0]) else v


def _url_value(v) -> str | None:
    if isinstance(v, dict):
        v = v.get("href") or v.get("url")
    return _absolute(v)


def _add(out: list, seen: dict, url, title, image) -> None:
    """Add a hit, or fill in what an earlier hit for the same recipe lacked.

    Search pages often link each recipe twice (a picture-only link and a text link), so the
    first link alone may have neither a title nor an image. `title` is None when unknown; the
    UI then shows the title from the recipe page itself.
    """
    if not url:
        return
    title = clean_text(title) or None
    if url in seen:
        hit = seen[url]
        hit["title"] = hit["title"] or title
        hit["image"] = hit["image"] or image
    elif len(out) < MAX_RESULTS:
        seen[url] = hit = {"url": url, "title": title, "image": image}
        out.append(hit)


def _from_itemlist(html: str) -> list[dict]:
    out, seen = [], {}
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
    out, seen = [], {}
    for block in JSON_SCRIPT_RE.findall(html):
        try:
            _walk(json.loads(block.strip()), out, seen)
        except ValueError:
            continue
    return out


def _from_links(html: str) -> list[dict]:
    out, seen = [], {}
    for tag, inner in LINK_RE.findall(html):
        url = _absolute(_attr(tag, "href"))
        if not url:
            continue
        img = IMG_RE.search(inner)
        image = title = None
        if img:
            image = _img_tag_src(img.group())
            title = _attr(img.group(), "alt")
        _add(out, seen, url, clean_text(inner) or title or _link_label(tag, inner), image)
    return out


def _attr(tag: str, name: str) -> str | None:
    m = re.search(r"(?<![\w-])" + re.escape(name) + r"\s*=\s*[\"']([^\"']*)[\"']", tag, re.I)
    return htmllib.unescape(m.group(1)) if m else None


def _img_tag_src(tag: str) -> str | None:
    """The real picture of an <img>, preferring lazy-load attributes and srcset over src."""
    for name in ("data-srcset", "srcset"):
        if (srcset := _attr(tag, name)) and (first := srcset.split(",")[0].split()):
            if image := _image_value(first[0]):
                return image
    for name in LAZY_SRC_ATTRS:
        if (src := _attr(tag, name)) and (image := _image_value(src.strip())):
            return image
    return None


def _link_label(tag: str, inner: str) -> str | None:
    """aria-label/title on the link or anything inside it (e.g. a heading-less card)."""
    for part in (tag, inner):
        for name in ("aria-label", "title"):
            if value := _attr(part, name):
                return value
    return None


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
