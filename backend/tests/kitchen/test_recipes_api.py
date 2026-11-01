from pathlib import Path

from app.kitchen import fetch, ica
from tests.helpers import jpeg_bytes

FIX = Path(__file__).parent / "fixtures"


def items(client):
    return {i["name"]: i for i in client.get("/api/items").json()}


def set_status(client, name, status):
    client.patch(f"/api/items/{items(client)[name]['id']}", json={"status": status})


def make_recipe(client, title="Pasta med grädde", ingredients="400 g pasta\n2 dl vispgrädde\n1 purjolök\nsalt efter smak", steps="Koka pastan.\nRör ner grädden.", **extra):
    data = {"title": title, "servings": "4", "minutes": "25", "ingredients": ingredients, "steps": steps, **extra}
    r = client.post("/api/recipes", data=data)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_own_recipe_links_ingredients(client):
    r = make_recipe(client)
    d = client.get(f"/api/recipes/{r['id']}").json()
    by_name = {i["name"]: i for i in d["ingredients"]}
    it = items(client)
    assert by_name["pasta"]["item_id"] == it["Pasta"]["id"]
    assert by_name["vispgrädde"]["item_id"] == it["Grädde"]["id"]
    assert by_name["purjolök"]["item_id"] == it["Purjolök"]["id"]
    assert by_name["salt"]["optional"] is True
    assert d["steps"] == ["Koka pastan.", "Rör ner grädden."]
    assert (d["servings"], d["minutes"], d["source"]) == (4, 25, "own")


