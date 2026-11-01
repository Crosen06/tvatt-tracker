from datetime import datetime, timedelta, timezone

import pytest

from tests.helpers import make_garment

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def now(monkeypatch):
    state = {"t": T0}
    monkeypatch.setattr("app.clock.utcnow", lambda: state["t"])
    return state


def in_basket(client, **kw):
    g = make_garment(client, **kw)
    client.post(f"/api/garments/{g['id']}/basket", json={"in_basket": True})
    return g


def test_suggestions_from_basket(client):
    a = in_basket(client, name="A")
    b = in_basket(client, name="B", person_id=2, max_spin=800, tumble_dry=False)
    w = in_basket(client, name="W", color="white")
    make_garment(client, name="not in basket")
    s = client.get("/api/suggestions").json()
    assert len(s) == 2
    assert s[0]["item_ids"] == [a["id"], b["id"]]
    assert (s[0]["color"], s[0]["care"], s[0]["temp"], s[0]["spin"]) == ("dark", "normal", 40, 800)
    assert s[0]["program_id"] == client.get("/api/programs").json()[0]["id"]
    assert s[0]["no_dry_ids"] == [b["id"]]
    assert s[0]["person_ids"] == [1, 2]
    assert s[1]["item_ids"] == [w["id"]]


def test_suggestions_empty(client):
    assert client.get("/api/suggestions").json() == []


def test_suggestions_respect_split_hot_setting(client):
    in_basket(client, max_temp=60)
    in_basket(client, max_temp=40)
    assert len(client.get("/api/suggestions").json()) == 2
    client.patch("/api/settings", json={"split_hot": False})
    assert len(client.get("/api/suggestions").json()) == 1


def test_check_endpoint_conflict(client):
    a = in_basket(client, color="white")
    b = in_basket(client, color="dark")
    r = client.post("/api/suggestions/check", json={"garment_ids": [a["id"], b["id"]]})
    assert r.json() == {"group": None, "compatible_ids": [], "conflicts": ["Olika färggrupper: vitt + mörkt"]}


def test_check_endpoint_compatible(client):
    a = in_basket(client)
    b = in_basket(client)
    r = client.post("/api/suggestions/check", json={"garment_ids": [a["id"]]}).json()
    assert r["compatible_ids"] == [b["id"]] and r["group"]["item_ids"] == [a["id"]]


def start(client, ids, program_index=0):
    pid = client.get("/api/programs").json()[program_index]["id"]
    return client.post("/api/washes", json={"program_id": pid, "garment_ids": ids, "temp": 40, "spin": 800})


def test_start_wash_and_current(client, now):
    a = in_basket(client)
    r = start(client, [a["id"]])
    assert r.status_code == 201
    cur = client.get("/api/washes/current").json()
    w = cur["wash"]
    assert (w["name"], w["duration_min"], w["temp"], w["spin"], w["status"]) == ("Bomull 40°", 180, 40, 800, "running")
    assert w["started_at"] == "2026-11-01T12:00:00+00:00"
    assert w["ends_at"] == "2026-11-01T15:00:00+00:00"
    assert w["is_done"] is False
    assert [i["id"] for i in w["items"]] == [a["id"]]
    assert w["items"][0]["in_wash"] is True


def test_current_includes_server_now(client, now):
    r = client.get("/api/washes/current").json()
    assert r == {"wash": None, "server_now": "2026-11-01T12:00:00+00:00"}


def test_second_wash_409(client, now):
    a, b = in_basket(client), in_basket(client)
    assert start(client, [a["id"]]).status_code == 201
    r = start(client, [b["id"]])
    assert r.status_code == 409 and r.json()["detail"] == "En tvätt är redan igång."


def test_start_requires_basket_items(client, now):
    g = make_garment(client)
    assert start(client, [g["id"]]).status_code == 400
    assert start(client, []).status_code == 422


def test_is_done_after_duration(client, now):
    a = in_basket(client)
    start(client, [a["id"]])
    now["t"] = T0 + timedelta(minutes=180)
    assert client.get("/api/washes/current").json()["wash"]["is_done"] is True


def test_finish_empties_basket(client, now):
    a, b = in_basket(client), in_basket(client)
    wid = start(client, [a["id"]]).json()["id"]
    assert client.post(f"/api/washes/{wid}/finish").status_code == 200
    assert client.get("/api/washes/current").json()["wash"] is None
    garments = {g["id"]: g for g in client.get("/api/garments").json()}
    assert garments[a["id"]]["in_basket"] is False and garments[a["id"]]["in_wash"] is False
    assert garments[b["id"]]["in_basket"] is True


def test_cancel_keeps_basket(client, now):
    a = in_basket(client)
    wid = start(client, [a["id"]]).json()["id"]
    assert client.post(f"/api/washes/{wid}/cancel").status_code == 200
    g = client.get("/api/garments").json()[0]
    assert g["in_basket"] is True and g["in_wash"] is False
    assert start(client, [a["id"]]).status_code == 201


def test_finish_unknown_or_finished_404(client, now):
    a = in_basket(client)
    wid = start(client, [a["id"]]).json()["id"]
    client.post(f"/api/washes/{wid}/finish")
    assert client.post(f"/api/washes/{wid}/finish").status_code == 404
    assert client.post("/api/washes/999/cancel").status_code == 404


def test_program_edit_does_not_change_running_wash(client, now):
    a = in_basket(client)
    start(client, [a["id"]])
    pid = client.get("/api/programs").json()[0]["id"]
    client.patch(f"/api/programs/{pid}", json={"name": "Ny", "duration_min": 10})
    client.delete(f"/api/programs/{pid}")
    w = client.get("/api/washes/current").json()["wash"]
    assert (w["name"], w["duration_min"], w["ends_at"]) == ("Bomull 40°", 180, "2026-11-01T15:00:00+00:00")


def test_in_wash_items_excluded_from_suggestions(client, now):
    a, b = in_basket(client), in_basket(client)
    start(client, [a["id"]])
    s = client.get("/api/suggestions").json()
    assert s[0]["item_ids"] == [b["id"]]
