import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getSiteData } from "../api/client";
import type { ChallengeItem, SiteData } from "../api/types";
import { TopBar } from "../components/Shell";
import { fmtInt, handle, parseT } from "../lib/format";

/* Route "/challenge": "Spot the automation", ported from the approved mockup (web/mockups/challenge.html).
 * Data: site_data.json's `challenge` (the export copies data/sample/challenge.json and adds each public account's
 * profile and hour-of-day mix). The viewer labels an account, then sees the model's score and reasons; Isaac's hand
 * label is shown only for accounts he has labeled. Answers stay in this tab. */

const CUTOFF = 0.5; // src/config.py HEADLINE_THRESHOLD
type Call = "auto" | "person" | "skip";
type Phase = "card" | "reveal" | "final";

interface Acct {
  ref: string;
  handle: string | null;
  p: number | null;
  reasons: string[];
  hand: "automated" | "human" | null;
  posts: { t: Date | null; text: string; kind?: string; lang?: string; langName?: string; en?: string }[];
  profile: NonNullable<ChallengeItem["profile"]>;
}

const squeeze = (s: string | undefined) => (s ?? "").replace(/\n\s*\n+/g, "\n").trim();

function toAcct(c: ChallengeItem): Acct {
  const posts = (c.posts ?? [])
    .map((p) =>
      typeof p === "string"
        ? { t: null, text: p }
        : { t: parseT(p.t), text: p.text, kind: p.kind, lang: p.lang, langName: p.lang_name, en: p.text_en },
    )
    .map((p) => ({ ...p, text: squeeze(p.text), en: p.en ? squeeze(p.en) || undefined : undefined }))
    .filter((p) => p.text?.trim())
    .sort((a, b) => (b.t?.getTime() ?? 0) - (a.t?.getTime() ?? 0));
  const h = (c.hand_label ?? "").toLowerCase();
  return {
    ref: c.account_ref,
    handle: c.public_handle ?? null,
    p: typeof c.p_automated === "number" ? c.p_automated : null,
    reasons: c.reasons ?? [],
    hand: h === "automated" ? "automated" : h === "human" ? "human" : null,
    posts,
    profile: c.profile ?? {},
  };
}

