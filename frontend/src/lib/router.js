import { useEffect, useState } from "react";

export const isKiosk = new URLSearchParams(window.location.search).has("kiosk");

const ID_ROUTES = [/^\/p\/(\d+)$/, /^\/admin\/plagg\/(\d+)$/, /^\/kok\/recept\/(\d+)$/, /^\/admin\/varor\/(\d+)$/, /^\/admin\/recept\/(\d+)$/, /^\/admin\/bilder\/(\d+)$/];

function parse() {
  const path = window.location.hash.replace(/^#/, "") || "/";
  const params = {};
  for (const re of ID_ROUTES) {
    const m = path.match(re);
    if (m) params.id = Number(m[1]);
  }
  return { path, params };
}

// Which part of the app a path belongs to. Admin pages count as neither.
export function section(path) {
  if (path.startsWith("/kok")) return "kitchen";
  if (path.startsWith("/admin")) return "admin";
  return "wash";
}

const lastPath = { wash: "/", kitchen: "/kok/skafferi" };

export function useRoute() {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const onHash = () => setRoute(parse());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const s = section(route.path);
  if (s !== "admin") lastPath[s] = route.path;
  return route;
}

export const navigate = (path) => {
  window.location.hash = path;
};

// Switch between Tvätt and Kök, returning to the page last shown in that part.
export const switchSection = (target) => navigate(lastPath[target]);
