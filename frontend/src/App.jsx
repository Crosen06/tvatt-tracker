import { useEffect } from "react";
import AdminRoutes from "./admin/AdminRoutes.jsx";
import DoneOverlay from "./components/DoneOverlay.jsx";
import PersonTab from "./components/PersonTab.jsx";
import TopBar from "./components/TopBar.jsx";
import WashTab from "./components/WashTab.jsx";
import { useRoute } from "./lib/router.js";
import { connectEvents, loadAll, useStore } from "./lib/store.js";

export default function App() {
  const { loaded, online, people, toast } = useStore();
  const route = useRoute();

  useEffect(() => {
    loadAll();
    const es = connectEvents();
    return () => es.close();
  }, []);

  let page = null;
  if (loaded) {
    if (route.path.startsWith("/admin")) page = <AdminRoutes route={route} />;
    else if (route.path === "/tvatta") page = <WashTab />;
    else page = <PersonTab personId={route.params.id ?? people[0]?.id} />;
  }

  return (
    <div className="app">
      <TopBar route={route} />
      {!online && <div className="offline" role="status">Ingen kontakt med tvätt-trackern. Försöker igen…</div>}
      <main className="main">{page}</main>
      {toast && (
        <div key={toast.id} className={`toast toast-${toast.kind}`} role="alert">
          {toast.message}
        </div>
      )}
      <DoneOverlay />
    </div>
  );
}