/* ---------- small pieces ---------- */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const clock = (d: Date) => {
  const h = d.getUTCHours(), m = d.getUTCMinutes();
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
};
const day = (d: Date) => `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;
function gapWords(ms: number): string {
  const s = Math.round(ms / 1000);
  if (s < 60) return s <= 1 ? "the same second" : `${s} seconds earlier`;
  const m = Math.round(s / 60);
  if (m < 60) return m === 1 ? "1 minute earlier" : `${m} minutes earlier`;
  const h = Math.round(m / 60);
  if (h < 48) return h === 1 ? "1 hour earlier" : `${h} hours earlier`;
  return `${Math.round(h / 24)} days earlier`;
}

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
}

/** Deterministic identicon from the account ref (no photos: a face would say more than the behavior does). */
function Avatar({ seed }: { seed: string }) {
  const h0 = hash(seed);
  let bits = Math.imul(h0, 2654435761) >>> 0;
  const fg = ["#4A4F5A", "#6B707A", "#5B6270"][h0 % 3];
  const cells: JSX.Element[] = [];
  for (let y = 0; y < 5; y++)
    for (let x = 0; x < 3; x++) {
      const on = bits & 1;
      bits >>>= 1;
      if (!on) continue;
      cells.push(<rect key={`${x}-${y}`} x={4 + x * 6.4} y={4 + y * 6.4} width={6.4} height={6.4} />);
      if (x < 2) cells.push(<rect key={`m${x}-${y}`} x={4 + (4 - x) * 6.4} y={4 + y * 6.4} width={6.4} height={6.4} />);
    }
  return (
    <span className="c-av" aria-hidden="true">
      <svg viewBox="0 0 40 40">
        <rect width="40" height="40" fill="#EEF0F2" />
        <g fill={fg}>{cells}</g>
      </svg>
    </span>
  );
}

function Who({ a, meta }: { a: Acct; meta?: boolean }) {
  const pr = a.profile;
  return (
    <div className="c-who">
      <Avatar seed={a.ref} />
      <div className="c-who-t">
        {a.handle ? (
          <>
            <b>{handle(a.handle)}</b>
            <span className="c-sub">Public account</span>
          </>
        ) : (
          <>
            <b>A private account</b>
            <span className="c-ref">acct·{a.ref.slice(-4)}</span>
          </>
        )}
      </div>
      {meta && (
        <span className="c-meta">
          {pr.account_age_days != null && <>{ageWords(pr.account_age_days)} old</>}
          {pr.posts_per_day != null && (
            <>
              <br />
              {ppd(pr.posts_per_day)} posts a day
            </>
          )}
        </span>
      )}
    </div>
  );
}

const ageWords = (d: number) => (d < 60 ? `${d} days` : d < 730 ? `${Math.round(d / 30.4)} months` : `${(d / 365).toFixed(1).replace(/\.0$/, "")} years`);
const ppd = (x: number) => (x >= 10 ? fmtInt(x) : x.toFixed(1).replace(/\.0$/, ""));

function Stats({ a }: { a: Acct }) {
  const pr = a.profile;
  const age = pr.account_age_days;
  return (
    <dl className="c-stats">
      <div>
        <dt>Account age</dt>
        <dd>{age == null ? "·" : age < 60 ? <>{age}<small>days</small></> : age < 730 ? <>{Math.round(age / 30.4)}<small>months</small></> : <>{(age / 365).toFixed(1).replace(/\.0$/, "")}<small>years</small></>}</dd>
      </div>
      <div>
        <dt>Posts per day</dt>
        <dd>{pr.posts_per_day == null ? "·" : ppd(pr.posts_per_day)}</dd>
      </div>
      <div>
        <dt>Follows / followers</dt>
        <dd>
          {fmtInt(pr.follows)}
          <small>/ {fmtInt(pr.followers)}</small>
        </dd>
      </div>
    </dl>
  );
}

const ReplyIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M9 7 4 12l5 5" />
    <path d="M4 12h10a6 6 0 0 1 6 6v1" />
  </svg>
);
const QuoteIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4 5h16v11H9l-5 4z" />
  </svg>
);

function Posts({ a }: { a: Acct }) {
  const shown = a.posts.slice(0, 3);
  if (!shown.length) return null;
  return (
    <ul className="c-posts" aria-label={`${shown.length === 3 ? "Three" : shown.length === 2 ? "Two" : "One"} most recent posts`}>
      {shown.map((p, i) => {
        const prev = shown[i - 1];
        return (
          <li key={i}>
            {p.t && (
              <time dateTime={p.t.toISOString()}>
                {i === 0 || !prev?.t ? (
                  `${day(p.t)}, ${clock(p.t)} UTC`
                ) : (
                  <>
                    {clock(p.t)} <span className="c-gap">· {gapWords(prev.t.getTime() - p.t.getTime())}</span>
                  </>
                )}
              </time>
            )}
            {p.kind === "reply" && (
              <span className="c-rp">
                <ReplyIcon />
                Reply
              </span>
            )}
            {p.kind === "quote" && (
              <span className="c-rp">
                <QuoteIcon />
                Quote post
              </span>
            )}
            {p.en ? (
              <>
                <p className="c-pt" lang="en">{p.en}</p>
                <p className="c-tr">Translated from {p.langName ?? "another language"}</p>
                <p className="c-orig" lang={p.lang}>{p.text}</p>
              </>
            ) : (
              <p className="c-pt">{p.text}</p>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function Hours({ a }: { a: Acct }) {
  const hrs = a.profile.hours_utc;
  if (!hrs || hrs.length !== 24) return null;
  const max = Math.max(1, ...hrs);
  const quiet = hrs.filter((v) => v === 0).length;
  const n = a.profile.hours_posts ?? hrs.reduce((s, v) => s + v, 0);
  return (
    <div className="c-when">
      <div className="c-lab">
        <span>When it posts, by hour</span>
        <span>Last {fmtInt(n)} posts, UTC</span>
      </div>
      <div className="c-hours" role="img" aria-label={quiet ? `Posts in ${24 - quiet} of 24 hours; quiet for ${quiet}` : "Posts in all 24 hours, with no quiet hour"}>
        {hrs.map((v, i) => (
          <i key={i} style={{ opacity: v ? 0.2 + 0.8 * (v / max) : 0.06 }} />
        ))}
      </div>
      <div className="c-haxis" aria-hidden="true">
        <span>12 am</span>
        <span>6 am</span>
        <span>Noon</span>
        <span>6 pm</span>
        <span>12 am</span>
      </div>
    </div>
  );
}

function AccountCard({ a, i, n }: { a: Acct; i: number; n: number }) {
  return (
    <article className="c-acct c-full" aria-label={`Account ${i + 1} of ${n}`}>
      <Who a={a} />
      <Stats a={a} />
      <Posts a={a} />
      <Hours a={a} />
    </article>
  );
}

const callWords = (c: Call) => (c === "auto" ? "likely automated" : c === "person" ? "probably a person" : "skipped");
const modelCall = (p: number | null): Call | null => (p == null ? null : p >= CUTOFF ? "auto" : "person");

/* ---------- page ---------- */

export default function ChallengePage() {
  const [data, setData] = useState<SiteData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [i, setI] = useState(0);
  const [phase, setPhase] = useState<Phase>("card");
  const [calls, setCalls] = useState<Record<string, Call>>({});

  useEffect(() => {
    document.title = "Spot the automation";
    getSiteData().then(setData, (e) => setErr(e.message));
  }, []);

  const accts = useMemo(() => {
    const ch = data?.challenge;
    const list = Array.isArray(ch) ? ch : ch?.accounts ?? [];
    return list.map(toAcct);
  }, [data]);
  const r100 = data?.validation?.recall_at_k?.["100"];
  const a = accts[i];
  const n = accts.length;
  const labeled = accts.filter((x) => calls[x.ref]);
  const answered = labeled.filter((x) => calls[x.ref] !== "skip");

  const answer = useCallback(
    (c: Call) => {
      if (!a) return;
      setCalls((s) => ({ ...s, [a.ref]: c }));
      if (c === "skip") {
        setI((k) => (k + 1 < n ? k + 1 : k));
        if (i + 1 >= n) setPhase("final");
      } else setPhase("reveal");
      window.scrollTo({ top: 0 });
    },
    [a, i, n],
  );
  const next = useCallback(() => {
    if (i + 1 >= n) setPhase("final");
    else {
      setI(i + 1);
      setPhase("card");
    }
    window.scrollTo({ top: 0 });
  }, [i, n]);
  const resume = () => {
    const k = accts.findIndex((x) => !calls[x.ref]);
    if (k < 0) {
      setCalls({});
      setI(0);
    } else setI(k);
    setPhase("card");
    window.scrollTo({ top: 0 });
  };

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.repeat) return;
      const t = e.target as HTMLElement | null;
      if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
      const k = e.key.toLowerCase();
      if (phase === "card" && k === "a") answer("auto");
      else if (phase === "card" && k === "p") answer("person");
      else if (phase === "card" && k === "s") answer("skip");
      else if (phase === "reveal" && k === "n") next();
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [phase, answer, next]);

  if (err || !data || !n)
    return (
      <div className="page challenge">
        <TopBar />
        <main className="ch-empty">
          <h1>Spot the automation</h1>
          <p>{err ? `The challenge set didn’t load: ${err}` : !data ? "Loading the challenge set…" : "The export has no challenge accounts yet (data/sample/challenge.json)."}</p>
        </main>
      </div>
    );

  const done = labeled.length;
  const count = phase === "final" ? `${done} of ${n} labeled` : `${i + 1} of ${n}`;

  return (
    <div className="page challenge" data-state={phase}>
      <TopBar />
      <div className="c-app">
        <header className="c-top">
          <div className="c-row">
            <h1>Spot the automation</h1>
            <span className="c-count">{count}</span>
          </div>
          <div className="c-dots" aria-hidden="true">
            {accts.map((x, k) => (
              <i key={x.ref} className={calls[x.ref] ? "c-done" : phase !== "final" && k === i ? "c-now" : ""} />
            ))}
          </div>
          <p className="c-lede">{n} public accounts from the Jensen Huang story on Bluesky. Your answers stay in this browser tab.</p>
        </header>

        <main>
          {phase !== "final" && a && (
            <div className="c-play">
              <AccountCard a={a} i={i} n={n} />
              {phase === "card" ? <Decide key={`d${i}`} i={i} n={n} onAnswer={answer} /> : <Reveal key={`r${i}`} a={a} call={calls[a.ref]} r100={r100} last={i + 1 >= n} onNext={next} onStop={() => setPhase("final")} />}
            </div>
          )}
          {phase === "final" && <Final accts={labeled} answered={answered} calls={calls} left={n - done} onResume={resume} />}
        </main>
      </div>
    </div>
  );
}

function Decide({ i, n, onAnswer }: { i: number; n: number; onAnswer: (c: Call) => void }) {
  return (
    <section className="c-view" aria-label={`Your call on account ${i + 1} of ${n}`}>
      <div className="c-spacer" />
      <div className="c-decide">
        <h2 className="c-ask">Is this account likely automated?</h2>
        <p className="c-ask-sub">Look at its age, how often it posts and when.</p>
        <div className="c-choices">
          <button className="c-choice c-auto" type="button" onClick={() => onAnswer("auto")}>
            <span className="c-sw" aria-hidden="true" />
            Likely automated
            <kbd aria-hidden="true">A</kbd>
          </button>
          <button className="c-choice c-person" type="button" onClick={() => onAnswer("person")}>
            <span className="c-sw" aria-hidden="true" />
            Probably a person
            <kbd aria-hidden="true">P</kbd>
          </button>
        </div>
        <button className="c-skip" type="button" onClick={() => onAnswer("skip")}>
          Skip, I can’t tell
        </button>
      </div>
    </section>
  );
}

const Tick = ({ dark }: { dark?: boolean }) => (
  <svg viewBox="0 0 22 22" aria-hidden="true">
    <circle cx="11" cy="11" r="10" fill={dark ? "#16181D" : "none"} stroke="#16181D" strokeWidth={dark ? 0 : 1.5} />
    {dark ? <path d="m6.5 11.3 3 3 6-6.3" fill="none" stroke="#F7F5F0" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /> : <path d="M7 11h8" stroke="#16181D" strokeWidth="1.8" strokeLinecap="round" />}
  </svg>
);

function Reveal({ a, call, r100, last, onNext, onStop }: { a: Acct; call?: Call; r100?: number; last: boolean; onNext: () => void; onStop: () => void }) {
  const mc = modelCall(a.p);
  const agree = call && call !== "skip" && mc ? call === mc : null;
  return (
    <section className="c-view" aria-label="The model’s score for this account" aria-live="polite">
      <article className="c-acct c-mini">
        <Who a={a} meta />
      </article>

      <p className="c-agree">
        <Tick dark={agree === true} />
        <span>
          You said <b>{callWords(call ?? "skip")}</b>. {agree === true ? <b>The model agrees.</b> : agree === false ? <b>The model disagrees.</b> : null}
        </span>
      </p>

      {a.p != null && (
        <div className="c-score">
          <div className="c-head">
            <span className="c-big">{a.p.toFixed(2)}</span>
            <p>
              automation score, out of 1.
              <br />
              {CUTOFF} or higher counts as <b>likely automated</b>.
            </p>
          </div>
          <div className="c-scale" role="img" aria-label={`Score ${a.p.toFixed(2)} on a scale from 0 to 1, cutoff at ${CUTOFF}`}>
            <span className="c-cut" />
            <span className={`c-pt${a.p >= CUTOFF ? "" : " c-lo"}`} style={{ left: `${Math.min(100, Math.max(0, a.p * 100))}%` }} />
          </div>
          <div className="c-sax" aria-hidden="true">
            <span>0</span>
            <span>Cutoff {CUTOFF}</span>
            <span>1</span>
          </div>
          {!!a.reasons.length && (
            <ol className="c-why" aria-label={`Top ${a.reasons.length === 3 ? "three" : a.reasons.length} reasons`}>
              {a.reasons.slice(0, 3).map((r, k) => (
                <li key={k}>
                  <span className="c-k">{k + 1}</span>
                  <span>{r[0].toUpperCase() + r.slice(1)}.</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}

      {a.hand && (
        <p className="c-hand">
          <b>Our hand check:</b> {a.hand === "automated" ? "automated" : "a person"}. A person on our team read this account’s profile and posts.
          {a.p != null && (a.hand === "automated") !== (a.p >= CUTOFF) ? " The model and the hand check disagree here." : ""}
        </p>
      )}

      <p className="c-fine">
        The model can be wrong.
        {r100 != null && (
          <>
            {" "}
            On held-out accounts known to be automated, it ranks {Math.round(r100 * 100)}% of them in its top 100 (recall@100 {r100.toFixed(2)}).
          </>
        )}{" "}
        A score is a sign, not proof, and never says who runs an account.
      </p>

      <div className="c-actions">
        <button className="c-primary" type="button" onClick={onNext}>
          {last ? "See my results" : "Next account"}
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <path d="M3.5 8h9M8.5 4l4 4-4 4" />
          </svg>
          <kbd aria-hidden="true">N</kbd>
        </button>
        {!last && (
          <button className="c-secondary" type="button" onClick={onStop}>
            Stop and see my results
          </button>
        )}
      </div>
    </section>
  );
}

function Final({ accts, answered, calls, left, onResume }: { accts: Acct[]; answered: Acct[]; calls: Record<string, Call>; left: number; onResume: () => void }) {
  const agreed = answered.filter((a) => modelCall(a.p) === calls[a.ref]).length;
  const withHand = answered.filter((a) => a.hand);
  const handHits = withHand.filter((a) => (a.hand === "automated" ? "auto" : "person") === calls[a.ref]).length;
  const dis = answered.filter((a) => modelCall(a.p) !== calls[a.ref]);
  return (
    <section className="c-view c-final" aria-label="Your results">
      <div className="c-result">
        <h2>{answered.length ? `You agreed with the model on ${agreed} of ${answered.length}.` : "You skipped every account so far."}</h2>
        <p>
          {withHand.length === 1
            ? `One account you labeled has a hand check from our team, and your call ${handHits ? "matched it" : "didn’t match it"}. `
            : withHand.length > 1
              ? `${withHand.length} accounts you labeled have a hand check from our team; your call matched ${handHits} of them. `
              : ""}
          Where you and the model disagree is where a hand check matters most.
        </p>
      </div>

      {!!accts.length && (
        <ul className="c-recap">
          {accts.map((a) => {
            const c = calls[a.ref];
            const ok = c !== "skip" && modelCall(a.p) === c;
            return (
              <li key={a.ref}>
                <Avatar seed={a.ref} />
                <div>
                  <div className="c-nm">{a.handle ? handle(a.handle) : <span className="c-ref">acct·{a.ref.slice(-4)}</span>}</div>
                  <div className="c-calls">
                    You: {callWords(c)}
                    <br />
                    Model: <span className="c-m">{a.p != null ? a.p.toFixed(2) : "·"}</span>
                    {a.p != null && `, ${a.p >= CUTOFF ? "above" : "below"} cutoff`}
                    {a.hand && `. Hand check: ${a.hand === "automated" ? "automated" : "a person"}`}
                  </div>
                </div>
                {c === "skip" ? (
                  <span className="c-tag c-yes">Skipped</span>
                ) : ok ? (
                  <span className="c-tag c-yes">
                    <svg viewBox="0 0 12 12" aria-hidden="true">
                      <path d="m2.5 6.3 2.2 2.2 4.8-5" />
                    </svg>
                    Agreed
                  </span>
                ) : (
                  <span className="c-tag c-q">
                    <svg viewBox="0 0 12 12" aria-hidden="true">
                      <path d="M3 3l6 6M9 3l-6 6" />
                    </svg>
                    Disagreed
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {!!dis.length && (
        <div className="c-queue">
          <svg viewBox="0 0 18 18" aria-hidden="true">
            <circle cx="9" cy="9" r="7.3" />
            <path d="M9 8.2v4.3" />
            <path d="M9 5.6v.1" />
          </svg>
          <span>
            The model learned from accounts that label themselves as bots, mostly news and trend feeds, so it is surest about that kind of automation. {dis.length === 1 ? "Your disagreement" : `Your ${dis.length} disagreements`} {dis.length === 1 ? "is" : "are"} the kind of case we check by hand.
          </span>
        </div>
      )}

      <div className="c-actions">
        <button className="c-primary" type="button" onClick={onResume}>
          {left ? `Keep going, ${left} ${left === 1 ? "account" : "accounts"} left` : "Start over"}
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <path d="M3.5 8h9M8.5 4l4 4-4 4" />
          </svg>
        </button>
        <Link className="c-secondary" to="/">
          Check a claim of your own
        </Link>
      </div>
    </section>
  );
}
