import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { isKiosk } from "./lib/router.js";
import "./styles.css";

if (isKiosk) document.documentElement.classList.add("kiosk");
createRoot(document.getElementById("root")).render(<App />);
