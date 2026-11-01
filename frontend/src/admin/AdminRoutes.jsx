import AddGarment from "./AddGarment.jsx";
import AdminHome from "./AdminHome.jsx";
import GarmentEdit from "./GarmentEdit.jsx";
import GarmentList from "./GarmentList.jsx";
import Programs from "./Programs.jsx";
import Settings from "./Settings.jsx";
import ItemEdit from "../kitchen/admin/ItemEdit.jsx";
import ItemList from "../kitchen/admin/ItemList.jsx";
import RecipeEdit from "../kitchen/admin/RecipeEdit.jsx";
import RecipeImport from "../kitchen/admin/RecipeImport.jsx";
import RecipeList from "../kitchen/admin/RecipeList.jsx";

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
    case "/admin/recept":
      return <RecipeList />;
    case "/admin/recept/ny":
      return <RecipeEdit key="new" />;
    case "/admin/recept/import":
      return <RecipeImport />;
    default:
      if (route.path.startsWith("/admin/plagg/")) return <GarmentEdit id={route.params.id} />;
      if (route.path.startsWith("/admin/varor/")) return <ItemEdit id={route.params.id} />;
      if (route.path.startsWith("/admin/recept/")) return <RecipeEdit key={route.params.id} id={route.params.id} />;
      return <AdminHome />;
  }
}
