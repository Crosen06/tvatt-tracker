import { useEffect, useState } from "react";
import { CARES, COLORS, SPINS, TEMPS, spinLabel, tempLabel } from "../lib/labels.js";
import { resizeImage } from "../lib/resizeImage.js";
import { useStore } from "../lib/store.js";
import { CameraIcon } from "./Icons.jsx";
import TagPicker from "./TagPicker.jsx";

export default function GarmentForm({ initial, photoUrl, photoRequired, submitLabel, onSubmit, children }) {
  const { people } = useStore();
  const [values, setValues] = useState(initial);
  const [photo, setPhoto] = useState(null); // { blob, url }
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k) => (v) => setValues((s) => ({ ...s, [k]: v }));

  useEffect(() => () => photo && URL.revokeObjectURL(photo.url), [photo]);

  async function pickPhoto(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const blob = await resizeImage(file);
    setPhoto({ blob, url: URL.createObjectURL(blob) });
    setError(null);
  }

  async function submit(e) {
    e.preventDefault();
    if (photoRequired && !photo) return setError("Ta ett foto på plagget först.");
    if (!values.name.trim()) return setError("Skriv vad plagget heter, till exempel ”Svart hoodie”.");
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ ...values, name: values.name.trim() }, photo?.blob);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  const preview = photo?.url || photoUrl;
  return (
    <form className="admin-form" onSubmit={submit} noValidate>
      <label className={`photo-pick${preview ? " has-photo" : ""}`}>
        {preview && <img src={preview} alt="" />}
        <input type="file" accept="image/*" capture="environment" onChange={pickPhoto} aria-label="Ta foto" />
        <span className="photo-pick-label">
          <CameraIcon width={32} height={32} />
          {preview ? "Ta nytt foto" : "Ta foto på plagget"}
        </span>
      </label>

      <TagPicker
        label="Vems plagg?"
        options={people.map((p) => ({ value: p.id, label: p.name, accent: p.color }))}
        value={values.person_id}
        onChange={set("person_id")}
      />

      <label className="field">
        <span className="field-label">Namn</span>
        <input className="input" value={values.name} onChange={(e) => set("name")(e.target.value)} placeholder="Till exempel Svart hoodie" maxLength={60} autoComplete="off" />
      </label>

      <TagPicker label="Färg" options={COLORS} value={values.color} onChange={set("color")} />
      <TagPicker label="Högsta temperatur" options={TEMPS.map((t) => ({ value: t, label: tempLabel(t) }))} value={values.max_temp} onChange={set("max_temp")} />
      <TagPicker label="Högsta centrifug" options={SPINS.map((s) => ({ value: s, label: s === 0 ? "Ingen" : spinLabel(s) }))} value={values.max_spin} onChange={set("max_spin")} />
      <TagPicker label="Typ av tvätt" options={CARES} value={values.care} onChange={set("care")} />
      <TagPicker
        label="Tål torktumlare"
        options={[
          { value: true, label: "Ja" },
          { value: false, label: "Nej" },
        ]}
        value={values.tumble_dry}
        onChange={set("tumble_dry")}
      />

      {children}
      <div className="sticky-save">
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
          {busy ? "Sparar…" : submitLabel}
        </button>
      </div>
    </form>
  );
}
