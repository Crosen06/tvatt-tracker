import { useState } from "react";
import { isKiosk, navigate } from "../lib/router.js";
import { setInBasket, useStore } from "../lib/store.js";
import EmptyState from "./EmptyState.jsx";
import GarmentCard from "./GarmentCard.jsx";
import { BasketIcon, CameraIcon } from "./Icons.jsx";

export default function PersonTab({ personId }) {
  const { people, garments } = useStore();
  const [filter, setFilter] = useState("all");
  const person = people.find((p) => p.id === personId);
  if (!person) return null;

  const mine = garments.filter((g) => g.person_id === person.id);
  const inBasket = mine.filter((g) => g.in_basket);
  const shown = filter === "basket" ? inBasket : mine;

  if (mine.length === 0) {
    return (
      <EmptyState
        icon={<CameraIcon width={40} height={40} />}
        title={`${person.name} har inga plagg än`}
        action={
          !isKiosk && (
            <button className="btn btn-primary" onClick={() => navigate("/admin/ny")}>
              Lägg till plagg
            </button>
          )
        }
      >
        {isKiosk
          ? "Öppna tvatt.local i mobilen, fota plagget och tagga det. Det dyker upp här direkt."
          : "Fota plagget och välj hur det ska tvättas."}
      </EmptyState>
    );
  }

  return (
    <section className="person-tab" style={{ "--accent": person.color }}>
      <div className="person-bar">
        <div className="segmented" role="tablist">
          <button role="tab" aria-selected={filter === "all"} onClick={() => setFilter("all")}>
            Alla plagg <span className="count">{mine.length}</span>
          </button>
          <button role="tab" aria-selected={filter === "basket"} onClick={() => setFilter("basket")}>
            I tvättkorgen <span className="count">{inBasket.length}</span>
          </button>
        </div>
        <p className="hint">Tryck på ett plagg när du lägger det i tvättkorgen.</p>
      </div>
      {shown.length === 0 ? (
        <EmptyState icon={<BasketIcon width={40} height={40} />} title="Inget av dina plagg ligger i tvättkorgen">
          Byt till Alla plagg och tryck på det du lägger i korgen.
        </EmptyState>
      ) : (
        <div className="garment-grid">
          {shown.map((g) => (
            <GarmentCard key={g.id} garment={g} accent={person.color} onToggle={(x) => setInBasket(x, !x.in_basket)} />
          ))}
        </div>
      )}
    </section>
  );
}
