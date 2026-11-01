from app.db import connect, init_db


def test_init_seeds_people_programs_settings(conn):
    people = [r["name"] for r in conn.execute("SELECT name FROM person ORDER BY sort")]
    assert people == ["Charlie", "Kiki", "Magnus"]
    programs = [
        (r["name"], r["duration_min"], r["temp"], r["care"])
        for r in conn.execute("SELECT * FROM program ORDER BY sort")
    ]
    assert programs == [
        ("Bomull 40°", 180, 40, "normal"),
        ("Bomull 60°", 200, 60, "normal"),
        ("Syntet 40°", 120, 40, "synthetic"),
        ("Fintvätt 30°", 60, 30, "delicate"),
        ("Ull 30°", 45, 30, "wool"),
        ("Snabbtvätt 30°", 30, 30, "normal"),
    ]
    split = conn.execute("SELECT value FROM setting WHERE key='split_hot'").fetchone()
    assert split["value"] == "1"


def test_init_is_idempotent(app):
    c = connect(app.state.db_path)
    init_db(c)
    init_db(c)
    assert c.execute("SELECT COUNT(*) FROM person").fetchone()[0] == 3
    assert c.execute("SELECT COUNT(*) FROM program").fetchone()[0] == 6
    c.close()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_data_dir_created(app, data_dir):
    assert (data_dir / "photos").is_dir()
    assert (data_dir / "photos" / "thumb").is_dir()
    assert (data_dir / "tvatt.db").is_file()
