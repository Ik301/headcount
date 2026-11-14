import { Link } from "react-router-dom";
import type { ClaimNarrative, ClaimResult } from "../api/types";
import { chartUrl } from "../api/client";
import { config } from "../config";
import { Icon } from "../components/Icons";
import { ci, countWord, fmtInt, handle, isoSec, lift, localStamp, pct, plural, postRef, windowLabel } from "../lib/format";
import { narrativeColor } from "../lib/narrativeColor";
import { useCopy } from "../lib/useCopy";

const MIN_MATCHES = 30; // src/config.py MIN_MATCHES; below this the API reports no shares

/** The reply-shaped result. Every number is read from the /claim JSON; nothing is recomputed
 *  except the "x times baseline" ratio, which uses the same rule as the reply text (>= 2x). */
export function ClaimResultView({ r, checkedAt }: { r: ClaimResult; checkedAt?: number }) {
  const [copied, copy] = useCopy();
  const narr = r.narratives ?? [];
  const enough = r.matched_posts >= MIN_MATCHES && narr.length > 0;
  const baseline = r.baseline_bot_share ?? narr[0]?.baseline_bot_share;
  const top = narr.length ? narr.reduce((a, b) => (b.bot_post_share > a.bot_post_share ? b : a)) : null;
  const link = `${window.location.origin}/claim/${encodeURIComponent(r.claim_id)}`;
  const png = chartUrl(r);
  const win = windowLabel(r.window?.from, r.window?.to);
  const live = r.scope === "live";

  const share = async () => {
    if (navigator.share && matchMedia("(pointer:coarse)").matches) {
      try {
        await navigator.share({ title: "Claim check", text: r.claim, url: link });
        return;
      } catch {
        /* user dismissed: fall back to copy */
      }
    }
    copy("link", link);
  };

  return (
    <section aria-labelledby="res-h">
      <div className="wrap result">
        <div className="query">
          <div>
            <q className="qtext">{r.claim}</q>
            <span className="src">
              {checkedAt ? `Checked ${localStamp(new Date(checkedAt))}` : "Saved check"} · <span className="mono">{r.claim_id}</span>
            </span>
          </div>
          <Link className="linkbtn" to="/">
            New check
          </Link>
        </div>

        <div className="r-grid">
          <div className="r-head">
            <h1 id="res-h">
              <Headline r={r} enough={enough} top={top} baseline={baseline} />
            </h1>
            <p className="r-meta">
              <span>
                <span className="mono">{fmtInt(r.matched_posts)}</span> matching posts
              </span>
              {enough && (
                <span>
                  <span className="mono">{narr.length}</span> {narr.length === 1 ? "narrative" : "narratives"}
                </span>
              )}
              <span>{live ? "Bluesky live search" : `Bluesky${win ? `, ${win}` : ""} (UTC)`}</span>
              {r.seconds != null && (
                <span>
                  checked in <span className="mono">{r.seconds < 10 ? r.seconds.toFixed(1) : Math.round(r.seconds)}</span> s
                </span>
              )}
            </p>
            <p className="nojudge">
              <Icon name="scale" />
              <span>
                <b>I don’t judge whether the claim is true.</b> This shows who is posting it and how.
              </span>
            </p>
          </div>

          <div className="actions">
            <div className="row">
              <button className="btn" type="button" onClick={share}>
                <Icon name="share" />
                <span>{copied === "link" ? "Link copied" : "Share link"}</span>
              </button>
              <button className="btn ghost" type="button" onClick={() => copy("text", (r.reply_text ?? "").trim() || link)} disabled={!r.reply_text}>
                <Icon name="copy" />
                <span>{copied === "text" ? "Text copied" : "Copy as text"}</span>
              </button>
            </div>
            <p className="copied" aria-live="polite">
              {copied === "link" && "Link copied. It opens this same check for anyone."}
              {copied === "text" && "Copied the text-message version of this answer."}
              {copied?.endsWith(":failed") && "Couldn’t reach the clipboard. Copy the address bar instead."}
            </p>
            <p className="side-links">
              {png && (
                <a href={png} target="_blank" rel="noreferrer">
                  <Icon name="chart" /> Chart image
                </a>
              )}
              <a href={`${config.apiBase}/join`} target="_blank" rel="noreferrer">
                <Icon name="msg" /> Get checks by text
              </a>
            </p>
          </div>

          {enough ? (
            <>
              <NarrativesBlock r={r} narr={narr} top={top} baseline={baseline} />
              <CommonBlock r={r} top={top} />
              <AmpBlock r={r} />
              {r.news && <NewsBlock r={r} />}
              <EvidenceBlock r={r} narr={narr} />
            </>
          ) : (
            <section className="blk narr">
              <h2>Not enough posts to measure</h2>
              <p className="reply">{r.reply_text || `I found ${plural(r.matched_posts, "Bluesky post")} making this claim, which isn’t enough to measure automation reliably (I need at least ${MIN_MATCHES}).`}</p>
              <p className="sub">Try a broader wording, or a claim about the Jensen Huang story from Nov 5 to 13.</p>
            </section>
          )}

          <div className="method">
            <p>
              Likely automated means an account’s automation score is 0.5 or higher, from its posting rhythm, age, repost share and coordination with other accounts. Intervals are
              95%, bootstrapped over accounts. A score is not proof of who runs an account.{" "}
              <Link to="/story?view=method">Method and validation</Link>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function ratio(n: ClaimNarrative, baseline?: number) {
  const b = n.baseline_bot_share ?? baseline;
  if (!b || n.bot_post_share < 2 * b) return null;
  return n.bot_post_share / b;
}

function Headline({ r, enough, top, baseline }: { r: ClaimResult; enough: boolean; top: ClaimNarrative | null; baseline?: number }) {
  if (!enough)
    return r.matched_posts === 0 ? <>No Bluesky posts we have make this claim.</> : <>Only {fmtInt(r.matched_posts)} matching posts, too few to measure automation.</>;
  if (!top || top.bot_post_share <= 0)
    return (
      <>
        <span className="n">{fmtInt(r.matched_posts)}</span> Bluesky posts make this claim. None of its narratives shows likely automated accounts at the default cutoff.
      </>
    );
  const x = ratio(top, baseline);
  return (
    <>
      <span className="n">{fmtInt(r.matched_posts)}</span> Bluesky posts make this claim. Likely automated accounts wrote <span className="sig n">{pct(top.bot_post_share)}</span> of those
      in “{top.label}”{x ? `, about ${x.toFixed(1)}× the story’s baseline` : ""}.
    </>
  );
}

function NarrativesBlock({ r, narr, top, baseline }: { r: ClaimResult; narr: ClaimNarrative[]; top: ClaimNarrative | null; baseline?: number }) {
  const max = Math.max(0.1, baseline ?? 0, ...narr.map((n) => n.bot_post_share_ci?.[1] ?? n.bot_post_share)) * 1.15;
  const pos = (v: number) => `${Math.min(100, (v / max) * 100)}%`;
  const word = countWord(narr.length);
  return (
    <section className="blk narr" aria-labelledby="narr-h">
      <h2 id="narr-h">{narr.length === 1 ? "One way people are telling it" : `${word} ways people are telling it`}</h2>
      <p className="sub">Share of all {fmtInt(r.matched_posts)} matching posts, then the share written by likely automated accounts.</p>
      <div className="stack" role="img" aria-label={narr.map((n) => `${n.label} ${pct(n.share_of_matches)}`).join(", ")}>
        {narr.map((n, i) => (
          <i key={n.id} style={{ flex: Math.max(n.share_of_matches, 0.004), background: narrativeColor(n.id, i) }} />
        ))}
      </div>
      <ul className="nrows">
        {narr.map((n, i) => {
          const isTop = top && n.id === top.id && top.bot_post_share > 0;
          const x = ratio(n, baseline);
          const [lo, hi] = n.bot_post_share_ci ?? [n.bot_post_share, n.bot_post_share];
          return (
            <li key={n.id} className={`nrow${isTop ? " top" : ""}`}>
              <div className="l1">
                <span className="sw" style={{ background: narrativeColor(n.id, i) }} />
                <span className="nm">
                  {n.label}
                  {isTop && <span className="flag">Highest automation</span>}
                </span>
                <span className="sh">
                  <b>{pct(n.share_of_matches)}</b>
                  {n.posts != null && <> · {plural(n.posts, "post")}</>}
                </span>
              </div>
              <div className="l2">
                <div className="track" aria-hidden="true">
                  <span className="band" style={{ left: pos(lo), width: `calc(${pos(hi)} - ${pos(lo)})` }} />
                  {baseline != null && <span className="base" style={{ left: pos(baseline) }} />}
                  <span className="pt" style={{ left: pos(n.bot_post_share) }} />
                </div>
                <span className="au-val">
                  <b>{pct(n.bot_post_share)}</b> {n.bot_post_share_ci && `(${ci(n.bot_post_share_ci)})`}
                  {x && <span className="xb">{x.toFixed(1)}× baseline</span>}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="legend">
        <span>
          <span className="k-band" />
          Likely automated, 95% interval
        </span>
        {baseline != null && (
          <span>
            <span className="k-base" />
            {pct(baseline)} across the whole story (baseline)
          </span>
        )}
      </div>
    </section>
  );
}

function CommonBlock({ r, top }: { r: ClaimResult; top: ClaimNarrative | null }) {
  const items = r.bot_commonalities ?? [];
  return (
    <section className="blk common" aria-labelledby="common-h">
      <h2 id="common-h">What the likely automated accounts have in common</h2>
      {items.length ? (
        <>
          <p className="sub">Observable signals among the likely automated accounts in these posts{top && top.bot_post_share > 0 ? `, most of them in “${top.label}”` : ""}.</p>
          <ul className="traits">
            {items.map((c, i) => (
              <li key={i}>
                <span className="k">
                  {fmtInt(c.accounts)}
                  <small>{c.accounts === 1 ? "account" : "accounts"}</small>
                </span>
                <span className="v">{c.signal}</span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="sub">Fewer than five likely automated accounts posted this claim, so there is no shared pattern to report.</p>
      )}
      <p className="aside-note">These are behaviors, not identities. We don’t say who runs an account.</p>
    </section>
  );
}

function AmpBlock({ r }: { r: ClaimResult }) {
  const a = r.amplifiers;
  const mix = a?.archetype_mix ?? [];
  const maxL = Math.max(3, ...mix.map((m) => m.lift_ci?.[1] ?? m.lift ?? 0)) * 1.1;
  const x = (v: number) => `${Math.min(100, (v / maxL) * 100)}%`;
  return (
    <section className="blk amp" aria-labelledby="amp-h">
      <h2 id="amp-h">Who amplifies them</h2>
      {a && a.n_humans > 0 && mix.length ? (
        <>
          <p className="sub">
            <span className="mono">{fmtInt(a.n_humans)}</span> real accounts reposted, quoted or liked posts from likely automated accounts. Grouped by behavior.
          </p>
          <ul className="arows">
            {mix.map((m) => (
              <li key={m.id} className="arow">
                <div className="l1">
                  <span className="nm">{m.label}</span>
                  <span className="sh">{pct(m.share)}</span>
                </div>
                {m.lift != null && (
                  <div className="l2">
                    <div className="ltrack" aria-hidden="true">
                      <span className="one" style={{ left: x(1) }} />
                      {m.lift_ci && <span className="band" style={{ left: x(m.lift_ci[0]), width: `calc(${x(m.lift_ci[1])} - ${x(m.lift_ci[0])})` }} />}
                      <span className="pt" style={{ left: x(m.lift) }} />
                    </div>
                    <span className={`lift${m.lift < 1 ? " low" : ""}`}>
                      <b>{lift(m.lift)}</b> {m.lift_ci && `(${m.lift_ci[0].toFixed(1)} to ${m.lift_ci[1].toFixed(1)})`}
                    </span>
                  </div>
                )}
              </li>
            ))}
          </ul>
          <div className="legend flush">
            <span>
              <span className="k-base" />1× = as likely as similar accounts to amplify
            </span>
            <span>Percent = share of the {fmtInt(a.n_humans)} amplifiers</span>
          </div>
        </>
      ) : (
        <p className="sub">
          {a?.note
            ? `No amplifier data for this check: ${a.note}.`
            : r.scope === "live"
              ? "Live checks don’t measure amplifiers yet; that needs the repost and like graph, which only the Jensen Huang corpus has."
              : "No real accounts were recorded reposting, quoting or liking the likely automated posts in these matches."}
        </p>
      )}
    </section>
  );
}

function NewsBlock({ r }: { r: ClaimResult }) {
  const n = r.news!;
  const heads = n.headlines ?? [];
  return (
    <section className="blk news" aria-labelledby="news-h">
      <h2 id="news-h">What accountable newsrooms report</h2>
      <p className="sub">Wire services and public broadcasters. Not neutral and not the truth, but edited and comparable.</p>
      {n.hedging_rate != null && (
        <p className="hedge">
          <b className="mono">{pct(n.hedging_rate)}</b> of these headlines hedge (“alleged”, “suspected”)
          {n.social_hedging_rate != null && (
            <>
              , against <b className="mono">{pct(n.social_hedging_rate)}</b> of the matching Bluesky posts
            </>
          )}
          .
        </p>
      )}
      {heads.length ? (
        <ul className="heads">
          {heads.slice(0, 6).map((h, i) => (
            <li key={i}>
              <span className="out">
                {h.outlet}
                {h.funding && <small> · {h.funding}</small>}
                {h.t && <time className="mono"> {isoSec(h.t).slice(0, 10)}</time>}
              </span>
              {h.url ? (
                <a href={h.url} target="_blank" rel="noreferrer">
                  {h.title}
                </a>
              ) : (
                <span>{h.title}</span>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="sub">No matching headlines from these outlets.</p>
      )}
    </section>
  );
}

function EvidenceBlock({ r, narr }: { r: ClaimResult; narr: ClaimNarrative[] }) {
  const nEx = narr.reduce((s, n) => s + (n.example_posts?.length ?? 0), 0);
  const nEv = narr.reduce((s, n) => s + (n.evidence?.length ?? 0), 0);
  const traces = (r.bot_commonalities ?? []).filter((c) => c.evidence?.length);
  return (
    <div className="evid">
      <details className="ev">
        <summary>
          <span>
            <span className="t">Evidence</span>
            <span className="c">
              {nEx} example posts and {nEv} matched posts with UTC timestamps{traces.length ? ", plus coordination traces" : ""}
            </span>
          </span>
          <Icon name="chev" />
        </summary>
        {traces.map((c, i) => (
          <div className="coord" key={i}>
            <p>
              <b>{c.signal}</b>
            </p>
            <ul className="trace">
              {c.evidence!.map((e, j) => (
                <li key={j}>
                  <time className="mono">{isoSec(e.t)}</time> <span className="mono ref">{postRef(e.post_uri)}</span> <span>{e.trace || e.note}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
        <div className="ev-narrs">
          {narr.map((n, i) => (
            <div key={n.id} className="ev-n">
              <h3>
                <span className="sw" style={{ background: narrativeColor(n.id, i) }} />
                {n.label}
              </h3>
              <ul className="posts">
                {(n.example_posts ?? []).map((p, j) => (
                  <li className="post" key={j}>
                    <div className="who">
                      {p.public_handle ? <span className="h">{handle(p.public_handle)}</span> : <span>a private account</span>}
                    </div>
                    <blockquote>{p.text}</blockquote>
                  </li>
                ))}
              </ul>
              {!!n.evidence?.length && (
                <ul className="trace">
                  {n.evidence.map((e, j) => (
                    <li key={j}>
                      <time className="mono">{isoSec(e.t)}</time> <span className="mono ref">{postRef(e.post_uri)}</span> <span>{e.note}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
        {r.reply_text && (
          <div className="as-text">
            <h3>As a text message</h3>
            <pre>{r.reply_text}</pre>
          </div>
        )}
        <p className="aside-note">Post refs are the last characters of each post’s ID. Account IDs are never shown for private accounts.</p>
      </details>
    </div>
  );
}
