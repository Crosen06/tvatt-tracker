import { useEffect } from "react";
import AdminRoutes from "./admin/AdminRoutes.jsx";
import DoneOverlay from "./components/DoneOverlay.jsx";
import PersonTab from "./components/PersonTab.jsx";
import TopBar from "./components/TopBar.jsx";
import WashTab from "./components/WashTab.jsx";
import Pantry from "./kitchen/Pantry.jsx";
import Recipes from "./kitchen/Recipes.jsx";
import ScanSheet from "./kitchen/ScanSheet.jsx";
import Shopping from "./kitchen/Shopping.jsx";
import { useRoute } from "./lib/router.js";
import { clearToast, connectEvents, loadAll, useStore } from "./lib/store.js";

export default function App() {
  const { loaded, online, people, toast, scanOpen } = useStore();
  const route = useRoute();

  useEffect(() => {
    loadAll();
    const es = connectEvents();
    return () => es.close();
  }, []);

  let page = null;
  if (loaded) {
    if (route.path.startsWith("/admin")) page = <AdminRoutes route={route} />;
    else if (route.path.startsWith("/kok/handla")) page = <Shopping />;
    else if (route.path.startsWith("/kok/recept") || route.path.startsWith("/kok/ica")) page = <Recipes route={route} />;
    else if (route.path.startsWith("/kok")) page = <Pantry />;
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
          {toast.action && (
            <button
              className="toast-action"
              onClick={() => {
                clearToast();
                toast.action.run();
              }}
            >
              {toast.action.label}
            </button>
          )}
        </div>
      )}
      {scanOpen && <ScanSheet />}
      <DoneOverlay />
    </div>
  );
}
