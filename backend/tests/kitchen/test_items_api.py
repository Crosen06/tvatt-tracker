import pytest


def item_by_name(client, name):
    return next(i for i in client.get("/api/items").json() if i["name"] == name)


def entries(client):
    return client.get("/api/shopping").json()["entries"]


def test_create_item_and_list(client):
    r = client.post("/api/items", json={"name": "  Halloumi ", "category": "Kyl"})
    assert r.status_code == 201, r.text
    it = r.json()
    assert it["name"] == "Halloumi" and it["status"] == "out" and it["on_list"] is False
    assert set(it) >= {"id", "name", "category", "status", "count", "staple", "counted", "match_words", "buy_count", "on_list"}
    assert item_by_name(client, "Halloumi")["id"] == it["id"]


def test_blank_name_rejected(client):
    assert client.post("/api/items", json={"name": "   ", "category": "Kyl"}).status_code == 422
    mid = item_by_name(client, "Mjölk")["id"]
    assert client.patch(f"/api/items/{mid}", json={"name": "  "}).status_code == 422


def test_bad_category_and_status_rejected(client):
    assert client.post("/api/items", json={"name": "X", "category": "Garage"}).status_code == 422
    mid = item_by_name(client, "Mjölk")["id"]
    assert client.patch(f"/api/items/{mid}", json={"status": "gone"}).status_code == 422


def test_duplicate_name_409(client):
    r = client.post("/api/items", json={"name": "mjölk", "category": "Kyl"})
    assert r.status_code == 409
    assert "finns redan" in r.json()["detail"]


def test_set_out_adds_to_list(client):
    mid = item_by_name(client, "Mjölk")["id"]
    client.patch(f"/api/items/{mid}", json={"status": "in_stock"})
    r = client.patch(f"/api/items/{mid}", json={"status": "out"})
    body = r.json()
    assert body["item"]["status"] == "out" and body["item"]["on_list"] is True
    assert body["previous"] == {"status": "in_stock", "count": None}
    assert isinstance(body["list_entry_id"], int)
    assert [e["text"] for e in entries(client)] == ["Mjölk"]


def test_out_twice_no_duplicate(client):
    mid = item_by_name(client, "Mjölk")["id"]
    client.patch(f"/api/items/{mid}", json={"status": "in_stock"})
    client.post("/api/shopping", json={"item_id": mid})
    r = client.patch(f"/api/items/{mid}", json={"status": "out"})
    assert r.json()["list_entry_id"] is None
    r = client.patch(f"/api/items/{mid}", json={"status": "out"})
    assert r.json()["list_entry_id"] is None
    assert len(entries(client)) == 1


def test_auto_list_off_does_not_add(client):
    client.patch("/api/settings", json={"auto_list": False})
    mid = item_by_name(client, "Mjölk")["id"]
    client.patch(f"/api/items/{mid}", json={"status": "in_stock"})
    assert client.patch(f"/api/items/{mid}", json={"status": "out"}).json()["list_entry_id"] is None
    assert entries(client) == []


def test_undo_restores_and_removes_auto_entry(client):
    mid = item_by_name(client, "Smör")["id"]
    client.patch(f"/api/items/{mid}", json={"status": "low"})
    r = client.patch(f"/api/items/{mid}", json={"status": "out"}).json()
    prev, entry = r["previous"], r["list_entry_id"]
    client.patch(f"/api/items/{mid}", json=prev)
    assert client.delete(f"/api/shopping/{entry}").status_code == 204
    assert entries(client) == []
    assert item_by_name(client, "Smör")["status"] == "low"


def test_counted_item_count_zero_is_out(client):
    eid = item_by_name(client, "Ägg")["id"]
    r = client.patch(f"/api/items/{eid}", json={"count": 2}).json()
    assert r["item"]["status"] == "in_stock" and r["item"]["count"] == 2
    r = client.patch(f"/api/items/{eid}", json={"count": 0}).json()
    assert r["item"]["status"] == "out" and r["list_entry_id"] is not None
    assert client.patch(f"/api/items/{eid}", json={"count": -1}).status_code == 422


