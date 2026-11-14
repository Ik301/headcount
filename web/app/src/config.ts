/**
 * Runtime config. Precedence (first wins):
 *   1. ?api=<url> on any page (saved to localStorage so it sticks for the session's links)
 *   2. localStorage "sbt.apiBase"
 *   3. VITE_API_BASE at build time (web/app/.env or the shell)
 *   4. http://127.0.0.1:8000
 * `?api=reset` clears the saved override.
 */
const DEFAULT_API = "http://127.0.0.1:8000";
const KEY = "sbt.apiBase";

function resolveApiBase(): string {
  try {
    const q = new URLSearchParams(window.location.search).get("api");
    if (q === "reset") localStorage.removeItem(KEY);
    else if (q) localStorage.setItem(KEY, q.replace(/\/+$/, ""));
    const saved = localStorage.getItem(KEY);
    if (saved) return saved;
  } catch {
    /* storage blocked: fall through */
  }
  const env = import.meta.env.VITE_API_BASE as string | undefined;
  return (env && env.trim() ? env : DEFAULT_API).replace(/\/+$/, "");
}

export const config = {
  apiBase: resolveApiBase(),
  /** Static dashboard data, served from web/public/site_data.json. */
  siteDataUrl: `${import.meta.env.BASE_URL}site_data.json`,
  /** Claim checks can take up to a minute on the live path. */
  claimTimeoutMs: 90_000,
};
