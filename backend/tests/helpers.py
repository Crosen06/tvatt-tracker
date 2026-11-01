import io

from PIL import Image


def jpeg_bytes(w=1600, h=1200, color=(40, 60, 90)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "JPEG")
    return buf.getvalue()


def make_garment(client, person_id=1, name="Svart tröja", **tags):
    fields = {
        "person_id": str(person_id),
        "name": name,
        "max_temp": "40",
        "color": "dark",
        "max_spin": "1200",
        "care": "normal",
        "tumble_dry": "true",
    }
    fields.update({k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in tags.items()})
    r = client.post("/api/garments", data=fields, files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")})
    assert r.status_code == 201, r.text
    return r.json()


def start_running_wash(conn, garment_ids, ends_at="2999-01-01T00:00:00+00:00"):
    cur = conn.execute(
        "INSERT INTO wash (program_id, name, duration_min, temp, spin, started_at, ends_at, status) "
        "VALUES (1, 'Bomull 40°', 180, 40, 1200, '2026-01-01T00:00:00+00:00', ?, 'running')",
        (ends_at,),
    )
    conn.executemany("INSERT INTO wash_item VALUES (?, ?)", [(cur.lastrowid, g) for g in garment_ids])
    conn.commit()
    return cur.lastrowid