def test_add_to_list_increments_buy_count_and_frequent_order(client):
    a, b = item_by_name(client, "Banan")["id"], item_by_name(client, "Kaffe")["id"]
    for _ in range(2):
        e = client.post("/api/shopping", json={"item_id": b}).json()["entry"]
        client.delete(f"/api/shopping/{e['id']}")
    r = client.post("/api/shopping", json={"item_id": a})
    assert r.status_code == 201
    again = client.post("/api/shopping", json={"item_id": a})
    assert again.status_code == 200 and again.json() == {"entry": None, "already": True}
    freq = client.get("/api/shopping").json()["frequent"]
    assert [f["name"] for f in freq[:2]] == ["Kaffe", "Banan"]
    assert freq[0]["buy_count"] == 2 and freq[1]["buy_count"] == 1
    assert len(freq) <= 24


def test_shopping_text_entry(client):
    r = client.post("/api/shopping", json={"text": " Födelsedagsljus ", "note": "till fredag"})
    assert r.status_code == 201
    e = entries(client)[0]
    assert (e["text"], e["note"], e["item_id"]) == ("Födelsedagsljus", "till fredag", None)
    assert client.post("/api/shopping", json={"text": "  "}).status_code == 422
    assert client.post("/api/shopping", json={}).status_code == 422
    assert client.post("/api/shopping", json={"text": "x", "item_id": 1}).status_code == 422
    assert client.post("/api/shopping", json={"item_id": 99999}).status_code == 404


def test_unpack_sets_in_stock_and_increments_count(client):
    egg, milk = item_by_name(client, "Ägg")["id"], item_by_name(client, "Mjölk")["id"]
    client.patch(f"/api/items/{egg}", json={"count": 1})
    e1 = client.post("/api/shopping", json={"item_id": egg}).json()["entry"]["id"]
    e2 = client.post("/api/shopping", json={"text": "Servetter"}).json()["entry"]["id"]
    e3 = client.post("/api/shopping", json={"item_id": milk}).json()["entry"]["id"]
    assert client.post("/api/shopping/unpack", json={"entry_ids": [e1, e2]}).status_code == 200
    assert item_by_name(client, "Ägg")["count"] == 2
    assert item_by_name(client, "Ägg")["status"] == "in_stock"
    assert item_by_name(client, "Mjölk")["status"] == "out"
    assert [e["id"] for e in entries(client)] == [e3]


def test_archive_item_unlinks_and_removes_entry(client):
    mid = item_by_name(client, "Mjölk")["id"]
    client.post("/api/shopping", json={"item_id": mid})
    assert client.delete(f"/api/items/{mid}").status_code == 204
    assert entries(client) == []
    assert all(i["name"] != "Mjölk" for i in client.get("/api/items").json())
    # name is free again after archiving
    assert client.post("/api/items", json={"name": "Mjölk", "category": "Kyl"}).status_code == 201


def test_non_int_id_422(client):
    assert client.patch("/api/items/abc", json={"status": "out"}).status_code in (404, 422)
    assert client.patch("/api/items/99999", json={"status": "out"}).status_code == 404


def test_events_published(client, app):
    seen = []
    app.state.bus.publish = seen.append
    mid = item_by_name(client, "Mjölk")["id"]
    client.patch(f"/api/items/{mid}", json={"status": "in_stock"})
    client.patch(f"/api/items/{mid}", json={"status": "out"})
    assert "items" in seen and "shopping" in seen


def test_counted_item_marked_in_stock_gets_count_one(client):
    eid = item_by_name(client, "Ägg")["id"]
    r = client.patch(f"/api/items/{eid}", json={"status": "in_stock"}).json()
    assert r["item"]["count"] == 1
    r = client.patch(f"/api/items/{eid}", json={"status": "out"}).json()
    assert r["item"]["count"] == 0


def test_count_delta_is_relative(client):
    eid = item_by_name(client, "Ägg")["id"]
    for _ in range(3):
        client.patch(f"/api/items/{eid}", json={"count_delta": 1})
    assert item_by_name(client, "Ägg")["count"] == 3
    assert item_by_name(client, "Ägg")["status"] == "in_stock"
    r = client.patch(f"/api/items/{eid}", json={"count_delta": -5}).json()
    assert r["item"]["count"] == 0 and r["item"]["status"] == "out" and r["list_entry_id"] is not None
    assert client.patch(f"/api/items/{eid}", json={"count_delta": 1, "count": 4}).status_code == 422
