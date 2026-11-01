import asyncio

from app.events import EventBus


def test_list_people(client):
    r = client.get("/api/people")
    assert r.status_code == 200
    assert [p["name"] for p in r.json()] == ["Charlie", "Kiki", "Magnus"]
    assert set(r.json()[0]) == {"id", "name", "color", "sort"}


def test_rename_person(client):
    pid = client.get("/api/people").json()[1]["id"]
    r = client.patch(f"/api/people/{pid}", json={"name": "Kristina", "color": "#ff0000"})
    assert r.status_code == 200
    assert r.json()["name"] == "Kristina"
    assert client.get("/api/people").json()[1]["color"] == "#ff0000"


def test_create_person(client):
    r = client.post("/api/people", json={"name": "Gäst", "color": "#123456"})
    assert r.status_code == 201
    assert [p["name"] for p in client.get("/api/people").json()][-1] == "Gäst"


def test_create_program_validates_care(client):
    r = client.post("/api/programs", json={"name": "X", "duration_min": 30, "temp": 30, "care": "x"})
    assert r.status_code == 422
    assert "detail" in r.json()


def test_create_and_patch_program(client):
    r = client.post("/api/programs", json={"name": "Ull 20°", "duration_min": 40, "temp": 20, "care": "wool"})
    assert r.status_code == 201
    pid = r.json()["id"]
    r = client.patch(f"/api/programs/{pid}", json={"duration_min": 55})
    assert r.status_code == 200 and r.json()["duration_min"] == 55


def test_program_duration_bounds(client):
    r = client.post("/api/programs", json={"name": "X", "duration_min": 0, "temp": 30, "care": "normal"})
    assert r.status_code == 422


def test_delete_program_hides_it(client):
    progs = client.get("/api/programs").json()
    assert len(progs) == 6
    r = client.delete(f"/api/programs/{progs[0]['id']}")
    assert r.status_code == 204
    assert [p["id"] for p in client.get("/api/programs").json()] == [p["id"] for p in progs[1:]]


def test_unknown_id_404(client):
    assert client.patch("/api/people/999", json={"name": "x"}).status_code == 404
    assert client.patch("/api/programs/999", json={"name": "x"}).status_code == 404


def test_settings_roundtrip(client):
    assert client.get("/api/settings").json()["split_hot"] is True
    r = client.patch("/api/settings", json={"split_hot": False})
    assert r.status_code == 200 and r.json()["split_hot"] is False
    assert client.get("/api/settings").json()["split_hot"] is False


def test_publish_reaches_subscriber():
    async def run():
        bus = EventBus()
        received = []

        async def listen():
            async for topic in bus.subscribe():
                received.append(topic)
                if len(received) == 2:
                    return

        task = asyncio.create_task(listen())
        await asyncio.sleep(0)
        bus.publish("garments")
        bus.publish("wash")
        await asyncio.wait_for(task, 1)
        return received

    assert asyncio.run(run()) == ["garments", "wash"]


def test_mutation_publishes(app, client):
    seen = []
    app.state.bus.publish = seen.append
    client.patch("/api/settings", json={"split_hot": False})
    assert seen == ["settings"]


def test_sse_disconnect_is_clean(app):
    """A client that goes away must not raise (it used to log a traceback per disconnect)."""
    sent = []

    async def run():
        disconnected = asyncio.Event()

        async def receive():
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)
            if message["type"] == "http.response.body" and message.get("body"):
                disconnected.set()

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
            "scheme": "http", "path": "/api/events", "raw_path": b"/api/events", "query_string": b"",
            "root_path": "", "headers": [], "client": ("127.0.0.1", 1), "server": ("127.0.0.1", 80),
            "state": {},
        }
        await asyncio.wait_for(app(scope, receive, send), 3)
        assert app.state.bus._queues == set()

    asyncio.run(run())
    assert sent[0]["status"] == 200


def test_settings_auto_list_roundtrip(client):
    assert client.get("/api/settings").json()["auto_list"] is True
    r = client.patch("/api/settings", json={"auto_list": False})
    assert r.status_code == 200 and r.json()["auto_list"] is False
    assert client.get("/api/settings").json()["auto_list"] is False
    assert client.get("/api/settings").json()["split_hot"] is True
