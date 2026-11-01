import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api.js";
import { closeScan, getState, toast, useStore } from "../lib/store.js";
import { beep } from "./beep.js";
import KioskInput from "./KioskInput.jsx";
import ScanResult from "./ScanResult.jsx";
import Sheet from "./Sheet.jsx";

const HEARTBEAT_MS = 30000;

function CodeEntrySheet({ onCode, onClose }) {
  const [code, setCode] = useState("");
  return (
    <Sheet title="Skriv streckkoden" full onClose={onClose} actions={<button className="btn btn-ghost" onClick={onClose}>Avbryt</button>}>
      <p className="hint">Siffrorna under strecken, 8 eller 13 stycken.</p>
      <KioskInput value={code} onChange={(v) => setCode(v.replace(/\D/g, ""))} onSubmit={() => code && onCode(code)} placeholder="Streckkod" numeric keyboardOpen maxLength={13} />
    </Sheet>
  );
}

export default function ScanSheet() {
  const { scan } = useStore();
  const [state, setState] = useState("starting"); // starting | ready | error
  const [error, setError] = useState(null);
  const [streamKey, setStreamKey] = useState(0);
  const [result, setResult] = useState(null);
  const [looking, setLooking] = useState(false);
  const [typing, setTyping] = useState(false);
  const firstSeq = useRef(getState().scan.seq);
  const ready = useRef(false);

  async function start() {
    setState("starting");
    setError(null);
    try {
      await api.post("/api/scan/start");
      ready.current = true;
      setState("ready");
      setStreamKey(Date.now());
    } catch (e) {
      ready.current = false;
      setState("error");
      setError(e.message);
    }
  }

  useEffect(() => {
    start();
    const t = setInterval(() => ready.current && api.post("/api/scan/start").catch(() => {}), HEARTBEAT_MS);
    return () => {
      clearInterval(t);
      api.post("/api/scan/stop").catch(() => {});
    };
  }, []);

  async function lookup(code) {
    setTyping(false);
    setLooking(true);
    try {
      setResult(await api.get(`/api/barcodes/${code}`));
    } catch (e) {
      toast(e.message);
    } finally {
      setLooking(false);
    }
  }

  useEffect(() => {
    if (scan.seq > firstSeq.current && scan.code) {
      firstSeq.current = scan.seq;
      beep();
      lookup(scan.code);
    }
  }, [scan.seq]);

  useEffect(() => {
    if (scan.error && state === "ready" && !scan.running) {
      ready.current = false;
      setState("error");
      setError(scan.error);
    }
  }, [scan.error, scan.running]);

  return (
    <div className="scan" role="dialog" aria-modal="true" aria-label="Skanna">
      <header className="scan-head">
        <h1 className="grow">Skanna</h1>
        <button className="btn" onClick={() => setTyping(true)}>Skriv koden</button>
        <button className="btn btn-primary" onClick={closeScan}>Klar</button>
      </header>
      <div className="scan-body">
        <div className="scan-preview">
          {state === "ready" && <img key={streamKey} src={`/api/scan/stream?k=${streamKey}`} alt="Kamerabild" />}
          {state === "ready" && <span className="scan-aim" aria-hidden="true" />}
          {state === "starting" && <p className="hint">Startar kameran…</p>}
          {state === "error" && (
            <div className="scan-error">
              <p className="error">{error}</p>
              <button className="btn" onClick={start}>Försök igen</button>
            </div>
          )}
        </div>
        <div className="scan-panel">
          {looking ? (
            <p className="hint">Letar upp varan…</p>
          ) : result ? (
            <ScanResult key={result.code} result={result} onResult={setResult} onDone={() => setResult(null)} />
          ) : (
            <div className="scan-idle">
              {state === "error" ? (
                <>
                  <p className="scan-idle-title">Skriv in koden i stället</p>
                  <p className="hint">Tryck på Skriv koden och skriv siffrorna under strecken.</p>
                </>
              ) : (
                <>
                  <p className="scan-idle-title">Håll streckkoden mot kameran</p>
                  <p className="hint">Det piper när koden är läst. Du kan skanna flera varor i rad.</p>
                </>
              )}
            </div>
          )}
        </div>
      </div>
      {typing && <CodeEntrySheet onCode={lookup} onClose={() => setTyping(false)} />}
    </div>
  );
}
