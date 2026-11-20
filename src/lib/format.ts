const timeFormat = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const numberFormat = new Intl.NumberFormat("fr-FR");

export function formatTime(iso: string): string {
  return timeFormat.format(new Date(iso));
}

const NARROW_NO_BREAK_SPACE = / /g;

/** French grouping with a plain no-break space: the narrow one is missing from the bundled fonts. */
export function formatNumber(value: number): string {
  return numberFormat.format(value).replace(NARROW_NO_BREAK_SPACE, " ");
}

export function percent(done: number, total: number): number {
  return total <= 0 ? 0 : Math.min(100, Math.floor((done * 100) / total));
}

export function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}
