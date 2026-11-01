"""Score recipes against the pantry: *Vad kan vi laga?* (spec §6). Pure functions."""

HOME = ("in_stock", "low")


def line_state(ing: dict, items: dict[int, dict]) -> str:
    if ing["ignored"]:
        return "ignored"
    if ing["optional"]:
        return "optional"
    item = items.get(ing["item_id"]) if ing["item_id"] is not None else None
    if item is None:
        return "unknown"
    if item["staple"] or item["status"] in HOME:
        return "have"
    return "missing"


def evaluate(ingredients: list[dict], items: dict[int, dict]) -> dict:
    ev = {"have": 0, "total": 0, "missing": [], "unknown": [], "low_used": 0}
    for ing in ingredients:
        state = line_state(ing, items)
        if state in ("ignored", "optional"):
            continue
        ev["total"] += 1
        if state == "have":
            ev["have"] += 1
            if items[ing["item_id"]]["status"] == "low":
                ev["low_used"] += 1
        elif state == "missing":
            ev["missing"].append({"id": ing["id"], "name": ing["name"], "item_id": ing["item_id"]})
        else:
            ev["unknown"].append({"id": ing["id"], "name": ing["name"]})
    return ev


def sort_key(recipe: dict, ev: dict) -> tuple:
    """Fewest missing first, then the ones that use up what is running low, then least recently cooked."""
    return (len(ev["missing"]) + len(ev["unknown"]), -ev["low_used"], recipe["last_cooked"] or "", recipe["title"].lower())
