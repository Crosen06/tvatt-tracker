export const CATEGORIES = ["Kyl", "Frys", "Skafferi", "Frukt & grönt", "Bröd", "Kryddor", "Dryck", "Hushåll"];

export const STATUSES = [
  { value: "in_stock", label: "Finns" },
  { value: "low", label: "Snart slut" },
  { value: "out", label: "Slut" },
];
export const statusName = (s) => STATUSES.find((x) => x.value === s)?.label ?? s;

// What a tile says about an item: "6 st" for counted items at home, otherwise the status.
export function statusLabel(item) {
  if (item.counted && item.count > 0 && item.status !== "out") {
    return item.status === "low" ? `${item.count} st, snart slut` : `${item.count} st`;
  }
  return statusName(item.status);
}

export const isHome = (item) => item.status === "in_stock" || item.status === "low";

export const capitalize = (s) => (s ? s[0].toLocaleUpperCase("sv") + s.slice(1) : s);
