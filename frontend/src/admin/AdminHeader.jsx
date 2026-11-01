import { BackIcon } from "../components/Icons.jsx";
import { navigate } from "../lib/router.js";

export default function AdminHeader({ title, back = "/admin" }) {
  return (
    <div className="admin-head">
      <button className="icon-btn" onClick={() => navigate(back)} aria-label="Tillbaka">
        <BackIcon />
      </button>
      <h1>{title}</h1>
    </div>
  );
}
