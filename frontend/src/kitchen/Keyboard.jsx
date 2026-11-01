// On-screen Swedish keyboard for the kiosk (the Pi has no reliable system keyboard).
// Keys use onPointerDown + preventDefault so the text field keeps focus.
import { useState } from "react";

const LETTERS = ["qwertyuiopå", "asdfghjklöä", "zxcvbnm-"];
const SYMBOLS = ["1234567890", ",.-/()%+&'", "!?:;\"#*="];

function Key({ label, aria, onPress, wide, className = "" }) {
  return (
    <button
      type="button"
      className={`osk-key ${wide ? "osk-wide" : ""} ${className}`}
      aria-label={aria || label}
      onPointerDown={(e) => {
        e.preventDefault();
        onPress();
      }}
      onClick={(e) => e.preventDefault()}
    >
      {label}
    </button>
  );
}

export default function Keyboard({ onKey, onBackspace, onDone, numeric = false }) {
  const [symbols, setSymbols] = useState(false);
  if (numeric) {
    return (
      <div className="osk osk-numeric" role="group" aria-label="Sifferknappar">
        {["123", "456", "789"].map((row) => (
          <div className="osk-row" key={row}>
            {[...row].map((c) => <Key key={c} label={c} onPress={() => onKey(c)} />)}
          </div>
        ))}
        <div className="osk-row">
          <Key label="⌫" aria="Radera" onPress={onBackspace} />
          <Key label="0" onPress={() => onKey("0")} />
          <Key label="Klar" onPress={onDone} className="osk-done" />
        </div>
      </div>
    );
  }
  const rows = symbols ? SYMBOLS : LETTERS;
  return (
    <div className="osk" role="group" aria-label="Tangentbord">
      {rows.map((row, i) => (
        <div className="osk-row" key={row}>
          {[...row].map((c) => <Key key={c} label={c} onPress={() => onKey(c)} />)}
          {i === 2 && <Key label="⌫" aria="Radera" onPress={onBackspace} wide />}
        </div>
      ))}
      <div className="osk-row">
        <Key label={symbols ? "abc" : "123"} aria={symbols ? "Bokstäver" : "Siffror och tecken"} onPress={() => setSymbols(!symbols)} wide />
        <Key label="mellanslag" aria="Mellanslag" onPress={() => onKey(" ")} className="osk-space" />
        <Key label="Klar" onPress={onDone} wide className="osk-done" />
      </div>
    </div>
  );
}
