"""Small helpers that give Starlette FastAPI-like ergonomics."""

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

M = TypeVar("M", bound=BaseModel)


async def parse(request: Request, model: type[M]) -> M:
    try:
        data = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(422, "Ogiltig JSON.")
    return validate(model, data)


FIELD_LABELS = {"name": "namn", "category": "kategori", "count": "antal", "text": "text", "title": "titel", "url": "länk"}


def validate(model: type[M], data) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as e:
        first = e.errors()[0]
        if not first["loc"]:
            raise HTTPException(422, "Ogiltiga uppgifter.")
        loc = ".".join(FIELD_LABELS.get(str(p), str(p)) for p in first["loc"])
        raise HTTPException(422, f"Ogiltigt värde för {loc}.")


def ok(data, status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status)


def no_content() -> Response:
    return Response(status_code=204)


def path_id(request: Request) -> int:
    return int(request.path_params["id"])


def publish(request: Request, *topics: str) -> None:
    for t in topics:
        request.app.state.bus.publish(t)


async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
