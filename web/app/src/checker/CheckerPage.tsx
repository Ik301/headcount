import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { postClaim, ApiError } from "../api/client";
import { Icon } from "../components/Icons";
import { TopBar, Footer } from "../components/Shell";
import { RunProgress } from "./RunProgress";
import { CheckError } from "./CheckError";
import { NetworkGlobe } from "./NetworkGlobe";
import { seq } from "../lib/motion";

/** Example chips. The first is the deep demo story (corpus path); the rest exercise retrieval. */
export const EXAMPLES = [
  "Was Jensen Huang's mistress a Chinese spy?",
  "Did bots defend Jensen Huang?",
  "Is the Nvidia board forcing Huang out?",
];

type State = { kind: "idle" } | { kind: "running"; text: string; startedAt: number } | { kind: "error"; text: string; error: ApiError };

/**
 * Route "/": the claim checker. idle -> running (POST /claim, mode auto) -> navigates to /claim/:id
 * with the result in router state, so the URL in the address bar is the shareable link.
 */
export default function CheckerPage() {
  const [params] = useSearchParams();
  const [text, setText] = useState(params.get("q") ?? "");
  const [state, setState] = useState<State>({ kind: "idle" });
  const ctl = useRef<AbortController | null>(null);
  const navigate = useNavigate();

  useEffect(() => () => ctl.current?.abort(), []);
  useEffect(() => {
    document.title = "Headcount: how much of this story is real?";
  }, []);

  async function run(claim: string) {
    const q = claim.trim();
    if (!q) return;
    ctl.current?.abort();
    const c = new AbortController();
    ctl.current = c;
    setState({ kind: "running", text: q, startedAt: performance.now() });
    window.scrollTo(0, 0);
    try {
      const r = await postClaim(q, c.signal);
      if (c.signal.aborted) return;
      navigate(`/claim/${encodeURIComponent(r.claim_id)}`, { state: { result: r, checkedAt: Date.now() } });
    } catch (e) {
      if (c.signal.aborted) return;
      setState({ kind: "error", text: q, error: e instanceof ApiError ? e : new ApiError(String(e)) });
    }
  }

  function cancel() {
    ctl.current?.abort();
    setState({ kind: "idle" });
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    run(text);
  };

  return (
    <div className={`page checker${state.kind === "error" ? "" : " is-dark"}`}>
      <TopBar />
      <main>
        {state.kind !== "error" && (
          <div className="hero">
            <div className="hero-grid">
              <div className="hero-main">
        {state.kind === "idle" && (
          <section aria-labelledby="idle-h">
            <div className="wrap narrow idle">
              <h1 id="idle-h" className="h-rise">Who is pushing this story?</h1>
              <p className="lede in" style={seq(1, 120)}>
                Type a claim or a story. We find the Bluesky posts making it, group them into the different ways people tell it, and measure how much comes from likely automated
                accounts and which real people spread it.
              </p>

              <form className="field in" style={seq(2, 120)} autoComplete="off" onSubmit={onSubmit}>
                <label htmlFor="q" className="sr-only">
                  Claim or story to check
                </label>
                <textarea
                  id="q"
                  rows={3}
                  placeholder="A claim, a rumor or a headline"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      run(text);
                    }
                  }}
                />
                <div className="field-foot">
                  <span className="hint">
                    Public posts only<span className="kbd-hint"> · <kbd>Enter</kbd> to check</span>
                  </span>
                  <button className="btn" type="submit" disabled={!text.trim()}>
                    Check <Icon name="arrow" />
                  </button>
                </div>
              </form>

              <p className="try in" style={seq(3, 120)} id="try-l">
                Or try one
              </p>
              <div className="chips as-list" role="group" aria-labelledby="try-l">
                {EXAMPLES.map((ex, i) => (
                  <button key={ex} type="button" className="chip in-wipe" style={seq(4 + i, 120)} aria-pressed={text === ex} onClick={() => run(ex)}>
                    <span className="chip-n" aria-hidden="true">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    {ex}
                    <span className="chip-go" aria-hidden="true">
                      <Icon name="arrow" />
                    </span>
                  </button>
                ))}
              </div>

              <p className="scope-note in" style={seq(6, 240)}>
                Claims about the Jensen Huang week answer from our archive in seconds. Any other story runs a live Bluesky search and takes up to a minute.
              </p>

              <div className="never in" style={seq(6, 300)}>
                <p>
                  <Icon name="scale" />
                  <span>It measures who is posting a story. It never rules on whether the story is true.</span>
                </p>
                <p>
                  <Icon name="lock" />
                  <span>Private accounts are counted, never named. Only public accounts, like news organizations, appear by handle.</span>
                </p>
              </div>
            </div>
          </section>
        )}

        {state.kind === "running" && <RunProgress text={state.text} startedAt={state.startedAt} onCancel={cancel} />}
              </div>
              <div className="hero-side">
                <NetworkGlobe mode={state.kind === "running" ? "scan" : "idle"} />
              </div>
            </div>
          </div>
        )}

        {state.kind === "error" && (
          <CheckError
            text={state.text}
            error={state.error}
            onRetry={() => run(state.text)}
            onBack={() => setState({ kind: "idle" })}
          />
        )}
      </main>
      <Footer />
    </div>
  );
}
