import { BasketIcon, CameraIcon, GearIcon } from "../components/Icons.jsx";
import { plural } from "../lib/labels.js";
import { navigate } from "../lib/router.js";
import { useStore } from "../lib/store.js";
import AdminHeader from "./AdminHeader.jsx";

const TimerIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <circle cx="12" cy="13" r="8" />
    <path d="M12 9v4l2.5 2.5M10 2h4" />
  </svg>
);

export default function AdminHome() {
  const { garments, programs } = useStore();
  const items = [
    { to: "/admin/ny", icon: <CameraIcon />, title: "Lägg till plagg", sub: "Fota och tagga ett nytt plagg" },
    { to: "/admin/plagg", icon: <BasketIcon />, title: "Alla plagg", sub: plural(garments.length, "plagg", "plagg") },
    { to: "/admin/program", icon: <TimerIcon />, title: "Tvättprogram", sub: `${plural(programs.length, "program", "program")} och hur långa de är` },
    { to: "/admin/installningar", icon: <GearIcon />, title: "Inställningar", sub: "Personer och tvättregler" },
  ];
  return (
    <div className="admin">
      <AdminHeader title="Hantera" back="/" />
      <div className="admin-menu">
        {items.map((i) => (
          <button key={i.to} className="menu-item" onClick={() => navigate(i.to)}>
            {i.icon}
            <span className="menu-item-main">
              <span>{i.title}</span>
              <span>{i.sub}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
