import { useEffect, useState } from "react";
import { Icon } from "../components/Icons";

/* The API answers once, at the end, so these stages are the pipeline's order, advanced on a
 * typical schedule; the clock is real. The last stage stays active until the answer arrives. */
const STAGES = [
  { at: 0, lbl: "Searching posts", sub: "The corpus first, then Bluesky public search" },
  { at: 1.5, lbl: "Grouping into narratives", sub: "The different ways people tell it" },
  { at: 4, lbl: "Scoring accounts", sub: "Signs of automation in each account’s behavior" },
  { at: 10, lbl: "Finding amplifiers", sub: "Real accounts that spread automated posts" },
];

const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

export function RunProgress({ text, startedAt, onCancel }: { text: string; startedAt: number; onCancel: () => void }) {
  const [t, setT] = useState(0);
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      setT((performance.now() - startedAt) / 1000);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [startedAt]);

  const active = STAGES.reduce((acc, s, i) => (t >= s.at ? i : acc), 0);

  return (
    <section aria-labelledby="run-h">
      <div className="wrap narrow run">
        <div className="query">
          <div>
            <q className="qtext">{text}</q>
          </div>
          <button className="linkbtn" type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>

        <div className="run-head">
          <h1 id="run-h">Checking Bluesky</h1>
          <p>
            <span className="num">{clock(t)}</span> elapsed. Claims about the Jensen Huang week answer in seconds; other stories search live and take up to a minute.
          </p>
        </div>

        <ol className="steps">
          {STAGES.map((s, i) => {
            const cls = i < active ? "done" : i === active ? "active" : "";
            const next = STAGES[i + 1]?.at;
            const frac = i === active ? (next ? Math.min(1, (t - s.at) / (next - s.at)) : Math.min(0.92, 1 - Math.exp(-(t - s.at) / 20))) : 0;
            return (
              <li key={s.lbl} className={`step ${cls}`} aria-current={i === active ? "step" : undefined}>
                <span className="st">
                  <Icon name="check" />
                </span>
                <span>
                  <span className="lbl">{s.lbl}</span>
                  <span className="sub">{s.sub}</span>
                </span>
                <span className="t">{i < active ? "done" : i === active ? "working" : "waiting"}</span>
                <span className="meter">
                  <i style={{ width: `${frac * 100}%` }} />
                </span>
              </li>
            );
          })}
        </ol>

        <p className="run-foot">
          <Icon name="scale" />
          <span>This measures who is posting. It does not judge whether the claim is true.</span>
        </p>
      </div>
    </section>
  );
}
