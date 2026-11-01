import AddGarment from "./AddGarment.jsx";
import AdminHome from "./AdminHome.jsx";
import GarmentEdit from "./GarmentEdit.jsx";
import GarmentList from "./GarmentList.jsx";
import Programs from "./Programs.jsx";
import Settings from "./Settings.jsx";

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
    default:
      if (route.path.startsWith("/admin/plagg/")) return <GarmentEdit id={route.params.id} />;
      return <AdminHome />;
  }
}
