// A text field that brings its own keyboard on the kiosk. On phones it is a normal input.
import { useRef, useState } from "react";
import { isKiosk } from "../lib/router.js";
import Keyboard from "./Keyboard.jsx";

export default function KioskInput({
  value, onChange, onSubmit, placeholder, label, numeric = false, keyboardOpen = false, maxLength = 60, autoFocus = false,
}) {
  const [focused, setFocused] = useState(false);
  const ref = useRef(null);
  const showKeyboard = isKiosk && (keyboardOpen || focused);

  return (
    <div className="kiosk-input">
      <input
        ref={ref}
        className="input"
        value={value}
        placeholder={placeholder}
        aria-label={label || placeholder}
        maxLength={maxLength}
        autoFocus={autoFocus && !isKiosk}
        inputMode={isKiosk ? "none" : numeric ? "numeric" : "text"}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && onSubmit) onSubmit();
        }}
      />
      {showKeyboard && (
        <Keyboard
          numeric={numeric}
          onKey={(c) => value.length < maxLength && onChange(value + c)}
          onBackspace={() => onChange(value.slice(0, -1))}
          onDone={() => (onSubmit ? onSubmit() : ref.current?.blur())}
        />
      )}
    </div>
  );
}
