import type { Finding } from "../api/types";
import { Icon } from "../components/Icons";
import { useCopy } from "../lib/useCopy";

/** The quotable lead line of each view, from site_data.findings[view]. Falls back to a computed line. */
export function FindingBar({ finding, fallback, source, view }: { finding?: Finding; fallback?: string; source?: string; view: string }) {
  const [copied, copy] = useCopy();
  const text = finding?.text ?? fallback;
  if (!text) return null;
  const link = `${window.location.origin}/story?view=${view}`;
  return (
    <div className="finding">
      <p className="ftext">{text}</p>
      <div className="fside">
        {(finding?.source ?? source) && <span className="fsrc">{finding?.source ?? source}</span>}
        <button className={`btn${copied === "f" ? " done" : ""}`} onClick={() => copy("f", text)}>
          <Icon name="copy" />
          <span>{copied === "f" ? "Copied" : "Copy finding"}</span>
        </button>
        <button className={`btn${copied === "l" ? " done" : ""}`} onClick={() => copy("l", link)}>
          <Icon name="link" />
          <span>{copied === "l" ? "Copied" : "Copy link"}</span>
        </button>
      </div>
    </div>
  );
}
