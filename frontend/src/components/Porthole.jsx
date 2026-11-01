// The washing-machine door: a ring that fills as the wash progresses.
export default function Porthole({ size = 44, progress = 0, running = false, done = false, children }) {
  const stroke = Math.max(3, size * 0.09);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div className={`porthole${running ? " is-running" : ""}${done ? " is-done" : ""}`} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle className="porthole-track" cx={size / 2} cy={size / 2} r={r} strokeWidth={stroke} />
        <circle
          className="porthole-fill"
          cx={size / 2}
          cy={size / 2}
          r={r}
          strokeWidth={stroke}
          strokeDasharray={c}
          strokeDashoffset={c * (1 - progress)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="porthole-glass" style={{ inset: stroke * 1.9 }}>
        <span className="porthole-drum" />
        {children && <div className="porthole-content">{children}</div>}
      </div>
    </div>
  );
}
