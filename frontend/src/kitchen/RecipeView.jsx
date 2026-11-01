import { useEffect, useState } from "react";
import { BackIcon } from "../components/Icons.jsx";
import { api } from "../lib/api.js";
import { isKiosk, navigate } from "../lib/router.js";
import { reload, toast, useStore } from "../lib/store.js";
import CookedSheet from "./CookedSheet.jsx";
import LinkIngredientSheet from "./LinkIngredientSheet.jsx";

const STATE = {
  have: { mark: "✓", label: "finns" },
  missing: { mark: "✗", label: "saknas" },
  unknown: { mark: "?", label: "okänd vara" },
  optional: { mark: "·", label: "valfri" },
  ignored: { mark: "–", label: "räknas inte" },
};

export default function RecipeView({ id }) {
  const { recipes, items } = useStore();
  const [recipe, setRecipe] = useState(null);
  const [linking, setLinking] = useState(null);
  const [cooking, setCooking] = useState(false);
  const [error, setError] = useState(null);
  const summary = recipes.find((r) => r.id === id);

  // Reload when the pantry or recipe list changes (e.g. an item was marked out on another screen).
  useEffect(() => {
    api.get(`/api/recipes/${id}`).then(setRecipe, (e) => setError(e.message));
  }, [id, summary, items]);

  if (error) return <p className="error">{error}</p>;
  if (!recipe) return null;
  const missingCount = recipe.eval.missing.length + recipe.eval.unknown.length;

  async function missingToList() {
    try {
      const r = await api.post(`/api/recipes/${id}/missing-to-list`);
      reload("shopping", "items");
      toast(r.added === 0 ? "Allt står redan på listan." : `${r.added} ${r.added === 1 ? "vara" : "varor"} lades på inköpslistan`, "ok");
    } catch (e) {
      toast(e.message);
    }
  }

  return (
    <article className="recipe-view">
      <header className="recipe-head">
        <button className="icon-btn" onClick={() => navigate("/kok/recept")} aria-label="Tillbaka">
          <BackIcon />
        </button>
        <h1 className="grow">{recipe.title}</h1>
        {!isKiosk && (
          <button className="btn btn-ghost" onClick={() => navigate(`/admin/recept/${id}`)}>Ändra</button>
        )}
      </header>
      <p className="hint recipe-meta">
        {[recipe.servings && `${recipe.servings} portioner`, recipe.minutes && `${recipe.minutes} min`, recipe.source === "ica" && "från ICA"]
          .filter(Boolean)
          .join(" · ")}
      </p>
      <div className="recipe-cols">
        <section className="recipe-ings">
          <h2>Ingredienser</h2>
          <ul>
            {recipe.ingredients.map((i) => (
              <li key={i.id}>
                <button className={`ing is-${i.state}`} aria-label={`${i.text}, ${STATE[i.state].label}`} onClick={() => setLinking(i)}>
                  <span className="ing-mark" aria-hidden="true">{STATE[i.state].mark}</span>
                  <span className="ing-text">{i.text}</span>
                </button>
              </li>
            ))}
          </ul>
          <p className="hint">Tryck på en rad för att koppla den till rätt vara.</p>
        </section>
        <section className="recipe-steps">
          <h2>Gör så här</h2>
          {recipe.steps.length === 0 ? <p className="hint">Inga steg inskrivna.</p> : (
            <ol>{recipe.steps.map((s, n) => <li key={n}>{s}</li>)}</ol>
          )}
          {recipe.source_url && !isKiosk && (
            <a className="hint" href={recipe.source_url} target="_blank" rel="noreferrer">Originalrecept</a>
          )}
        </section>
      </div>
      <div className="recipe-actions">
        <button className="btn" onClick={missingToList} disabled={missingCount === 0}>Lägg saknade på listan</button>
        <button className="btn btn-primary" onClick={() => setCooking(true)}>Vi lagade den</button>
      </div>
      {linking && (
        <LinkIngredientSheet
          recipeId={id}
          ingredient={linking}
          onClose={() => setLinking(null)}
          onDone={(r) => {
            setRecipe(r);
            setLinking(null);
            reload("recipes");
          }}
        />
      )}
      {cooking && <CookedSheet recipe={recipe} onClose={() => setCooking(false)} />}
    </article>
  );
}
