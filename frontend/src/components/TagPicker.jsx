// A row of large single-choice buttons (radio group).
export default function TagPicker({ label, options, value, onChange }) {
  return (
    <div className="field">
      <span className="field-label" id={`lbl-${label}`}>
        {label}
      </span>
      <div className="options" role="radiogroup" aria-labelledby={`lbl-${label}`}>
        {options.map((o) => (
          <button
            type="button"
            key={String(o.value)}
            role="radio"
            aria-checked={value === o.value}
            className={`option${o.accent ? " option-person" : ""}`}
            style={o.accent ? { "--accent": o.accent } : undefined}
            onClick={() => onChange(o.value)}
          >
            {o.swatch && <span className="swatch" style={{ background: o.swatch }} />}
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}
