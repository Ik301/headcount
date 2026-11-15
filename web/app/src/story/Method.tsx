import { fmtInt, pct } from "../lib/format";
import { FindingBar } from "./FindingBar";
import type { Model } from "./model";

function Curve({ data, label }: { data: Record<string, number>; label: string }) {
  const k = Object.keys(data).sort((a, b) => +a - +b);
  const v = k.map((x) => data[x]);
  const hiI = k.indexOf(k.includes("100") ? "100" : k.includes("20") ? "20" : k[Math.floor(k.length / 2)]);
  const w = 420, h = 104, l = 30, r = 12, t = 10, b = 26;
  const x = (i: number) => l + (k.length > 1 ? i / (k.length - 1) : 0.5) * (w - l - r);
  const y = (val: number) => t + (1 - val) * (h - t - b);
  return (
    <svg className="curve" viewBox={`0 0 ${w} ${h}`} role="img" aria-label={label}>
      {[0, 0.5, 1].map((g) => (
        <g key={g}>
          <line x1={l} x2={w - r} y1={y(g)} y2={y(g)} stroke="#EFECE5" />
          <text x={l - 6} y={y(g) + 4} textAnchor="end" className="ax">
            {g}
          </text>
        </g>
      ))}
      <polyline points={v.map((val, i) => `${x(i)},${y(val)}`).join(" ")} fill="none" stroke="#16181D" strokeWidth={1.6} />
      {v.map((val, i) => (
        <g key={i}>
          <circle cx={x(i)} cy={y(val)} r={i === hiI ? 4.5 : 2.6} fill={i === hiI ? "#16181D" : "#fff"} stroke="#16181D" strokeWidth={1.4} />
          <text x={x(i)} y={h - 8} textAnchor="middle" className="ax">
            {k[i]}
          </text>
        </g>
      ))}
      <text x={l + 6} y={t + 2} className="ax sans">
        {label}
      </text>
    </svg>
  );
}

const Check = () => (
  <svg viewBox="0 0 13 13" aria-hidden="true">
    <path d="M2 6.8l3 3L11 3" fill="none" stroke="#2F6F8F" strokeWidth="1.6" />
  </svg>
);

