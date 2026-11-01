// Kitchen mutations shared by several pages. Each one updates the server, then lets SSE reload.
import { api } from "../lib/api.js";
import { reload, toast, getState } from "../lib/store.js";

function refresh() {
  reload("items", "shopping");
}

// patch: { status } and/or { count }. Shows an undo toast when the item went onto the list.
export async function updateItem(item, patch) {
  try {
    const r = await api.patch(`/api/items/${item.id}`, patch);
    refresh();
    if (r.list_entry_id) {
      const entryId = r.list_entry_id;
      toast(`${item.name} lades på inköpslistan`, "ok", {
        label: "Ångra",
        run: async () => {
          try {
            await api.patch(`/api/items/${item.id}`, r.previous);
            await api.del(`/api/shopping/${entryId}`);
          } catch (e) {
            toast(e.message);
          }
          refresh();
        },
      });
    }
    return r.item;
  } catch (e) {
    toast(e.message);
    return null;
  }
}

export async function addItemToList(item) {
  try {
    await api.post("/api/shopping", { item_id: item.id });
    refresh();
  } catch (e) {
    toast(e.message);
  }
}

export async function addTextToList(text, note) {
  const clean = text.trim();
  if (!clean) return false;
  const existing = getState().items.find((i) => i.name.toLowerCase() === clean.toLowerCase());
  try {
    await api.post("/api/shopping", existing ? { item_id: existing.id, note } : { text: clean, note });
    refresh();
    return true;
  } catch (e) {
    toast(e.message);
    return false;
  }
}

export async function removeFromList(entryId) {
  try {
    await api.del(`/api/shopping/${entryId}`);
    refresh();
  } catch (e) {
    toast(e.message);
  }
}

export function entryForItem(itemId) {
  return getState().shopping.entries.find((e) => e.item_id === itemId);
}

export async function toggleOnList(item) {
  const entry = entryForItem(item.id);
  if (entry) await removeFromList(entry.id);
  else await addItemToList(item);
}
