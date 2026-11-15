import { useEffect, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { getClaim, ApiError } from "../api/client";
import type { ClaimResult } from "../api/types";
import { TopBar, Footer } from "../components/Shell";
import { ClaimResultView } from "./ClaimResult";
import { CheckError } from "./CheckError";

/**
 * Route "/claim/:id": the link the text line sends. Uses the result handed over by the checker
 * (router state) when present, else GET {API_BASE}/claim/{id}.
 */
export default function ClaimPage() {
  const { id = "" } = useParams();
  const loc = useLocation();
  const handed = (loc.state as { result?: ClaimResult; checkedAt?: number } | null) ?? null;
  const [result, setResult] = useState<ClaimResult | null>(handed?.result?.claim_id === id ? handed.result : null);
  const [error, setError] = useState<ApiError | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (result?.claim_id === id) return;
    const c = new AbortController();
    setError(null);
    getClaim(id, c.signal)
      .then((r) => setResult(r))
      .catch((e) => !c.signal.aborted && setError(e instanceof ApiError ? e : new ApiError(String(e))));
    return () => c.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, tick]);

  useEffect(() => {
    if (result) document.title = `“${result.claim}” · Headcount`;
  }, [result]);

  return (
    <div className="page checker">
      <TopBar />
      <main>
        {result ? (
          <ClaimResultView r={result} checkedAt={handed?.result?.claim_id === id ? handed?.checkedAt : undefined} />
        ) : error ? (
          <CheckError error={error} onRetry={error.status === 404 ? undefined : () => setTick((t) => t + 1)} />
        ) : (
          <div className="wrap narrow run" aria-busy="true">
            <div className="run-head">
              <h1>Loading the check</h1>
              <p>
                Fetching check <span className="num">{id}</span>.
              </p>
            </div>
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}
