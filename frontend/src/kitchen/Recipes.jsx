import EmptyState from "../components/EmptyState.jsx";
import { isKiosk, navigate } from "../lib/router.js";
import { useStore } from "../lib/store.js";
import IcaSearch from "./IcaSearch.jsx";
import RecipeCard from "./RecipeCard.jsx";
import RecipeView from "./RecipeView.jsx";

export default function Recipes({ route }) {
  const { recipes } = useStore();
  if (route.path === "/kok/ica") return <IcaSearch />;
  if (route.params.id) return <RecipeView id={route.params.id} />;

  return (
    <section className="recipes">
      <div className="recipes-bar">
        <h2 className="grow">Vad kan vi laga?</h2>
        <button className="btn" onClick={() => navigate("/kok/ica")}>Sök på ICA</button>
        {!isKiosk && <button className="btn" onClick={() => navigate("/admin/recept/ny")}>Nytt recept</button>}
      </div>
      {recipes.length === 0 ? (
        <EmptyState title="Inga recept än">
          {isKiosk
            ? "Sök på ICA här, eller lägg in egna recept i mobilen under Hantera → Recept."
            : "Sök på ICA, klistra in en länk under Hantera → Recept eller skriv in ett eget recept."}
        </EmptyState>
      ) : (
        <div className="recipe-grid">
          {recipes.map((r) => (
            <RecipeCard key={r.id} recipe={r} />
          ))}
        </div>
      )}
    </section>
  );
}
