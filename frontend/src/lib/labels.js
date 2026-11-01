export const TEMPS = [20, 30, 40, 50, 60, 90];
export const tempLabel = (t) => (t === 20 ? "Kallt" : `${t}°`);

export const COLORS = [
  { value: "white", label: "Vitt", swatch: "#f4f6fa" },
  { value: "light", label: "Ljust", swatch: "#e6d3ad" },
  { value: "dark", label: "Mörkt", swatch: "#46536d" },
  { value: "colored", label: "Kulört", swatch: "#e2574c" },
];
export const colorInfo = (v) => COLORS.find((c) => c.value === v) || COLORS[2];

export const SPINS = [0, 400, 600, 800, 1000, 1200, 1400];
export const spinLabel = (s) => (s === 0 ? "Ingen centrifug" : `${s} varv`);
export const spinShort = (s) => (s === 0 ? "Ingen" : `${s}`);

export const CARES = [
  { value: "normal", label: "Bomull" },
  { value: "synthetic", label: "Syntet" },
  { value: "delicate", label: "Fintvätt" },
  { value: "wool", label: "Ull" },
  { value: "hand", label: "Handtvätt" },
];
export const careLabel = (v) => CARES.find((c) => c.value === v)?.label ?? v;

export const DEFAULT_TAGS = { max_temp: 40, color: "dark", max_spin: 1200, care: "normal", tumble_dry: true };

export const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

// Swedish genitive: "Kikis", but "Magnus" stays "Magnus".
export const genitive = (name = "") => (/[sxz]$/i.test(name) ? name : `${name}s`);

// Mirrors backend grouping.GENTLENESS: a program must be at least as gentle as the garments need.
export const GENTLENESS = { normal: 0, synthetic: 1, delicate: 2, wool: 3, hand: 3 };
export const programAllowed = (garmentCare, programCare) => GENTLENESS[programCare] >= GENTLENESS[garmentCare];
