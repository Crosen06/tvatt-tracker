from starlette.routing import Route

from app.db import open_db
from app.models import SettingsPatch
from app.web import ok, parse, publish


def read_settings(conn) -> dict:
    values = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM setting")}
    return {"split_hot": values.get("split_hot", "1") == "1"}


async def get_settings(request):
    with open_db(request) as conn:
        return ok(read_settings(conn))


async def patch_settings(request):
    body = await parse(request, SettingsPatch)
    with open_db(request) as conn:
        if body.split_hot is not None:
            conn.execute(
                "INSERT INTO setting (key, value) VALUES ('split_hot', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("1" if body.split_hot else "0",),
            )
        result = read_settings(conn)
    publish(request, "settings")
    return ok(result)


routes = [
    Route("/api/settings", get_settings, methods=["GET"]),
    Route("/api/settings", patch_settings, methods=["PATCH"]),
]
