import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api.js";
import { closeScan, getState, reload, toast, useStore } from "../lib/store.js";
import { beep } from "./beep.js";
import ItemPickerSheet from "./ItemPickerSheet.jsx";
import KioskInput from "./KioskInput.jsx";
import LearnSheet from "./LearnSheet.jsx";
import ScanResult from "./ScanResult.jsx";
import Sheet from "./Sheet.jsx";
import VisionResult from "./VisionResult.jsx";

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
  const { scan, vision, visionStatus } = useStore();
  const [state, setState] = useState("starting"); // starting | ready | error
  const [error, setError] = useState(null);
  const [streamKey, setStreamKey] = useState(0);
  const [result, setResult] = useState(null);
  const [looking, setLooking] = useState(false);
  const [typing, setTyping] = useState(false);
  const [picking, setPicking] = useState(false); // choosing which item to learn
  const [learning, setLearning] = useState(null); // item being learned
  const firstSeq = useRef(getState().scan.seq);
  const visionSeq = useRef(getState().vision.seq);
  const busy = useRef(false);
  busy.current = Boolean(result || looking || typing || picking || learning);
  const canSee = visionStatus.available;
  const ready = useRef(false);
  const sawRunning = useRef(false);

  function lost(message) {
    ready.current = false;
    sawRunning.current = false;
    setState("error");
    setError(message || "Kameran slutade svara.");
  }

  async function start() {
    setState("starting");
    setError(null);
    try {
      await api.post("/api/scan/start");
      ready.current = true;
      setState("ready");
      setStreamKey(Date.now());
    } catch (e) {
      lost(e.message);
    }
  }

  useEffect(() => {
    start();
    // The heartbeat only keeps a running camera alive; if it has died the sheet shows the error.
    const t = setInterval(() => {
      if (ready.current) api.post("/api/scan/heartbeat").catch((e) => lost(e.message));
    }, HEARTBEAT_MS);
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
      if (looking || result?.code === scan.code) return; // same item still in front of the camera
      beep();
      lookup(scan.code);
    }
  }, [scan.seq]);

  // An automatic suggestion only shows when nothing else is on screen; a barcode always wins.
  useEffect(() => {
    if (vision.seq > visionSeq.current) {
      visionSeq.current = vision.seq;
      if (busy.current || !vision.matches.length) return;
      beep();
      setResult({ kind: "vision", ...vision });
    }
  }, [vision.seq]);

  async function identify() {
    setLooking(true);
    try {
      const r = await api.post("/api/vision/identify");
      setResult({ kind: "vision", ...r });
    } catch (e) {
      toast(e.message);
    } finally {
      setLooking(false);
    }
  }

  useEffect(() => {
    if (scan.running && ready.current) sawRunning.current = true;
    if (!scan.running && sawRunning.current && ready.current) lost(scan.error);
  }, [scan.running, scan.error]);

  function streamFailed() {
    // The MJPEG stream ended: check whether the camera is still running.
    if (ready.current) api.get("/api/scan/last").then((s) => !s.running && lost(s.error), () => {});
    reload("scan");
  }

  return (
    <div className="scan" role="dialog" aria-modal="true" aria-label="Skanna">
      <header className="scan-head">
        <h1 className="grow">Skanna</h1>
        {canSee && state === "ready" && <button className="btn" onClick={identify} disabled={looking}>Vad är det här?</button>}
        {canSee && state === "ready" && <button className="btn" onClick={() => setPicking(true)}>Lär in</button>}
        <button className="btn" onClick={() => setTyping(true)}>Skriv koden</button>
        <button className="btn btn-primary" onClick={closeScan}>Klar</button>
      </header>
      <div className="scan-body">
        <div className="scan-preview">
          {state === "ready" && <img key={streamKey} src={`/api/scan/stream?k=${streamKey}`} alt="Kamerabild" onError={streamFailed} />}
          {state === "ready" && !canSee && <span className="scan-aim" aria-hidden="true" />}
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
          ) : result?.kind === "vision" ? (
            <VisionResult key={result.token} result={result} onDone={() => setResult(null)} onLearn={canSee ? setLearning : null} />
          ) : result ? (
            <ScanResult key={result.code} result={result} onResult={setResult} onDone={() => setResult(null)} onLearn={canSee && state === "ready" ? setLearning : null} />
          ) : (
            <div className="scan-idle">
              {state === "error" ? (
                <>
                  <p className="scan-idle-title">Skriv in koden i stället</p>
                  <p className="hint">Tryck på Skriv koden och skriv siffrorna under strecken.</p>
                </>
              ) : (
                <>
                  <p className="scan-idle-title">{canSee ? "Håll upp varan mot kameran" : "Håll streckkoden mot kameran"}</p>
                  <p className="hint">
                    {canSee
                      ? "Visa streckkoden, eller håll varan stilla i mitten så känner appen igen den. Det piper när den vet vad det är."
                      : "Det piper när koden är läst. Du kan skanna flera varor i rad."}
                  </p>
                </>
              )}
            </div>
          )}
        </div>
      </div>
      {typing && <CodeEntrySheet onCode={lookup} onClose={() => setTyping(false)} />}
      {picking && (
        <ItemPickerSheet
          title="Vilken vara ska läras in?"
          allowNew
          onClose={() => setPicking(false)}
          onPick={(item) => {
            setPicking(false);
            setLearning(item);
          }}
        />
      )}
      {learning && <LearnSheet item={learning} onClose={() => setLearning(null)} />}
    </div>
  );
}
