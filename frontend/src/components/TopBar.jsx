import { isKiosk, navigate } from "../lib/router.js";
import { useStore } from "../lib/store.js";
import { formatClock, formatShort, progress, remainingMs, useNow } from "../lib/time.js";
import { CameraIcon, GearIcon } from "./Icons.jsx";
import Porthole from "./Porthole.jsx";

export default function TopBar({ route }) {
  const { people, garments, wash, serverOffsetMs } = useStore();
  const now = useNow(1000);
  const activeId = route.params.id ?? people[0]?.id;
  const onPerson = route.path === "/" || route.path.startsWith("/p/");
  const basketTotal = garments.filter((g) => g.in_basket && !g.in_wash).length;
  const left = remainingMs(wash, serverOffsetMs, now);

  return (
    <header className="topbar">
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
      <div className="topbar-right">
        {wash && (
          <button className="wash-chip" onClick={() => navigate("/tvatta")} aria-label={`Tvätt pågår, ${formatShort(left)} kvar`}>
            <Porthole size={34} progress={progress(wash, serverOffsetMs, now)} running={left > 0} done={left <= 0} />
            <span className="wash-chip-time">{formatShort(left)}</span>
          </button>
        )}
        {!isKiosk && (
          <button className="btn btn-primary add-btn" onClick={() => navigate("/admin/ny")}>
            <CameraIcon width={20} height={20} />
            Lägg till plagg
          </button>
        )}
        <span className="clock">{formatClock(now)}</span>
        <button className="icon-btn" onClick={() => navigate("/admin")} aria-label={isKiosk ? "Inställningar" : "Hantera plagg"}>
          <GearIcon />
        </button>
      </div>
    </header>
  );
}