def test_create_recipe_validation(client):
    assert client.post("/api/recipes", data={"title": "  ", "ingredients": "", "steps": ""}).status_code == 422
    assert client.post("/api/recipes", data={"title": "X", "servings": "abc"}).status_code == 422
    r = client.post("/api/recipes", data={"title": "Med foto", "ingredients": "1 ägg"}, files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")})
    assert r.status_code == 201 and r.json()["thumb_url"].startswith("/photos/thumb/")


def test_recipe_detail_states(client):
    set_status(client, "Pasta", "in_stock")
    r = make_recipe(client, ingredients="400 g pasta\n2 dl vispgrädde\n1 st halloumi\nsalt efter smak\n1 dl vatten")
    d = client.get(f"/api/recipes/{r['id']}").json()
    states = {i["name"]: i["state"] for i in d["ingredients"]}
    assert states == {"pasta": "have", "vispgrädde": "missing", "halloumi": "unknown", "salt": "optional", "vatten": "ignored"}
    summary = next(x for x in client.get("/api/recipes").json() if x["id"] == r["id"])
    assert summary["eval"]["have"] == 1 and summary["eval"]["total"] == 3
    assert [m["name"] for m in summary["eval"]["missing"]] == ["vispgrädde"]


def test_recipes_sorted_by_missing(client):
    set_status(client, "Pasta", "in_stock")
    make_recipe(client, title="Saknar mycket", ingredients="1 purjolök\n2 dl grädde\n1 st halloumi")
    make_recipe(client, title="Allt finns", ingredients="400 g pasta\nsalt")
    assert [r["title"] for r in client.get("/api/recipes").json()] == ["Allt finns", "Saknar mycket"]


def test_link_ingredient_updates_map_and_other_recipes(client):
    a = make_recipe(client, title="A", ingredients="1 st halloumi")
    b = make_recipe(client, title="B", ingredients="200 g halloumi, skivad")
    ost = items(client)["Ost"]["id"]
    ing = client.get(f"/api/recipes/{a['id']}").json()["ingredients"][0]
    r = client.patch(f"/api/recipes/{a['id']}/ingredients/{ing['id']}", json={"item_id": ost})
    assert r.status_code == 200
    assert client.get(f"/api/recipes/{b['id']}").json()["ingredients"][0]["item_id"] == ost
    c = make_recipe(client, title="C", ingredients="halloumi")
    assert client.get(f"/api/recipes/{c['id']}").json()["ingredients"][0]["item_id"] == ost
    assert client.patch(f"/api/recipes/{a['id']}/ingredients/{ing['id']}", json={"item_id": 99999}).status_code == 404
    assert client.patch(f"/api/recipes/{a['id']}/ingredients/{ing['id']}", json={}).status_code == 422


def test_ignore_ingredient(client):
    a = make_recipe(client, title="A", ingredients="1 nypa kärlek")
    ing = client.get(f"/api/recipes/{a['id']}").json()["ingredients"][0]
    client.patch(f"/api/recipes/{a['id']}/ingredients/{ing['id']}", json={"ignored": True})
    d = client.get(f"/api/recipes/{a['id']}").json()
    assert d["ingredients"][0]["state"] == "ignored"
    assert d["eval"]["total"] == 0
    client.patch(f"/api/recipes/{a['id']}/ingredients/{ing['id']}", json={"ignored": False})
    assert client.get(f"/api/recipes/{a['id']}").json()["ingredients"][0]["state"] == "unknown"


def test_missing_to_list(client):
    r = make_recipe(client, title="Gryta", ingredients="2 dl vispgrädde\n1 st halloumi\n400 g pasta")
    set_status(client, "Pasta", "in_stock")
    res = client.post(f"/api/recipes/{r['id']}/missing-to-list")
    assert res.json() == {"added": 2}
    entries = client.get("/api/shopping").json()["entries"]
    assert [(e["text"], e["note"]) for e in entries] == [("Grädde", "till Gryta"), ("Halloumi", "till Gryta")]
    assert client.post(f"/api/recipes/{r['id']}/missing-to-list").json() == {"added": 0}


def test_cooked_updates_status_and_count(client):
    set_status(client, "Grädde", "in_stock")
    r = make_recipe(client, ingredients="2 dl vispgrädde")
    gid = items(client)["Grädde"]["id"]
    res = client.post(f"/api/recipes/{r['id']}/cooked", json={"updates": [{"item_id": gid, "status": "out"}]})
    assert res.status_code == 200
    d = client.get(f"/api/recipes/{r['id']}").json()
    assert d["cooked_count"] == 1 and d["last_cooked"]
    assert items(client)["Grädde"]["status"] == "out"
    assert client.get("/api/shopping").json()["entries"][0]["text"] == "Grädde"


def test_patch_recipe_replaces_ingredients(client):
    r = make_recipe(client)
    client.patch(f"/api/recipes/{r['id']}", json={"title": "Ny titel", "ingredients": "1 st ägg", "steps": "Stek."})
    d = client.get(f"/api/recipes/{r['id']}").json()
    assert d["title"] == "Ny titel" and [i["name"] for i in d["ingredients"]] == ["ägg"] and d["steps"] == ["Stek."]
    assert client.delete(f"/api/recipes/{r['id']}").status_code == 204
    assert client.get(f"/api/recipes/{r['id']}").status_code == 404


def fake_page(monkeypatch, name="ica_recipe.html", image=True):
    def get(url, **kw):
        if url.endswith(".jpg"):
            if not image:
                raise fetch.FetchError("nope")
            return jpeg_bytes(400, 300)
        return (FIX / name).read_bytes()

    monkeypatch.setattr(fetch, "get", get)


def test_import_creates_recipe(client, monkeypatch):
    fake_page(monkeypatch)
    url = "https://www.ica.se/recept/kramig-kycklinggryta-722668/"
    r = client.post("/api/recipes/import", json={"url": url})
    assert r.status_code == 201, r.text
    d = client.get(f"/api/recipes/{r.json()['id']}").json()
    assert d["title"] == "Krämig kycklinggryta med curry" and d["source"] == "ica" and d["source_url"] == url
    assert d["thumb_url"] and len(d["ingredients"]) == 7 and len(d["steps"]) == 3


def test_import_without_image_still_saves(client, monkeypatch):
    fake_page(monkeypatch, "graph_recipe.html", image=False)
    r = client.post("/api/recipes/import", json={"url": "https://mat.example.se/recept/pasta"})
    assert r.status_code == 201
    d = client.get(f"/api/recipes/{r.json()['id']}").json()
    assert d["source"] == "web" and d["thumb_url"] is None


def test_import_duplicate_returns_existing(client, monkeypatch):
    fake_page(monkeypatch)
    url = "https://www.ica.se/recept/kramig-kycklinggryta-722668/"
    first = client.post("/api/recipes/import", json={"url": url}).json()
    again = client.post("/api/recipes/import", json={"url": url})
    assert again.status_code == 200 and again.json() == {"id": first["id"], "existing": True}


def test_import_errors(client, monkeypatch):
    def boom(url, **kw):
        raise fetch.FetchError("Kunde inte nå www.ica.se. Kontrollera Pi:ns internetanslutning.")

    monkeypatch.setattr(fetch, "get", boom)
    r = client.post("/api/recipes/import", json={"url": "https://www.ica.se/recept/x-1/"})
    assert r.status_code == 502 and "Kunde inte nå" in r.json()["detail"]
    fake_page(monkeypatch, "no_recipe.html")
    r = client.post("/api/recipes/import", json={"url": "https://www.ica.se/recept/y-2/"})
    assert r.status_code == 422 and r.json()["detail"] == "Hittade inget recept på sidan."
    assert client.post("/api/recipes/import", json={"url": "inte en länk"}).status_code == 422


def test_ica_search_and_preview(client, monkeypatch):
    ica.preview_cache._data.clear()

    def get(url, **kw):
        if "?q=" in url:
            assert url == "https://www.ica.se/recept/?q=kyckling"
            return (FIX / "ica_search_itemlist.html").read_bytes()
        return (FIX / "ica_recipe.html").read_bytes()

    monkeypatch.setattr(fetch, "get", get)
    set_status(client, "Lök", "in_stock")
    res = client.get("/api/ica/search?q=kyckling").json()["results"]
    assert res[0]["title"] == "Krämig kycklinggryta"
    p = client.get("/api/ica/preview", params={"url": res[0]["url"]}).json()
    assert p["title"].startswith("Krämig") and p["total"] == 6 and p["have"] == 1
    assert "kokosmjölk" in p["missing"] and p["saved_id"] is None
    rid = client.post("/api/recipes/import", json={"url": res[0]["url"]}).json()["id"]
    assert client.get("/api/ica/preview", params={"url": res[0]["url"]}).json()["saved_id"] == rid


def test_ica_preview_rejects_other_hosts(client):
    assert client.get("/api/ica/preview", params={"url": "https://evil.se/recept/a-1/"}).status_code == 422
    assert client.get("/api/ica/search?q=").status_code == 422
    assert client.get("/api/ica/search?q=" + "x" * 81).status_code == 422


def test_archive_item_unlinks_recipe_lines(client):
    r = make_recipe(client, ingredients="1 purjolök")
    pid = items(client)["Purjolök"]["id"]
    client.delete(f"/api/items/{pid}")
    line = client.get(f"/api/recipes/{r['id']}").json()["ingredients"][0]
    assert line["item_id"] != pid


def test_new_item_rematches_unknown(client):
    r = make_recipe(client, ingredients="1 st halloumi")
    assert client.get(f"/api/recipes/{r['id']}").json()["ingredients"][0]["state"] == "unknown"
    client.post("/api/items", json={"name": "Halloumi", "category": "Kyl", "status": "in_stock"})
    assert client.get(f"/api/recipes/{r['id']}").json()["ingredients"][0]["state"] == "have"
