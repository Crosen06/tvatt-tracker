import { useEffect, useState } from "react";

export const isKiosk = new URLSearchParams(window.location.search).has("kiosk");

function parse() {
  const path = window.location.hash.replace(/^#/, "") || "/";
  const params = {};
  let m;
  if ((m = path.match(/^\/p\/(\d+)$/))) params.id = Number(m[1]);
  if ((m = path.match(/^\/admin\/plagg\/(\d+)$/))) params.id = Number(m[1]);
  return { path, params };
}

export function useRoute() {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const onHash = () => setRoute(parse());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  return route;
}

export const navigate = (path) => {
  window.location.hash = path;
};
