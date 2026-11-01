"""Recipes, suggestions, import from links and ICA search."""

from urllib.parse import urlsplit

from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.routing import Route

from app.db import open_db
from app.kitchen import fetch, ica, recipe_import, repo
from app.kitchen.ingredients import match, parse_line
from app.kitchen.suggest import evaluate
from app.models import MAX_MINUTES, MAX_SERVINGS, CookedIn, ImportIn, LinkIn, RecipeIn, RecipePatch
from app.photos import PhotoTooLarge, UnsupportedPhoto, delete_photo, save_photo
from app.routers.garments import MAX_UPLOAD, _check_length, _read_photo
from app.web import no_content, ok, parse, path_id, publish, validate

MSG_NO_RECIPE = "Hittade inget recept på sidan."
MAX_IMAGE = 8_000_000


def _guard(fn):
    async def wrapper(request):
        try:
            return await fn(request)
        except repo.NotFound as e:
            raise HTTPException(404, str(e))
        except fetch.FetchError as e:
            raise HTTPException(502, str(e))
        except recipe_import.NoRecipe:
            raise HTTPException(422, MSG_NO_RECIPE)

    return wrapper


def _lines(text: str) -> list[str]:
    return [line for line in (text or "").splitlines() if line.strip()]


@_guard
async def list_recipes(request):
    with open_db(request) as conn:
        return ok(repo.list_recipes(conn))


@_guard
async def get_recipe(request):
    with open_db(request) as conn:
        return ok(repo.recipe_detail(conn, path_id(request)))


@_guard
async def create_recipe(request):
    _check_length(request)
    async with request.form(max_part_size=MAX_UPLOAD) as form:
        fields = {k: v for k, v in form.items() if k != "photo" and isinstance(v, str)}
        body = validate(RecipeIn, fields)
        photo = None
        if getattr(form.get("photo"), "filename", None):
            photo = await _read_photo(form, request)
    with open_db(request) as conn:
        rid = repo.create_recipe(
            conn, title=body.title, servings=body.servings, minutes=body.minutes,
            ingredients=_lines(body.ingredients), steps=_lines(body.steps), photo=photo,
        )
        out = repo.recipe_detail(conn, rid)
    publish(request, "recipes")
    return ok(out, 201)


@_guard
async def patch_recipe(request):
    rid = path_id(request)
    body = await parse(request, RecipePatch)
    changes = body.model_dump(exclude_unset=True)
    with open_db(request) as conn:
        repo.fetch_recipe(conn, rid)
        for field in ("title", "servings", "minutes"):
            if field in changes and not (field == "title" and changes[field] is None):
                conn.execute(f"UPDATE recipe SET {field}=? WHERE id=?", (changes[field], rid))
        if changes.get("steps") is not None:
            conn.execute("UPDATE recipe SET instructions=? WHERE id=?", ("\n".join(_lines(changes["steps"])), rid))
        if changes.get("ingredients") is not None:
            repo.set_ingredients(conn, rid, _lines(changes["ingredients"]))
        out = repo.recipe_detail(conn, rid)
    publish(request, "recipes")
    return ok(out)


@_guard
async def archive_recipe(request):
    rid = path_id(request)
    with open_db(request) as conn:
        repo.fetch_recipe(conn, rid)
        conn.execute("UPDATE recipe SET archived=1 WHERE id=?", (rid,))
    publish(request, "recipes")
    return no_content()


@_guard
async def replace_photo(request):
    rid = path_id(request)
    _check_length(request)
    with open_db(request) as conn:
        old = repo.fetch_recipe(conn, rid)["photo"]
    async with request.form(max_part_size=MAX_UPLOAD) as form:
        photo = await _read_photo(form, request)
    with open_db(request) as conn:
        conn.execute("UPDATE recipe SET photo=? WHERE id=?", (photo, rid))
        out = repo.recipe_detail(conn, rid)
    delete_photo(old, request.app.state.data_dir / "photos")
    publish(request, "recipes")
    return ok(out)


@_guard
async def link_ingredient(request):
    rid, ing_id = path_id(request), int(request.path_params["ing_id"])
    body = await parse(request, LinkIn)
    with open_db(request) as conn:
        repo.fetch_recipe(conn, rid)
        repo.link_ingredient(conn, rid, ing_id, item_id=body.item_id, ignored=body.ignored)
        out = repo.recipe_detail(conn, rid)
    publish(request, "recipes")
    return ok(out)


@_guard
async def missing_to_list(request):
    with open_db(request) as conn:
        added = repo.missing_to_list(conn, path_id(request))
    publish(request, "shopping", "items")
    return ok({"added": added})


