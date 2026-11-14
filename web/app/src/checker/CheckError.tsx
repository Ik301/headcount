import { Link } from "react-router-dom";
import type { ApiError } from "../api/client";
import { config } from "../config";
import { Icon } from "../components/Icons";

/** Shown when the API is unreachable or answers with an error. Never a blank page (DEMO H8). */
export function CheckError({ text, error, onRetry, onBack }: { text?: string; error: ApiError; onRetry?: () => void; onBack?: () => void }) {
  const unreachable = error.kind === "network";
  const missing = error.status === 404;
  return (
    <section aria-labelledby="err-h">
      <div className="wrap narrow run">
        {text && (
          <div className="query">
            <div>
              <q className="qtext">{text}</q>
            </div>
          </div>
        )}
        <div className="run-head err">
          <h1 id="err-h">
            {missing ? "This check isn’t on the server anymore" : unreachable ? "The analysis service didn’t answer" : "That check didn’t finish"}
          </h1>
          <p>
            {missing
              ? "Checks are kept in memory, so a restart of the service clears old links. Run the claim again to get a fresh result."
              : unreachable
                ? `Nothing came back from ${config.apiBase}. The service may be restarting.`
                : error.message}
          </p>
        </div>
        <div className="err-actions">
          {onRetry && (
            <button className="btn" type="button" onClick={onRetry}>
              Try again
            </button>
          )}
          {onBack ? (
            <button className="btn ghost" type="button" onClick={onBack}>
              New check
            </button>
          ) : (
            <Link className="btn ghost" to="/">
              New check
            </Link>
          )}
          <Link className="btn ghost" to="/story">
            See the Jensen Huang story
          </Link>
        </div>
        <div className="never">
          <p>
            <Icon name="scale" />
            <span>When it runs, the check measures who is posting a claim and how. It never rules on whether the claim is true.</span>
          </p>
          <p>
            <Icon name="lock" />
            <span>Private accounts are counted, never named. Likely automated means a score of 0.5 or higher, shown with a 95% interval.</span>
          </p>
        </div>
      </div>
    </section>
  );
}
