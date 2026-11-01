import AddGarment from "./AddGarment.jsx";
import AdminHome from "./AdminHome.jsx";
import GarmentEdit from "./GarmentEdit.jsx";
import GarmentList from "./GarmentList.jsx";
import Programs from "./Programs.jsx";
import Settings from "./Settings.jsx";
import ItemEdit from "../kitchen/admin/ItemEdit.jsx";
import ItemList from "../kitchen/admin/ItemList.jsx";

export default function AdminRoutes({ route }) {
  switch (route.path) {
    case "/admin/ny":
      return <AddGarment />;
    case "/admin/plagg":
      return <GarmentList />;
    case "/admin/program":
      return <Programs />;
    case "/admin/installningar":
      return <Settings />;
    case "/admin/varor":
      return <ItemList />;
    default:
      if (route.path.startsWith("/admin/plagg/")) return <GarmentEdit id={route.params.id} />;
      if (route.path.startsWith("/admin/varor/")) return <ItemEdit id={route.params.id} />;
      return <AdminHome />;
  }
}
