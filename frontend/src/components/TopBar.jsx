import { isKiosk, navigate, section, switchSection } from "../lib/router.js";
import { openScan, useStore } from "../lib/store.js";
import { formatClock, formatShort, progress, remainingMs, useNow } from "../lib/time.js";
import { CameraIcon, GearIcon } from "./Icons.jsx";
import Porthole from "./Porthole.jsx";

export default function TopBar({ route }) {
  const { people, garments, wash, serverOffsetMs, shopping } = useStore();
  const now = useNow(1000);
  const activeId = route.params.id ?? people[0]?.id;
  const onPerson = route.path === "/" || route.path.startsWith("/p/");
  const basketTotal = garments.filter((g) => g.in_basket && !g.in_wash).length;
  const left = remainingMs(wash, serverOffsetMs, now);
  const kitchen = section(route.path) === "kitchen" || /^\/admin\/(varor|recept)/.test(route.path);
  const kitchenTabs = [
    { path: "/kok/skafferi", label: "Skafferi" },
    { path: "/kok/handla", label: "Handla", count: shopping.entries.length },
    { path: "/kok/recept", label: "Recept" },
  ];

  return (
    <header className="topbar">
      <div className="switch" role="group" aria-label="Del av appen">
        <button aria-pressed={!kitchen} onClick={() => kitchen && switchSection("wash")}>Tvätt</button>
        <button aria-pressed={kitchen} onClick={() => !kitchen && switchSection("kitchen")}>Kök</button>
      </div>
      {kitchen ? (
        <nav className="tabs" aria-label="Kök">
          {kitchenTabs.map((t) => {
            const active = route.path.startsWith(t.path) || (t.path === "/kok/recept" && route.path === "/kok/ica");
            return (
              <button key={t.path} className={`tab tab-kitchen${active ? " is-active" : ""}`} onClick={() => navigate(t.path)} aria-current={active ? "page" : undefined}>
                {t.label}
                {t.count > 0 && <span className="tab-count">{t.count}</span>}
              </button>
            );
          })}
        </nav>
      ) : (
      <nav className="tabs" aria-label="Personer och tvätt">
        {people.map((p) => {
          const n = garments.filter((g) => g.person_id === p.id && g.in_basket && !g.in_wash).length;
          const active = onPerson && p.id === activeId;
          return (
            <button key={p.id} className={`tab${active ? " is-active" : ""}`} style={{ "--accent": p.color }} onClick={() => navigate(`/p/${p.id}`)} aria-current={active ? "page" : undefined}>
              <span className="tab-dot" />
              {p.name}
              {n > 0 && <span className="tab-count">{n}</span>}
            </button>
          );
        })}
        <button className={`tab tab-wash${route.path === "/tvatta" ? " is-active" : ""}`} onClick={() => navigate("/tvatta")} aria-current={route.path === "/tvatta" ? "page" : undefined}>
          Tvätta
          {basketTotal > 0 && <span className="tab-count">{basketTotal}</span>}
        </button>
      </nav>
      )}
      <div className="topbar-right">
        {wash && (
          <button className="wash-chip" onClick={() => navigate("/tvatta")} aria-label={left > 0 ? `Tvätt pågår, ${formatShort(left)} kvar` : "Tvätten är klar"}>
            <Porthole size={34} progress={progress(wash, serverOffsetMs, now)} running={left > 0} done={left <= 0} />
            <span className="wash-chip-time">{formatShort(left)}</span>
          </button>
        )}
        {!isKiosk && !kitchen && (
          <button className="btn btn-primary add-btn" onClick={() => navigate("/admin/ny")}>
            <CameraIcon width={20} height={20} />
            Lägg till plagg
          </button>
        )}
        {isKiosk && kitchen && (
          <button className="btn scan-btn" onClick={openScan}>
            <CameraIcon width={22} height={22} />
            Skanna
          </button>
        )}
        <span className="clock">{formatClock(now)}</span>
        <button className="icon-btn" onClick={() => navigate("/admin")} aria-label={isKiosk ? "Inställningar" : "Hantera"}>
          <GearIcon />
        </button>
      </div>
    </header>
  );
}
