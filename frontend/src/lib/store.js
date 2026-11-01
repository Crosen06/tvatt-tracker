// Tiny global store: server data + live updates over SSE.
import { useSyncExternalStore } from "react";
import { api } from "./api.js";

let state = {
  loaded: false,
  online: true,
  people: [],
  programs: [],
  settings: { split_hot: true, auto_list: true },
  garments: [],
  suggestions: [],
  wash: null,
  serverOffsetMs: 0,
  toast: null,
  items: [],
  shopping: { entries: [], frequent: [] },
  recipes: [],
  scan: { seq: 0, code: null, error: null, running: false },
  scanOpen: false,
};
const listeners = new Set();

function set(patch) {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
}

export function useStore() {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => state,
  );
}

export const getState = () => state;

const loaders = {
  people: async () => set({ people: await api.get("/api/people") }),
  programs: async () => set({ programs: await api.get("/api/programs") }),
  settings: async () => set({ settings: await api.get("/api/settings") }),
  garments: async () => set({ garments: await api.get("/api/garments") }),
  suggestions: async () => set({ suggestions: await api.get("/api/suggestions") }),
  items: async () => set({ items: await api.get("/api/items") }),
  shopping: async () => set({ shopping: await api.get("/api/shopping") }),
  recipes: async () => set({ recipes: await api.get("/api/recipes") }),
  scan: async () => set({ scan: await api.get("/api/scan/last") }),
  wash: async () => {
    const r = await api.get("/api/washes/current");
    set({ wash: r.wash, serverOffsetMs: Date.parse(r.server_now) - Date.now() });
  },
};

const TOPICS = {
  people: ["people"],
  programs: ["programs", "suggestions"],
  settings: ["settings", "suggestions"],
  garments: ["garments", "suggestions"],
  wash: ["wash", "suggestions"],
  items: ["items", "shopping", "recipes"],
  shopping: ["shopping", "items"],
  recipes: ["recipes"],
  scan: ["scan"],
};

const pending = new Set();
let timer = null;

export function reload(...names) {
  names.forEach((n) => pending.add(n));
  clearTimeout(timer);
  timer = setTimeout(async () => {
    const batch = [...pending];
    pending.clear();
    try {
      await Promise.all(batch.map((n) => loaders[n]()));
      if (!state.online) set({ online: true });
    } catch {
      set({ online: false });
    }
  }, 40);
}

export async function loadAll() {
  try {
    await Promise.all(Object.values(loaders).map((fn) => fn()));
    set({ loaded: true, online: true });
  } catch {
    set({ online: false });
    setTimeout(loadAll, 3000);
  }
}

export function connectEvents() {
  const es = new EventSource("/api/events");
  let dropped = false;
  es.addEventListener("changed", (e) => reload(...(TOPICS[e.data] || [])));
  es.onopen = () => {
    if (dropped) {
      dropped = false;
      loadAll();
    }
    set({ online: true });
  };
  es.onerror = () => {
    dropped = true;
    set({ online: false });
  };
  // Re-sync when a phone wakes up or the tab is shown again.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") loadAll();
  });
  return es;
}

let toastTimer = null;
// action: optional { label, run } shown as a button in the toast (e.g. Ångra).
export function toast(message, kind = "error", action = null) {
  clearTimeout(toastTimer);
  set({ toast: { message, kind, action, id: Date.now() } });
  toastTimer = setTimeout(() => set({ toast: null }), action ? 6000 : 4000);
}

export const clearToast = () => set({ toast: null });

export const openScan = () => set({ scanOpen: true });
export const closeScan = () => set({ scanOpen: false });

export function patchGarmentLocal(garment) {
  set({ garments: state.garments.map((g) => (g.id === garment.id ? { ...g, ...garment } : g)) });
}

export async function setInBasket(garment, inBasket) {
  patchGarmentLocal({ id: garment.id, in_basket: inBasket });
  try {
    const updated = await api.post(`/api/garments/${garment.id}/basket`, { in_basket: inBasket });
    patchGarmentLocal(updated);
  } catch (e) {
    patchGarmentLocal({ id: garment.id, in_basket: garment.in_basket });
    toast(e.message);
  }
}
