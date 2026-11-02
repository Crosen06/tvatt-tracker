"""Application factory. Run with: uvicorn --factory app.main:create_app"""

import contextlib
from pathlib import Path

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from app.config import resolve_data_dir
from app.db import connect, init_db
from app.events import EventBus
from app.kitchen import vision
from app.kitchen.scanner import Scanner, default_source_factory
from app.kitchen.vision_service import VisionService
from app.routers import events, garments, kitchen_items, kitchen_recipes, kitchen_scan, kitchen_vision, people, programs, settings, suggestions, washes
from app.web import http_error


STATIC_DIR = Path(__file__).parent / "static"


async def health(request):
    return JSONResponse({"ok": True})


async def api_not_found(request):
    raise HTTPException(404, "Not Found")


async def spa(request):
    """Serve built files, falling back to index.html for client-side routes."""
    path = request.path_params.get("path", "")
    if path.startswith("api/") or path == "api":
        raise HTTPException(404, "Not Found")
    candidate = (STATIC_DIR / path).resolve()
    if path and candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
        return FileResponse(candidate, headers={"Cache-Control": "public, max-age=604800"})
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        return JSONResponse({"detail": "Gränssnittet är inte byggt. Kör: cd frontend && node build.mjs"}, 503)
    return FileResponse(index, headers={"Cache-Control": "no-cache"})


def create_app(data_dir: Path | None = None, camera_factory=None, vision_loader=None) -> Starlette:
    data_dir = resolve_data_dir(data_dir)
    (data_dir / "photos" / "thumb").mkdir(parents=True, exist_ok=True)
    (data_dir / "vision").mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "tvatt.db"
    conn = connect(db_path)
    init_db(conn)
    conn.close()

    routes = [
        Route("/api/health", health),
        *people.routes,
        *programs.routes,
        *settings.routes,
        *garments.routes,
        *suggestions.routes,
        *washes.routes,
        *events.routes,
        *kitchen_items.routes,
        *kitchen_recipes.routes,
        *kitchen_scan.routes,
        *kitchen_vision.routes,
        Route("/api/{path:path}", api_not_found, methods=["GET", "POST", "PATCH", "PUT", "DELETE"]),
        Mount("/photos", app=StaticFiles(directory=data_dir / "photos"), name="photos"),
        Mount("/vision", app=StaticFiles(directory=data_dir / "vision"), name="vision"),
        Route("/{path:path}", spa, methods=["GET", "HEAD"]),
    ]
    @contextlib.asynccontextmanager
    async def lifespan(app):
        yield
        app.state.scanner.stop()

    app = Starlette(routes=routes, exception_handlers={HTTPException: http_error}, lifespan=lifespan)
    app.state.bus = EventBus()
    app.state.vision = VisionService(data_dir, db_path, lambda topic: app.state.bus.publish(topic), loader=vision_loader or vision.load_embedder)

    def on_scan(code: str) -> None:
        app.state.bus.publish("scan")
        app.state.vision.on_barcode(code, app.state.scanner.latest_frame())

    app.state.scanner = Scanner(
        camera_factory or default_source_factory,
        on_scan,
        on_change=lambda: app.state.bus.publish("scan"),
        overlay=lambda img, size: app.state.vision.draw_overlay(img, size),
    )
    app.state.data_dir = data_dir
    app.state.db_path = db_path
    return app
