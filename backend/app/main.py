"""Application factory. Run with: uvicorn --factory app.main:create_app"""

from pathlib import Path

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from app.config import resolve_data_dir
from app.db import connect, init_db
from app.events import EventBus
from app.routers import events, garments, people, programs, settings, suggestions, washes
from app.web import http_error


STATIC_DIR = Path(__file__).parent / "static"


async def health(request):
    return JSONResponse({"ok": True})


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


def create_app(data_dir: Path | None = None) -> Starlette:
    data_dir = resolve_data_dir(data_dir)
    (data_dir / "photos" / "thumb").mkdir(parents=True, exist_ok=True)
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
        Mount("/photos", app=StaticFiles(directory=data_dir / "photos"), name="photos"),
        Route("/{path:path}", spa, methods=["GET", "HEAD"]),
    ]
    app = Starlette(routes=routes, exception_handlers={HTTPException: http_error})
    app.state.bus = EventBus()
    app.state.data_dir = data_dir
    app.state.db_path = db_path
    return app
