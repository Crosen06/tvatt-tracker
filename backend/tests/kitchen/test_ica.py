from pathlib import Path

from app.kitchen import fetch, ica

FIX = Path(__file__).parent / "fixtures"


def page(name):
    return (FIX / name).read_text()


def test_search_url():
    assert ica.search_url("kyckling curry") == "https://www.ica.se/recept/?q=kyckling+curry"
    assert ica.search_url("ägg") == "https://www.ica.se/recept/?q=%C3%A4gg"


def test_is_recipe_url():
    assert ica.is_recipe_url("https://www.ica.se/recept/pasta-carbonara-713012/")
    assert not ica.is_recipe_url("https://www.ica.se/recept/pasta/")
    assert not ica.is_recipe_url("https://evil.se/recept/pasta-carbonara-713012/")
    assert not ica.is_recipe_url("http://www.ica.se/recept/pasta-carbonara-713012/")


def test_parse_search_itemlist():
    r = ica.parse_search(page("ica_search_itemlist.html"))
    assert r == [
        {"url": "https://www.ica.se/recept/kramig-kycklinggryta-722668/", "title": "Krämig kycklinggryta", "image": "https://assets.example.se/a.jpg"},
        {"url": "https://www.ica.se/recept/kyckling-i-ugn-713399/", "title": "Kyckling i ugn", "image": "https://assets.example.se/b.jpg"},
    ]


def test_parse_search_next_data():
    r = ica.parse_search(page("ica_search_next.html"))
    assert [(x["url"], x["title"], x["image"]) for x in r] == [
        ("https://www.ica.se/recept/pasta-carbonara-713012/", "Pasta carbonara", "https://assets.example.se/c.jpg"),
        ("https://www.ica.se/recept/snabb-tomatsoppa-720001/", "Snabb tomatsoppa", "https://assets.example.se/d.jpg"),
    ]


def test_parse_search_links():
    r = ica.parse_search(page("ica_search_links.html"))
    assert len(r) == 20
    assert r[0] == {"url": "https://www.ica.se/recept/lasagne-720000/", "title": "Lasagne", "image": "https://assets.example.se/l.jpg"}
    assert r[1]["title"] == "Fiskgratäng & potatis" and r[1]["image"] is None
    assert len({x["url"] for x in r}) == 20
    assert all("/recept/kyckling/" not in x["url"] for x in r)


def test_parse_search_empty():
    assert ica.parse_search("<html></html>") == []


def test_preview_cache(monkeypatch):
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        return page("ica_recipe.html").encode()

    monkeypatch.setattr(fetch, "get", fake_get)
    now = [1000.0]
    cache = ica.PreviewCache(maxsize=2, ttl=1800, clock=lambda: now[0])
    url = "https://www.ica.se/recept/kramig-kycklinggryta-722668/"
    assert cache.get(url).title.startswith("Krämig")
    cache.get(url)
    assert len(calls) == 1
    now[0] += 1801
    cache.get(url)
    assert len(calls) == 2
    cache.get("https://www.ica.se/recept/a-1/")
    cache.get("https://www.ica.se/recept/b-2/")
    assert len(cache) == 2