@_guard
async def cooked(request):
    body = await parse(request, CookedIn)
    with open_db(request) as conn:
        repo.mark_cooked(conn, path_id(request), [(u.item_id, u.status) for u in body.updates])
    publish(request, "recipes", "items", "shopping")
    return ok({"ok": True})


def _download_photo(url: str, photos_dir) -> str | None:
    """Best effort: a recipe without its picture is still worth saving."""
    try:
        return save_photo(fetch.get(url, max_bytes=MAX_IMAGE, accept="image/*"), photos_dir)
    except (fetch.FetchError, UnsupportedPhoto, PhotoTooLarge):
        return None


@_guard
async def import_recipe(request):
    body = await parse(request, ImportIn)
    url = body.url.strip()
    with open_db(request) as conn:
        existing = repo.recipe_by_url(conn, url)
    if existing:
        return ok({"id": existing["id"], "existing": True})
    imported = await run_in_threadpool(recipe_import.import_url, url)
    photo = None
    if imported.image_url:
        photo = await run_in_threadpool(_download_photo, imported.image_url, request.app.state.data_dir / "photos")
    host = (urlsplit(url).hostname or "").lower()
    source = "ica" if host == "ica.se" or host.endswith(".ica.se") else "web"
    with open_db(request) as conn:
        existing = repo.recipe_by_url(conn, url)  # another tap may have saved it meanwhile
        if existing:
            delete_photo(photo, request.app.state.data_dir / "photos")
            return ok({"id": existing["id"], "existing": True})
        rid = repo.create_recipe(
            conn, title=imported.title,
            # Values a site gets wrong must not make the recipe impossible to edit later.
            servings=imported.servings if imported.servings and imported.servings <= MAX_SERVINGS else None,
            minutes=imported.minutes if imported.minutes and imported.minutes <= MAX_MINUTES else None,
            ingredients=imported.ingredients, steps=imported.steps, source=source, source_url=url, photo=photo,
        )
    publish(request, "recipes")
    return ok({"id": rid, "existing": False}, 201)


def _query(request) -> str:
    q = " ".join(request.query_params.get("q", "").split())
    if not 1 <= len(q) <= 80:
        raise HTTPException(422, "Skriv vad du vill söka efter.")
    return q


@_guard
async def ica_search(request):
    q = _query(request)
    return ok({"results": await run_in_threadpool(ica.search, q)})


@_guard
async def ica_preview(request):
    url = request.query_params.get("url", "")
    if not ica.is_recipe_url(url):
        raise HTTPException(422, "Det är inte en länk till ett ICA-recept.")
    r = await run_in_threadpool(ica.preview_cache.get, url)
    with open_db(request) as conn:
        refs, mapping, items = repo.item_refs(conn), repo.ingredient_mapping(conn), repo.items_by_id(conn)
        saved = repo.recipe_by_url(conn, url)
    lines = []
    for i, text in enumerate(r.ingredients):
        p = parse_line(text)
        if p is None:
            continue
        iid, ignored = match(p.name, refs, mapping) if p.name else (None, True)
        lines.append({"id": i, "name": p.name, "item_id": iid, "optional": p.optional, "ignored": ignored})
    ev = evaluate(lines, items)
    return ok({
        "url": url, "title": r.title, "image": r.image_url, "minutes": r.minutes,
        "total": ev["total"], "have": ev["have"],
        "missing": [m["name"] for m in ev["missing"] + ev["unknown"]],
        "saved_id": saved["id"] if saved else None,
    })


routes = [
    Route("/api/recipes", list_recipes, methods=["GET"]),
    Route("/api/recipes", create_recipe, methods=["POST"]),
    Route("/api/recipes/import", import_recipe, methods=["POST"]),
    Route("/api/recipes/{id:int}", get_recipe, methods=["GET"]),
    Route("/api/recipes/{id:int}", patch_recipe, methods=["PATCH"]),
    Route("/api/recipes/{id:int}", archive_recipe, methods=["DELETE"]),
    Route("/api/recipes/{id:int}/photo", replace_photo, methods=["POST"]),
    Route("/api/recipes/{id:int}/ingredients/{ing_id:int}", link_ingredient, methods=["PATCH"]),
    Route("/api/recipes/{id:int}/missing-to-list", missing_to_list, methods=["POST"]),
    Route("/api/recipes/{id:int}/cooked", cooked, methods=["POST"]),
    Route("/api/ica/search", ica_search, methods=["GET"]),
    Route("/api/ica/preview", ica_preview, methods=["GET"]),
]
