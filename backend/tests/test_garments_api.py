from PIL import Image

from tests.helpers import jpeg_bytes, make_garment, start_running_wash


def test_create_garment_with_photo(client, data_dir):
    g = make_garment(client, tumble_dry=False)
    assert g["name"] == "Svart tröja"
    assert (g["max_temp"], g["color"], g["max_spin"], g["care"], g["tumble_dry"]) == (40, "dark", 1200, "normal", False)
    assert g["in_basket"] is False and g["in_wash"] is False
    fname = g["photo_url"].rsplit("/", 1)[1]
    with Image.open(data_dir / "photos" / fname) as im:
        assert max(im.size) == 1200
    with Image.open(data_dir / "photos" / "thumb" / fname) as im:
        assert max(im.size) <= 400
    assert client.get(g["thumb_url"]).status_code == 200


def test_reject_non_image_415(client):
    r = client.post(
        "/api/garments",
        data={"person_id": "1", "name": "x", "max_temp": "40", "color": "dark", "max_spin": "1200", "care": "normal", "tumble_dry": "true"},
        files={"photo": ("p.jpg", b"not an image", "image/jpeg")},
    )
    assert r.status_code == 415
    assert r.json()["detail"] == "Bildformatet stöds inte. Ta en ny bild med kameran."


def test_missing_photo_422(client):
    r = client.post(
        "/api/garments",
        data={"person_id": "1", "name": "x", "max_temp": "40", "color": "dark", "max_spin": "1200", "care": "normal", "tumble_dry": "true"},
    )
    assert r.status_code == 422


def test_invalid_tag_422(client):
    r = client.post(
        "/api/garments",
        data={"person_id": "1", "name": "x", "max_temp": "45", "color": "dark", "max_spin": "1200", "care": "normal", "tumble_dry": "true"},
        files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")},
    )
    assert r.status_code == 422
    g = make_garment(client)
    assert client.patch(f"/api/garments/{g['id']}", json={"color": "pink"}).status_code == 422


def test_unknown_person_422(client):
    r = client.post(
        "/api/garments",
        data={"person_id": "99", "name": "x", "max_temp": "40", "color": "dark", "max_spin": "1200", "care": "normal", "tumble_dry": "true"},
        files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")},
    )
    assert r.status_code == 422


def test_patch_garment(client):
    g = make_garment(client)
    r = client.patch(f"/api/garments/{g['id']}", json={"name": "Blå tröja", "color": "colored", "person_id": 2})
    assert r.status_code == 200
    assert (r.json()["name"], r.json()["color"], r.json()["person_id"]) == ("Blå tröja", "colored", 2)


def test_replace_photo(client):
    g = make_garment(client)
    r = client.post(f"/api/garments/{g['id']}/photo", files={"photo": ("p.png", jpeg_bytes(300, 300), "image/jpeg")})
    assert r.status_code == 200
    assert r.json()["photo_url"] != g["photo_url"]


def test_filter_by_person_and_basket(client):
    a = make_garment(client, person_id=1, name="A")
    make_garment(client, person_id=2, name="B")
    client.post(f"/api/garments/{a['id']}/basket", json={"in_basket": True})
    assert [g["name"] for g in client.get("/api/garments?person_id=1").json()] == ["A"]
    assert [g["name"] for g in client.get("/api/garments?in_basket=1").json()] == ["A"]
    assert [g["name"] for g in client.get("/api/garments").json()] == ["A", "B"]


def test_basket_toggle_idempotent(client):
    g = make_garment(client)
    for _ in range(2):
        r = client.post(f"/api/garments/{g['id']}/basket", json={"in_basket": True})
        assert r.status_code == 200 and r.json()["in_basket"] is True
    assert r.json()["basket_since"] is not None
    r = client.post(f"/api/garments/{g['id']}/basket", json={"in_basket": False})
    assert r.json()["in_basket"] is False and r.json()["basket_since"] is None


def test_archive_removes_from_basket(client, conn):
    g = make_garment(client)
    client.post(f"/api/garments/{g['id']}/basket", json={"in_basket": True})
    assert client.delete(f"/api/garments/{g['id']}").status_code == 204
    assert client.get("/api/garments").json() == []
    row = conn.execute("SELECT in_basket, archived FROM garment WHERE id=?", (g["id"],)).fetchone()
    assert (row["in_basket"], row["archived"]) == (0, 1)


def test_archive_or_toggle_in_wash_409(client, conn):
    g = make_garment(client)
    client.post(f"/api/garments/{g['id']}/basket", json={"in_basket": True})
    start_running_wash(conn, [g["id"]])
    assert client.get("/api/garments").json()[0]["in_wash"] is True
    r = client.post(f"/api/garments/{g['id']}/basket", json={"in_basket": False})
    assert r.status_code == 409
    assert r.json()["detail"] == "Plagget ligger i maskinen just nu."
    assert client.delete(f"/api/garments/{g['id']}").status_code == 409


def test_garment_404(client):
    assert client.post("/api/garments/999/basket", json={"in_basket": True}).status_code == 404


FIELDS = {"person_id": "1", "name": "x", "max_temp": "40", "color": "dark", "max_spin": "1200", "care": "normal", "tumble_dry": "true"}
MSG_TOO_BIG = "Bilden är för stor. Ta en ny bild med kameran."


def test_upload_too_large_413(client):
    big = b"\xff\xd8" + b"\0" * (21 * 1024 * 1024)
    r = client.post("/api/garments", data=FIELDS, files={"photo": ("p.jpg", big, "image/jpeg")})
    assert r.status_code == 413
    assert r.json()["detail"] == MSG_TOO_BIG


def test_huge_pixel_count_413(client):
    import io

    buf = io.BytesIO()
    Image.new("1", (12000, 12000)).save(buf, "PNG")
    r = client.post("/api/garments", data=FIELDS, files={"photo": ("p.png", buf.getvalue(), "image/png")})
    assert r.status_code == 413
    assert r.json()["detail"] == MSG_TOO_BIG

