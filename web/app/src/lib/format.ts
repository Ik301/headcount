/* Number, date and privacy formatting shared by every view. */

export const fmtInt = (n: number | null | undefined) => (n == null || !isFinite(n) ? "·" : Math.round(n).toLocaleString("en-US"));

/** 0.0912 -> "9%". Small non-zero shares keep one decimal so they don't read as 0. */
export function pct(x: number | null | undefined, digits?: number): string {
  if (x == null || !isFinite(x)) return "·";
  const v = x * 100;
  if (digits != null) return `${v.toFixed(digits)}%`;
  if (v > 0 && v < 1) return `${v.toFixed(1)}%`;
  return `${Math.round(v)}%`;
}

/** [0.06, 0.12] -> "6 to 12%" (the reply-text convention). */
export function ci(range?: [number, number] | null): string {
  if (!range || range.length < 2) return "";
  const [lo, hi] = range;
  const f = (x: number) => {
    const v = x * 100;
    return v > 0 && v < 1 ? v.toFixed(1) : String(Math.round(v));
  };
  return `${f(lo)} to ${f(hi)}%`;
}

export const lift = (x?: number | null) => (x == null || !isFinite(x) ? "·" : `${x.toFixed(1)}×`);

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function parseT(t?: string | null): Date | null {
  if (!t) return null;
  // Python sometimes emits 6-digit fractions or +00:00; Date handles both after trimming micros.
  const d = new Date(t.replace(/(\.\d{3})\d+/, "$1"));
  return isNaN(d.getTime()) ? null : d;
}

/** "Nov 5 to 13" style window, UTC. */
export function windowLabel(from?: string | null, to?: string | null): string {
  const a = parseT(from), b = parseT(to);
  if (!a || !b) return "";
  const am = MONTHS[a.getUTCMonth()], bm = MONTHS[b.getUTCMonth()];
  return am === bm ? `${am} ${a.getUTCDate()} to ${b.getUTCDate()}` : `${am} ${a.getUTCDate()} to ${bm} ${b.getUTCDate()}`;
}

/** ISO to the second, UTC: 2026-11-12T20:31:04Z */
export function isoSec(t?: string | null): string {
  const d = parseT(t);
  return d ? d.toISOString().replace(/\.\d{3}Z$/, "Z") : t || "";
}

export function utcLabel(d: Date): string {
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}

export function localStamp(d = new Date()): string {
  return d.toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" });
}

/* ---------- privacy ----------
 * Evidence post URIs are at://did:plc:<account>/app.bsky.feed.post/<rkey>. The DID identifies the
 * account, so it is never rendered or copied. We show a short post ref built from the rkey only,
 * and a handle only when the data marks the account public (public_handle). */

export function postRef(uri?: string): string {
  if (!uri) return "post";
  const rkey = uri.split("/").pop() || uri;
  return `post·${rkey.slice(-6)}`;
}

/** Hash-like short ref for an account id that is not public. Never derived visibly from a DID. */
export function acctRef(id: string): string {
  if (/^[0-9a-f]{8,}$/i.test(id)) return `acct·${id.slice(0, 4)}`;
  let h = 2166136261;
  for (let i = 0; i < id.length; i++) h = Math.imul(h ^ id.charCodeAt(i), 16777619);
  return `acct·${(h >>> 0).toString(16).slice(0, 4).padStart(4, "0")}`;
}

export const handle = (h?: string | null) => (h ? (h.startsWith("@") ? h : `@${h}`) : null);

export function plural(n: number, one: string, many = one + "s") {
  return `${fmtInt(n)} ${n === 1 ? one : many}`;
}

const WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"];
export const countWord = (n: number) => WORDS[n] ?? fmtInt(n);
