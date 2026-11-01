import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { isKiosk } from "./lib/router.js";
import "./styles.css";

// After a long idle period the Pi's screen is probably blanked. The tap that wakes it
// must not also press whatever button happens to be under the finger.
const IDLE_MS = 9 * 60 * 1000;

function swallowWakeTap() {
  let last = Date.now();
  let swallow = false;
  window.addEventListener(
    "pointerdown",
    (e) => {
      const now = Date.now();
      if (now - last > IDLE_MS) {
        swallow = true;
        e.preventDefault();
        e.stopPropagation();
      }
      last = now;
    },
    true,
  );
  window.addEventListener(
    "click",
    (e) => {
      if (swallow) {
        swallow = false;
        e.preventDefault();
        e.stopPropagation();
      }
    },
    true,
  );
}

if (isKiosk) {
  document.documentElement.classList.add("kiosk");
  swallowWakeTap();
}
createRoot(document.getElementById("root")).render(<App />);
