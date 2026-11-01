// Bottom sheet used across the kitchen. full: takes the whole screen (for the on-screen keyboard).
export default function Sheet({ title, onClose, children, actions, full = false, className = "" }) {
  return (
    <div className="scrim" onClick={onClose}>
      <div
        className={`sheet ${full ? "sheet-full" : ""} ${className}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sheet-head">
          <h2 className="grow">{title}</h2>
          {actions}
        </div>
        {children}
      </div>
    </div>
  );
}
