"""Application factory. Run with: uvicorn --factory app.main:create_app"""

from pathlib import Path

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from app.config import resolve_data_dir
from app.db import connect, init_db
from app.events import EventBus
from app.routers import events, garments, people, programs, settings
from app.web import http_error


async def health(request):
    return JSONResponse({"ok": True})


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
        *events.routes,
        Mount("/photos", app=StaticFiles(directory=data_dir / "photos"), name="photos"),
    ]
    app = Starlette(routes=routes, exception_handlers={HTTPException: http_error})
    app.state.bus = EventBus()
    app.state.data_dir = data_dir
    app.state.db_path = db_path
    return app
