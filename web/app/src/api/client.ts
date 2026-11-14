import { config } from "../config";
import type { ClaimResult, SiteData } from "./types";

export class ApiError extends Error {
  constructor(message: string, public status?: number, public kind: "network" | "http" | "timeout" | "shape" = "http") {
    super(message);
  }
}

async function request<T>(url: string, init?: RequestInit, timeoutMs = config.claimTimeoutMs, signal?: AbortSignal): Promise<T> {
  const ctl = new AbortController();
  const timer = window.setTimeout(() => ctl.abort("timeout"), timeoutMs);
  signal?.addEventListener("abort", () => ctl.abort("cancel"));
  let res: Response;
  try {
    res = await fetch(url, { ...init, signal: ctl.signal });
  } catch (e) {
    window.clearTimeout(timer);
    if (ctl.signal.aborted && ctl.signal.reason === "timeout") throw new ApiError("The check took longer than 90 seconds and was stopped.", undefined, "timeout");
    if (ctl.signal.aborted) throw new ApiError("Cancelled.", undefined, "network");
    throw new ApiError("Couldn't reach the analysis service.", undefined, "network");
  }
  window.clearTimeout(timer);
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const b = body as { error?: string; detail?: string } | null;
    throw new ApiError(b?.error || b?.detail || `The service answered ${res.status}.`, res.status, "http");
  }
  const b = body as { error?: string } | null;
  if (b && typeof b === "object" && b.error) throw new ApiError(b.error, res.status, "http");
  return body as T;
}

export function postClaim(text: string, signal?: AbortSignal): Promise<ClaimResult> {
  return request<ClaimResult>(
    `${config.apiBase}/claim`,
    { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text, mode: "auto" }) },
    config.claimTimeoutMs,
    signal,
  ).then(validateClaim);
}

export function getClaim(id: string, signal?: AbortSignal): Promise<ClaimResult> {
  return request<ClaimResult>(`${config.apiBase}/claim/${encodeURIComponent(id)}`, undefined, 20_000, signal).then(validateClaim);
}

export function getHealth(): Promise<{ ok: boolean; artifacts_loaded?: boolean; bot_model?: string }> {
  return request(`${config.apiBase}/health`, undefined, 5_000);
}

export function chartUrl(r: ClaimResult): string | null {
  if (!r.chart_png_url) return null;
  return /^https?:/.test(r.chart_png_url) ? r.chart_png_url : `${config.apiBase}${r.chart_png_url}`;
}

export async function getSiteData(): Promise<SiteData> {
  const res = await fetch(config.siteDataUrl, { cache: "no-cache" });
  if (!res.ok) throw new ApiError("site_data.json is missing.", res.status, "http");
  try {
    return (await res.json()) as SiteData;
  } catch {
    throw new ApiError("site_data.json is not valid JSON.", res.status, "shape");
  }
}

function validateClaim(r: ClaimResult): ClaimResult {
  if (!r || typeof r !== "object" || typeof r.matched_posts !== "number") throw new ApiError("The service sent an answer in an unexpected shape.", undefined, "shape");
  return { ...r, narratives: Array.isArray(r.narratives) ? r.narratives : [] };
}
