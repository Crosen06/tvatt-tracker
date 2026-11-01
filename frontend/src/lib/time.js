import { useEffect, useState } from "react";

export function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

export function remainingMs(wash, offsetMs, now = Date.now()) {
  if (!wash) return 0;
  return Date.parse(wash.ends_at) - (now + offsetMs);
}

export function progress(wash, offsetMs, now = Date.now()) {
  if (!wash) return 0;
  const total = Date.parse(wash.ends_at) - Date.parse(wash.started_at);
  if (total <= 0) return 1;
  return Math.min(1, Math.max(0, 1 - remainingMs(wash, offsetMs, now) / total));
}

export function formatRemaining(ms) {
  if (ms <= 0) return "Klar";
  const totalSec = Math.ceil(ms / 1000);
  if (totalSec < 60) return `${totalSec} s kvar`;
  const min = Math.ceil(totalSec / 60);
  if (min < 60) return `${min} min kvar`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? `${h} h ${m} min kvar` : `${h} h kvar`;
}

const clockFmt = new Intl.DateTimeFormat("sv-SE", { hour: "2-digit", minute: "2-digit" });
export const formatClock = (ms) => clockFmt.format(new Date(ms));