export function Method({ m }: { m: Model }) {
  const v = m.validation;
  const r100 = v.recall_at_k?.["100"];
  const rr20 = v.retrieval_recall_at_k?.["20"];
  const handAgree = v.hand_label_agreement ?? v.gold_accuracy;
  const llmAgree = v.narrative_llm_agreement;
  const rt = v.retrieval;
  const fallback = r100 != null ? `Scores are evidence, not verdicts. The model ranks ${pct(r100)} of held-out labeled bots in its top 100${handAgree != null ? `; narrative labels match hand labels ${pct(handAgree)} of the time` : ""}.` : undefined;
  return (
    <section className="view v-method" aria-label="Method and validation">
      <FindingBar finding={m.findings.method} fallback={fallback} source="Validation on held-out labeled data" view="method" />
      <div className="panel metrics">
        <div className="metric">
          <div className="v">{r100 != null ? r100.toFixed(2) : "·"}</div>
          <div className="k">bot model recall@100</div>
          <p>
            Of held-out accounts that label themselves as bots, the share the model ranks in its top 100 most likely automated.
            {v.baseline_recall_at_k?.["100"] != null && ` The baseline (posting rate alone) is ${v.baseline_recall_at_k["100"].toFixed(3)}.`}
          </p>
          {v.recall_at_k && Object.keys(v.recall_at_k).length > 1 && <Curve data={v.recall_at_k} label="recall@k, k = accounts reviewed" />}
        </div>
        {rr20 != null && <div className="metric">
          <div className="v">{rr20.toFixed(2)}</div>
          <div className="k">claim retrieval recall@20</div>
          <p>
            For {rt?.claims ? `the first ${rt.claims}` : ""} hand-checked claims, the share of truly matching posts found in the first 20 results the search returns, before narrative grouping
            {rt?.floor != null ? ` (similarity floor ${rt.floor.toFixed(2)})` : ""}.
            {rt?.recall_at_20_all != null && rt.claims_all ? ` On all ${rt.claims_all} claims: ${rt.recall_at_20_all.toFixed(2)}.` : ""}
          </p>
          {v.retrieval_recall_at_k && Object.keys(v.retrieval_recall_at_k).length > 1 && <Curve data={v.retrieval_recall_at_k} label="recall@k, k = results returned" />}
        </div>}
        {v.handcheck_precision?.n != null && (
          <div className="metric">
            <div className="v">
              {v.handcheck_precision.hits} of {v.handcheck_precision.n}
            </div>
            <div className="k">hand check</div>
            <p>Of the accounts the model scored highest that carry no bot label, the share that were clearly automated when checked by hand.</p>
          </div>
        )}
        {llmAgree != null && handAgree == null && (
          <div className="metric">
            <div className="v">{pct(llmAgree)}</div>
            <div className="k">classifier agreement with the language-model labels</div>
            <p>
              A language model labeled every post with its narrative. The fast classifier that serves new posts agrees with those labels on {pct(llmAgree)} of held-out posts
              {v.narrative_llm_agreement_n ? ` (${fmtInt(v.narrative_llm_agreement_n)})` : ""}. Agreement with hand labels: pending.
            </p>
          </div>
        )}
        {handAgree != null && <div className="metric">
          <div className="v">{pct(handAgree)}</div>
          <div className="k">narrative agreement with hand labels</div>
          <p>How often narrative labels agree with hand labels on a held-out set of posts from this story.{llmAgree != null ? ` The classifier agrees with the language-model labels on ${pct(llmAgree)}.` : ""}</p>
          {v.gold_by_narrative && (
            <div className="agree">
              {m.narratives
                .filter((n) => v.gold_by_narrative![n.id] != null)
                .map((n) => (
                  <div key={n.id} className="ag">
                    <span>
                      <i className="sw" style={{ background: n.color }} />
                      {n.label}
                    </span>
                    <div className="ab">
                      <i style={{ width: `${v.gold_by_narrative![n.id] * 100}%`, background: n.color }} />
                    </div>
                    <span className="mono">{pct(v.gold_by_narrative![n.id])}</span>
                  </div>
                ))}
            </div>
          )}
        </div>}
      </div>
      <div className="mcols">
        <div className="panel">
          <h2>How a score becomes a number</h2>
          <dl>
            <dt>Score</dt>
            <dd>0 to 1 per account, from posting rhythm, account age, text reuse, repost timing and follow ratios. Self-labels are training labels, never output.</dd>
            <dt>Default cutoff</dt>
            <dd>0.5. Every share is also shown at 0.3, 0.7 and 0.9.</dd>
            <dt>Interval</dt>
            <dd>95%, bootstrap over accounts, 1,000 resamples, seed 42.</dd>
            {m.baseline != null && (
              <>
                <dt>Baseline</dt>
                <dd>{pct(m.baseline, 1)} of all posts in the story come from likely automated accounts.</dd>
              </>
            )}
            <dt>Lift</dt>
            <dd>Amplifier rate against accounts matched on narrative, time window, reach, activity and follower bucket.</dd>
            <dt>Clusters</dt>
            <dd>Same text or same link, or reposts of the same post, within 60 seconds.</dd>
            {v.model_version && (
              <>
                <dt>Model</dt>
                <dd className="mono">{v.model_version}</dd>
              </>
            )}
          </dl>
        </div>
        <div className="panel">
          <h2>Data sources</h2>
          <dl>
            <dt>Platform</dt>
            <dd>Bluesky public API, no login, no private data.</dd>
            <dt>Window</dt>
            <dd className="mono">
              {new Date(m.start).toISOString().slice(0, 16).replace("T", " ")} to {new Date(m.start + m.hours * 3_600_000 - 60_000).toISOString().slice(5, 16).replace("T", " ")} UTC
            </dd>
            {m.totals.posts != null && (
              <>
                <dt>Posts</dt>
                <dd>
                  <span className="mono">{fmtInt(m.totals.posts)}</span> from keyword and link search
                </dd>
              </>
            )}
            {m.totals.accounts != null && (
              <>
                <dt>Accounts</dt>
                <dd>
                  <span className="mono">{fmtInt(m.totals.accounts)}</span> authors and engagers
                </dd>
              </>
            )}
            {m.totals.engagements != null && (
              <>
                <dt>Engagement</dt>
                <dd>
                  <span className="mono">{fmtInt(m.totals.engagements)}</span> likes, reposts and quotes
                </dd>
              </>
            )}
            {m.totals.selfLabeled != null && (
              <>
                <dt>Self-labels</dt>
                <dd>
                  <span className="mono">{fmtInt(m.totals.selfLabeled)}</span> accounts carry a bot label; counted apart from model scores
                </dd>
              </>
            )}
            {m.nodes.length > 0 && (
              <>
                <dt>Replay graph</dt>
                <dd>
                  <span className="mono">{fmtInt(m.nodes.length)}</span> accounts{m.graphNote ? `. ${m.graphNote}` : ", the highest-engagement accounts"}
                </dd>
              </>
            )}
            {m.news?.outlets?.length ? (
              <>
                <dt>News baseline</dt>
                <dd>{m.news.outlets.map((o) => o.name ?? o.source).join(", ")}</dd>
              </>
            ) : null}
          </dl>
        </div>
        <div className="panel">
          <h2>Privacy rules</h2>
          <ul className="rules">
            <li>
              <Check />
              Public accounts only, by handle<span>5,000+ followers, verified, news organizations, self-labeled bots.</span>
            </li>
            <li>
              <Check />
              Everyone else is counted, never listed<span>Evidence shows a hashed ref such as acct·3f9a, never an account ID.</span>
            </li>
            <li>
              <Check />
              “Likely automated”, never “bot”<span>For any account that has not labeled itself.</span>
            </li>
            <li>
              <Check />
              No ruling on truth, no attribution<span>We do not say whether a claim is true or who runs an account.</span>
            </li>
          </ul>
          {m.challengeCount > 0 && (
            <p className="muted mt8">
              Challenge set: {m.challengeCount} frozen accounts. <a href="/challenge">Try labeling them yourself</a>.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
