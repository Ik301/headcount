import { seq } from "../../lib/motion";
import { useState, type ReactNode } from "react";
import { Icon } from "../../components/Icons";
import { countWord, fmtInt, handle } from "../../lib/format";
import { useCopy } from "../../lib/useCopy";
import type { DrawerContent } from "../Drawer";
import { archetypeDrawer, narrativeDrawer } from "../drawers";
import { AUTOMATED, HUMAN_MAX, type Model } from "../model";
import { CheckGrid, CutoffStrip, EstimateBar, HedgeBars, LiftRows, NarrativeRows, RankBars, RecallChart, Term, Waffle, useWidth } from "./charts";
import { against, oneIn, pc, range, timeLabel, type GuideData } from "./data";
import { ReplayFigure } from "./Replay";
import { VoiceSorter } from "../../checker/VoiceSorter";
import { Receipt } from "../../components/Receipt";

export interface ChapterProps {
  m: Model;
  g: GuideData;
  still: boolean;
  openDrawer: (c: DrawerContent) => void;
  explore: (view: string) => string;
}

export interface Chapter {
  id: string;
  title: string;
  /** Label in the chapter steps; the full title is the pager's. */
  short: string;
  render: (p: ChapterProps) => ReactNode;
}

/* ---------- shared pieces ---------- */

function Head({ h, children }: { h: ReactNode; children?: ReactNode }) {
  return (
    <header className="g-chead">
      <h1 className="g-h h-rise">{h}</h1>
      {children && <div className="g-dek in" style={seq(1, 120)}>{children}</div>}
    </header>
  );
}

function More({ summary, children, open }: { summary: string; children: ReactNode; open?: boolean }) {
  return (
    <details className="g-more" open={open}>
      <summary>
        <Icon name="chev" />
        {summary}
      </summary>
      <div className="g-more-body">{children}</div>
    </details>
  );
}

function Actions({ finding, explore, exploreLabel }: { finding?: string; explore?: string; exploreLabel?: string }) {
  const [copied, copy] = useCopy();
  return (
    <div className="g-actions">
      {finding && (
        <button className="g-link" onClick={() => copy("f", `${finding} (${window.location.href})`)}>
          <Icon name="copy" />
          {copied === "f" ? "Copied" : "Copy this finding"}
        </button>
      )}
      {explore && (
        <a className="g-link" href={explore}>
          <Icon name="chart" />
          {exploreLabel ?? "Explore the full data"}
        </a>
      )}
    </div>
  );
}

/** One line of sourcing under a chart (Bellingcat / Reuters): where the numbers come from and how many. */
function Source({ children }: { children: ReactNode }) {
  return (
    <p className="g-src">
      <span className="g-src-k">Source</span>
      <span>{children}</span>
    </p>
  );
}
const dot = " · ";

const subject = (title: string) => title.split(",")[0].trim();
const hoursWord = (h: number) => (h < 1 ? "less than an hour" : h < 1.5 ? "about an hour" : `${Math.round(h)} hours`);

/* ---------- 1 What happened ---------- */

function WhatHappened({ m, g, still, explore }: ChapterProps) {
  const days = Math.round(m.hours / 24);
  const prev = g.peak ? [...g.events].reverse().find((e) => e.h <= g.peak!.h) : undefined;
  return (
    <>
      <Head
        h={
          g.posts != null && g.accounts != null ? (
            <>
              In {countWord(days).toLowerCase()} days, {fmtInt(g.accounts)} {g.platform} accounts posted {fmtInt(g.posts)} times about {subject(g.title)}.
            </>
          ) : (
            subject(g.title)
          )
        }
      >
        <p>
          {g.peak && (
            <>
              The busiest hour was {timeLabel(new Date(m.start + g.peak.h * 3_600_000)).replace(/:\d\d UTC$/, ":00 UTC")} ({fmtInt(g.peak.posts)} posts)
              {prev && g.peak.h - prev.h < 48 ? <>, {hoursWord(g.peak.h - prev.h)} after “{prev.label}”</> : null}.{" "}
            </>
          )}
          Watch the week rebuild hour by hour. Each dot is an account the story turns on.
        </p>
      </Head>
      <ReplayFigure m={m} g={g} still={still} />
      <Source>
        {g.platform} public API, no login{dot}
        {g.posts != null && <>{fmtInt(g.posts)} posts</>}
        {g.engagements != null && <>, {fmtInt(g.engagements)} likes, reposts and quotes</>}
        {dot}
        {g.windowLabel}, {g.year}, UTC{dot}events from news reports, times as published
      </Source>
      <div className="g-after">
        <More summary="What the colors mean">
          <p>We only draw the accounts this story is about: the ones that look automated, the real people who passed their posts on, and well-known public accounts.</p>
          <p>
            <b className="g-sig">Likely automated</b> means our model gave the account a score of {AUTOMATED} or more out of 1 for posting like a machine. Chapter 2 explains the score.
          </p>
          <p>
            <b className="g-hum">Real accounts that passed posts on</b> score under {HUMAN_MAX} and liked, reposted or quoted a post from a likely automated account. They appear the moment they first did.
          </p>
          <p>
            <b>Public accounts</b> (news organizations, verified accounts, 5,000+ followers, self-labeled bots) are the only ones we name. Everyone else is counted, never listed.
          </p>
        </More>
        {m.graphMeta?.accounts_with_engagement != null && (
          <More summary="What's left out of the picture">
            <p>
              {fmtInt(m.graphMeta.accounts_with_engagement)} accounts liked, reposted or quoted a post in this story. Drawing all of them would hide the pattern, so the picture keeps every likely automated account that got engagement, the real accounts that engaged with them most, and the most-engaged public accounts.
            </p>
          </More>
        )}
        <Actions finding={g.findings.story} explore={explore("replay")} exploreLabel="Open the full replay, with every narrative" />
      </div>
    </>
  );
}

/* ---------- 2 How much was automated ---------- */

function HowMuch({ g }: ChapterProps) {
  const [ref] = useWidth<HTMLDivElement>(900);
  const b = g.baseline;
  if (!b) return <Head h="The export has no story-wide share of likely automated posts yet." />;
  const one = oneIn(b.share);
  const strip = b.strip;
  return (
    <>
      <Head h={one ? <>About {one} posts came from likely automated accounts.</> : <>{pc(b.share)} of posts came from likely automated accounts.</>}>
        <p>
          An account is <Term>likely automated</Term> when our model scores it {AUTOMATED} or higher on a scale from 0 to 1. The score reads how an account posts (how regular, how often, how repetitive), never what it says. A high score is a sign, not proof, and we never say who runs an account.
        </p>
      </Head>
      <figure className="g-fig g-split" ref={ref}>
        <div className="g-split-fig">
          <Waffle share={b.share} cols={10} />
          <figcaption className="g-cap">Each square is 1 in 100 posts. <span className="g-key-auto">Magenta</span>: posts from likely automated accounts.</figcaption>
        </div>
        <div className="g-interval">
          <p className="g-interval-text">
            Our best estimate is{" "}
            <Receipt
              title="Receipt · story-wide share"
              lines={[
                ["Source", `${g.platform} public API, no login`],
                ["Window", `${g.windowLabel}, ${g.year} (UTC)`],
                b.nPosts != null && ["Posts", fmtInt(b.nPosts)],
                b.nAccounts != null && ["Accounts", fmtInt(b.nAccounts)],
                ["Left out", "bridged fediverse accounts (counted separately)"],
                ["Counted as automated", `account score ≥ ${AUTOMATED}`],
                ["Estimate", pc(b.share)],
                b.ci && ["95% interval", range(b.ci)],
                ["Interval method", "1,000 bootstrap resamples over accounts"],
                g.modelVersion ? ["Model", <span className="mono">{g.modelVersion}</span>] : null,
              ]}
            >
              <b>{pc(b.share)}</b>
            </Receipt>
            {b.ci && (
              <>
                . The true share is most likely between {pc(b.ci[0])} and {pc(b.ci[1])}: that range is the <Term>interval</Term>. We give 95% intervals, worked out by recounting many times on resampled accounts.
              </>
            )}
          </p>
          <EstimateBar value={b.share} ci={b.ci} max={Math.max(0.1, (b.ci?.[1] ?? b.share) * 1.5)} label={`${pc(b.share)}, interval ${range(b.ci)}`} />
          {strip && (
            <div className="g-cuts-box">
              <p className="g-cuts-h">Does it depend on where we draw the line?</p>
              <p className="g-cuts-dek">
                The {AUTOMATED} cutoff is a choice, so here is the same share at four cutoffs.{" "}
                {strip["0.9"] != null && strip["0.3"] != null && (
                  <>
                    Even at a strict 0.9 it is {pc(strip["0.9"])}; at a loose 0.3 it is {pc(strip["0.3"])}.
                  </>
                )}
              </p>
              <CutoffStrip strip={strip} current={String(AUTOMATED)} />
            </div>
          )}
        </div>
      </figure>
      <Source>
        {b.nPosts != null ? <>{fmtInt(b.nPosts)} posts</> : <>All story posts</>}
        {b.nAccounts != null && <> from {fmtInt(b.nAccounts)} accounts</>}, bridged fediverse accounts counted separately{dot}score cutoff {AUTOMATED}
        {dot}interval: 1,000 bootstrap resamples over accounts
        {g.modelVersion && (
          <>
            {dot}model <span className="mono">{g.modelVersion}</span>
          </>
        )}
      </Source>
      <div className="g-after">
        {b.accountShare != null && (
          <More summary="Why count posts and not accounts?">
            <p>
              Likely automated accounts are only {pc(b.accountShare)} of accounts, but they wrote {pc(b.share)} of posts, because they post far more often than people do. Counting posts measures how much of what readers saw was automated.
            </p>
          </More>
        )}
        <Actions finding={g.findings.story} />
      </div>
    </>
  );
}

/* ---------- 3 Where the automation was ---------- */

function Where({ m, g, openDrawer, explore }: ChapterProps) {
  const [removed, setRemoved] = useState(false);
  const N = g.narr;
  if (N.length < 2) return <Head h="The export has no narrative breakdown yet." />;
  const top = N[0], low = N[N.length - 1];
  const base = g.baseline?.share;
  const d = g.defend;
  const dv = d && base != null ? against(d.ci, base) : null;
  const topVs = base != null ? against(top.ci, base) : null;
  const newsy = N.slice(0, 3).every((n) => n.side === "neutral_news");
  const wapo = g.events.find((e) => /washington post/i.test(e.label)) || g.findings.wapo;
  const headline =
    newsy && d && dv && dv !== "above" ? (
      <>
        Posts relaying the news had the highest point estimates, up to {pc(top.bot)}
        {topVs === "above" ? "" : " (suggestive: the interval overlaps the story-wide share)"}. Posts defending Huang were no higher than usual.
      </>
    ) : (
      <>
        Likely automated accounts wrote {pc(top.bot)} of “{top.label}” posts, and {pc(low.bot)} of “{low.label}” posts.
      </>
    );
  const ranked = N.filter((n) => n.rank != null || n.volumeShare != null);
  const moved = ranked.filter((n) => n.rank != null && n.rankWithout != null && n.rank !== n.rankWithout);
  const notes: Record<string, string> = {};
  if (d && wapo) notes[d.id] = "where the Post's “online bots” claim would show";
  return (
    <>
      <Head h={headline}>
        <p>
          A <Term>narrative</Term> is one way of telling the story, like the spy plot or the jokes. A language model sorted every post into one of {countWord(N.length).toLowerCase()}.
          {d && dv && base != null && wapo && (
            <>
              {" "}
              The Washington Post reported “online bots” defending Huang on X. On {g.platform}, {pc(d.bot)} of posts defending him came from likely automated accounts, {dv === "same" ? "not clearly different from" : dv === "below" ? "below" : "above"} the {pc(base)} across the whole story.
            </>
          )}
        </p>
      </Head>
      <figure className="g-fig">
        <NarrativeRows narr={N} baseline={base} baselineCi={g.baseline?.ci} note={notes} />
        <figcaption className="g-cap">
          Share of each narrative’s posts that came from likely automated accounts. Dot: best estimate. Bar: 95% interval. Dashed line: the whole story.
          {g.unassigned && g.unassigned.posts > 0 && <> {fmtInt(g.unassigned.posts)} posts that fit no narrative (bare links, trend lists) are left out.</>}
        </figcaption>
      </figure>
      <Source>
        {fmtInt(N.reduce((t, n) => t + n.posts, 0))} posts in {countWord(N.length).toLowerCase()} narratives, each post labeled by a language model{dot}smallest: “{[...N].sort((a, b) => a.posts - b.posts)[0].label}”, {fmtInt(Math.min(...N.map((n) => n.posts)))} posts{dot}same score cutoff and intervals as chapter 2
      </Source>
      <div className="g-sorter">
        <VoiceSorter
          subject="story"
          matched={N.reduce((t, n) => t + n.posts, 0)}
          narr={N.map((n) => ({ id: n.id, label: n.label, posts: n.posts, share_of_matches: n.share, bot_post_share: n.bot, bot_post_share_ci: n.ci }))}
        />
      </div>
      {ranked.length > 1 && (
        <section className="g-sub" aria-labelledby="g-without">
          <div className="g-sub-head">
            <h2 id="g-without">Count the likes and reposts too. Does the order change?</h2>
            <button className="g-switch" role="switch" aria-checked={removed} onClick={() => setRemoved(!removed)}>
              <span className="g-switch-track" aria-hidden="true" />
              Remove likely automated accounts
            </button>
          </div>
          <p className="g-sub-dek">
            The sorter above counts posts. Here each narrative’s share of the conversation also counts likes, reposts and quotes, and removing likely automated accounts takes out their engagement as well.{" "}
            {removed && (
              <b>
                {moved.length === 0
                  ? "Every narrative keeps its place."
                  : moved
                      .map((n) => `“${n.label}” moves from ${n.rank} to ${n.rankWithout}`)
                      .slice(0, 2)
                      .join("; ") + "."}
              </b>
            )}
          </p>
          <RankBars narr={ranked} removed={removed} />
        </section>
      )}
      <div className="g-after">
        {N.some((n) => n.strip) && (
          <More summary="Does the order depend on the cutoff?">
            <p>The same share at four score cutoffs. The order of the narratives is the thing to watch.</p>
            <table className="g-table">
              <thead>
                <tr>
                  <th>Narrative</th>
                  {Object.keys(N[0].strip ?? {})
                    .sort()
                    .map((k) => (
                      <th key={k} className="r">
                        {k}+
                      </th>
                    ))}
                </tr>
              </thead>
              <tbody>
                {N.map((n) => (
                  <tr key={n.id}>
                    <td>{n.label}</td>
                    {Object.keys(N[0].strip ?? {})
                      .sort()
                      .map((k) => (
                        <td key={k} className="r">
                          {pc(n.strip?.[k])}
                        </td>
                      ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </More>
        )}
        <More summary="See the posts behind each number">
          <ul className="g-openers">
            {N.map((n) => (
              <li key={n.id}>
                <button className="g-link" onClick={() => openDrawer(narrativeDrawer(m, n, "Chapter 3, where the automation was"))}>
                  {n.label}
                  <span className="g-muted"> · {fmtInt(n.posts)} posts</span>
                </button>
              </li>
            ))}
          </ul>
        </More>
        <Actions finding={g.findings.spread ?? g.findings.wapo} explore={explore("nobots")} exploreLabel="Open the full narrative table" />
      </div>
    </>
  );
}

/* ---------- 4 Newsrooms vs Bluesky ---------- */

function Newsrooms({ g }: ChapterProps) {
  const h = g.hedge;
  const news = h.rows.find((r) => r.tone === "news");
  const social = h.rows.find((r) => r.id === "social");
  const link = h.rows.find((r) => r.id === "link");
  const own = h.rows.find((r) => r.id === "own");
  if (!news || (!social && !link)) return <Head h="The export has no news comparison yet." />;
  const retelling = link && own && own.share < link.share && Math.abs(link.share - news.share) < 0.1;
  const terms = (h.terms.length ? h.terms : ["alleged", "suspected", "reportedly", "claims"]).map((t) => t.replace(/\(s\)$/, "s"));
  // the words people know first, then the rest of the list (inflections like "allegedly" add nothing to the sentence)
  const shown = [...["alleged", "suspected", "reportedly", "claims"].filter((t) => terms.includes(t)), ...terms].filter((t, i, a) => a.indexOf(t) === i);
  const names = h.outlets.map((o) => o.name);
  const hedgeRe = new RegExp(`\\b(${terms.map((t) => t.toLowerCase().replace(/[^a-z ]/g, "").trim().replace(/\s+/g, "\\s+")).filter(Boolean).join("|")})\\w*`, "gi");
  return (
    <>
      <Head
        h={
          retelling ? (
            <>Newsrooms hedged the spy claim. On {g.platform}, the caution survived the share button and disappeared in the retelling.</>
          ) : (
            <>
              {pc(news.share)} of newsroom headlines about the spy claim hedged. {pc(social!.share)} of {g.platform} posts making the claim did.
            </>
          )
        }
      >
        <p>
          To <Term>hedge</Term> is to mark a claim as unproven, with words like {shown.slice(0, 4).map((t, i) => <span key={t}>{i ? ", " : ""}“{t}”</span>)}. The newsrooms are {names.length ? `${countWord(names.length).toLowerCase()} wire services and public broadcasters (${names.join(", ")})` : "wire services and public broadcasters"}. They are edited and accountable, not neutral, and not the truth.
        </p>
      </Head>
      <figure className="g-fig">
        <HedgeBars rows={h.rows} />
        <figcaption className="g-cap">Share of headlines or posts about the spy claim that hedge. Thin lines: 95% intervals (newsroom interval resamples outlets, {g.platform} interval resamples accounts).</figcaption>
      </figure>
      <Source>
        {news.n != null && <>{fmtInt(news.n)} headlines</>}
        {h.outlets.length > 0 && <> from {countWord(h.outlets.length).toLowerCase()} outlets</>}, via their RSS feeds and Google News RSS search{dot}
        {h.rows
          .filter((r) => r.tone === "social" && r.n != null)
          .map((r) => fmtInt(r.n!))
          .join(" + ")}{" "}
        {g.platform} posts{dot}a post or headline hedges if it uses any of {terms.length} words, matched the same way on both sides
      </Source>
      <div className="g-after">
        {!!h.examples.length && (
          <More summary="Headlines we counted">
            <ul className="g-heads">
              {h.examples.slice(0, 8).map((e, i) => (
                <li key={i}>
                  <q>{e.hedged ? highlight(e.title, hedgeRe) : e.title}</q>
                  <span className="g-muted">
                    {e.source}
                    {e.published ? `, ${timeLabel(new Date(e.published)).split(",")[0]}` : ""} · {e.hedged ? "hedged" : "not hedged"}
                  </span>
                </li>
              ))}
            </ul>
          </More>
        )}
        {!!h.outlets.length && (
          <More summary="Who the newsrooms are, and who funds them">
            <table className="g-table">
              <thead>
                <tr>
                  <th>Outlet</th>
                  <th>Funding</th>
                  <th className="r">Spy headlines hedged</th>
                </tr>
              </thead>
              <tbody>
                {h.outlets.map((o) => (
                  <tr key={o.name}>
                    <td>{o.name}</td>
                    <td className="g-muted">{o.funding}</td>
                    <td className="r">{o.spy != null ? `${o.hedged ?? 0} of ${o.spy}` : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </More>
        )}
        <Actions finding={g.findings.news} />
      </div>
    </>
  );
}

function highlight(text: string, re: RegExp): ReactNode {
  const parts: ReactNode[] = [];
  let last = 0;
  text.replace(re, (mt, _g, off: number) => {
    parts.push(text.slice(last, off), <mark key={off}>{mt}</mark>);
    last = off + mt.length;
    return mt;
  });
  parts.push(text.slice(last));
  return parts;
}

/* ---------- 5 Who spread it ---------- */

function WhoSpread({ m, g, openDrawer, explore }: ChapterProps) {
  const A = g.arch;
  if (!A.length) return <Head h="The export has no amplifier groups yet." />;
  const sig = A.filter((a) => a.ci && a.ci[0] > 1).sort((a, b) => b.lift - a.lift);
  const low = A.filter((a) => a.ci && a.ci[1] < 1).sort((a, b) => a.lift - b.lift);
  const autoCut = g.ampDefinition?.match(/>=\s*([\d.]+)/)?.[1];
  const example = A.find((a) => /repost/i.test(a.label)) ?? A[0];
  return (
    <>
      <Head
        h={
          sig.length ? (
            <>
              Real accounts in the group “{sig[0].label}” were {sig[0].lift.toFixed(1)} times as likely as others to pass on likely automated posts.
            </>
          ) : (
            <>No kind of real account stood out for passing on likely automated posts.</>
          )
        }
      >
        <p>
          {g.matched ? (
            <>
              {fmtInt(g.matched.amplifiers)} real accounts <Term>amplified</Term> likely automated accounts, meaning they liked, reposted or quoted their posts. We paired {fmtInt(g.matched.matched)} of them with a similar account that saw the same story but engaged only with people: same narrative, same six hours, similar reach, activity and followers. Then we grouped all {fmtInt(g.matched.accounts)} by how they behave into {countWord(A.length).toLowerCase()} <Term>archetypes</Term>, such as “{example.label.toLowerCase()}”, and compared how often each group amplified.
            </>
          ) : (
            <>
              We took the {g.humans != null ? fmtInt(g.humans) : ""} real accounts that engaged with the story and grouped them by how they behave into {countWord(A.length).toLowerCase()} <Term>archetypes</Term>, such as “{example.label.toLowerCase()}”. Then we compared how often each group <Term>amplified</Term> likely automated accounts, meaning it liked, reposted or quoted their posts.
            </>
          )}
          {!sig.length && !low.length && " Every group’s interval crosses “no difference”, so we can’t say any one type of person spreads automation more than another."}
          {!sig.length && low.length > 0 && (
            <>
              {" "}No group was clearly more likely to pass them on. {low.length === 1 ? "One was less likely" : `${countWord(low.length)} were less likely`}: “{low[0].label.toLowerCase()}”, {low[0].lift.toFixed(2)}× ({low[0].ci![0].toFixed(2)} to {low[0].ci![1].toFixed(2)}). Groups shift between model runs, so treat this as exploratory.
            </>
          )}
        </p>
      </Head>
      <figure className="g-fig">
        <LiftRows arch={A} />
        <figcaption className="g-cap">
          How often each group amplified likely automated accounts, compared with {g.matched ? "the matched sample" : "all the real accounts"}. Dot: best estimate, filled when the interval clears “no difference”. Bar: 95% interval; an arrow means it runs off the scale. Dashed line: {g.matched ? "same as similar accounts" : "same as everyone"}.
        </figcaption>
      </figure>
      <Source>
        {g.matched ? (
          <>
            {fmtInt(g.matched.accounts)} real accounts: {fmtInt(g.matched.matched)} amplifiers and their matched controls
          </>
        ) : (
          g.humans != null && <>{fmtInt(g.humans)} real accounts that engaged and had a public posting history</>
        )}
        {dot}groups from each account’s recent posts and profile, behavior only{dot}no demographic guesses
      </Source>
      <div className="g-after">
        <More summary="Who is in each group">
          <ul className="g-groups">
            {A.map((a) => (
              <li key={a.id}>
                <h3>{a.label}</h3>
                <p className="g-muted">
                  {a.description ? `Typical: ${a.description}. ` : ""}
                  {a.amplifiers != null && (g.matched ? `${fmtInt(a.size)} accounts in the matched sample, ${fmtInt(a.amplifiers)} of them amplifiers.` : `${fmtInt(a.amplifiers)} of ${fmtInt(a.size)} amplified a likely automated account.`)}
                </p>
                <p className="g-muted">
                  {a.examples.length ? (
                    <>
                      Public examples: <span className="mono">{a.examples.slice(0, 3).map((h) => handle(h)).join(", ")}</span>
                    </>
                  ) : (
                    "No public accounts in this group; private accounts are counted, never named."
                  )}
                </p>
                {a.evidence.length > 0 && (
                  <button
                    className="g-link"
                    onClick={() => {
                      const src = (m.archetypes ?? []).find((x) => x.id === a.id);
                      if (src) openDrawer(archetypeDrawer(m, src, "Chapter 5, who spread it"));
                    }}
                  >
                    See what they amplified
                  </button>
                )}
              </li>
            ))}
          </ul>
        </More>
        <More summary="How we define it">
          <p>
            A real account here scores under {HUMAN_MAX}. It amplified automation if it liked, reposted or quoted a post from an account scoring {autoCut ?? AUTOMATED} or more.{" "}
            {g.matched
              ? `Each amplifier is paired with one similar account that engaged only with posts by people (${g.matched.matching ?? "same narrative, time window, reach, activity and followers"}); ${fmtInt(g.matched.amplifiers - g.matched.matched)} found no match and are left out. A group's lift is its amplifier rate over the rate across the whole matched sample.`
              : `Each group’s rate is compared with the rate across all ${g.humans != null ? fmtInt(g.humans) : ""} real accounts that engaged.`}
          </p>
        </More>
        <Actions finding={g.findings.archetype} explore={explore("archetypes")} exploreLabel="Open the archetype details" />
      </div>
    </>
  );
}

/* ---------- 6 How we know ---------- */

function HowWeKnow({ g, explore }: ChapterProps) {
  const [ref, w] = useWidth<HTMLDivElement>(900);
  const hand = g.hand;
  const r100 = g.recall?.find((r) => r.k === "100");
  return (
    <>
      <Head
        h={
          hand ? (
            <>
              We checked by hand the {hand.n} accounts the model was surest about that don’t call themselves bots. {hand.hits} were clearly automated.
            </>
          ) : (
            <>Scores are signs, not proof. Here is how we tested them.</>
          )
        }
      >
        <p>
          The model learned from {g.platform} accounts that label themselves as bots, then looks for accounts that post the same way. It reads behavior only: posting rhythm, volume, repetition, links, account age.
          {r100?.base != null && (
            <>
              {" "}
              In a test on labeled bots it had never seen, it ranked {pc(r100.model)} of them in its top 100 accounts, against {pc(r100.base)} for posting rate alone.
            </>
          )}
        </p>
      </Head>
      {hand && (
        <figure className="g-fig" ref={ref}>
          <CheckGrid hits={hand.hits} n={hand.n} cols={w < 560 ? 10 : 25} />
          <figcaption className="g-cap">
            Each square is one hand-checked account. <span className="g-key-auto">Magenta</span>: clearly automated when checked by hand. Outlined: not clearly automated.
          </figcaption>
        </figure>
      )}
      <Source>
        Hand check: one reviewer read each account’s profile and recent posts; verdicts are never published per account
        {r100?.base != null && <>{dot}held-out test: self-labeled bots hidden from training, ranked among all {g.accounts != null ? fmtInt(g.accounts) : ""} accounts</>}
      </Source>
      <div className="g-after">
        {g.recall && g.recall.length > 1 && (
          <More summary="The test on hidden labeled bots">
            <p>We hid some self-labeled bots from the model, trained it on the rest, and counted how many of the hidden ones landed among its top-ranked accounts.</p>
            <RecallChart rows={g.recall} />
          </More>
        )}
        <More summary="The words we use">
          <dl className="g-glossary">
            <dt>Likely automated</dt>
            <dd>An account our model scores {AUTOMATED} or more out of 1 for posting like a machine. Never called a bot unless it labels itself one.</dd>
            <dt>Interval</dt>
            <dd>The range the true number most likely falls in. We give 95% intervals, from recounting on resampled accounts.</dd>
            <dt>Narrative</dt>
            <dd>One way of telling the story. A language model sorted every post into one.</dd>
            <dt>Hedge</dt>
            <dd>A word that marks a claim as unproven, like “alleged” or “suspected”.</dd>
            <dt>Archetype</dt>
            <dd>A group of real accounts that behave alike, described in plain words.</dd>
            <dt>Amplify</dt>
            <dd>Like, repost or quote someone’s post.</dd>
          </dl>
        </More>
        <More summary="Data and privacy">
          <ul className="g-rules">
            {g.sources?.data && <li>{g.sources.data}.</li>}
            <li>
              {g.windowLabel}, {g.year} (UTC){g.posts != null && <>: {fmtInt(g.posts)} posts</>}
              {g.accounts != null && <>, {fmtInt(g.accounts)} accounts</>}
              {g.engagements != null && <>, {fmtInt(g.engagements)} likes, reposts and quotes</>}.
            </li>
            <li>Only public accounts are named: news organizations, verified accounts, 5,000+ followers, self-labeled bots. Everyone else is counted, never listed.</li>
            <li>We never say whether a claim is true, or who runs an account.</li>
            <li>Limit: the model learned from self-labeled bots, which are mostly news and trend feeds, so it is best at spotting that kind of automation.</li>
            {g.modelVersion && (
              <li>
                Model version <code>{g.modelVersion}</code>
              </li>
            )}
          </ul>
        </More>
        <Actions explore={explore("method")} exploreLabel="Open the full method and validation" />
      </div>
    </>
  );
}

export const CHAPTERS: Chapter[] = [
  { id: "what", title: "What happened", short: "What happened", render: (p) => <WhatHappened {...p} /> },
  { id: "how-much", title: "How much was automated", short: "How much was automated", render: (p) => <HowMuch {...p} /> },
  { id: "where", title: "Where the automation was", short: "Where it was", render: (p) => <Where {...p} /> },
  { id: "news", title: "What newsrooms said vs Bluesky", short: "Newsrooms vs Bluesky", render: (p) => <Newsrooms {...p} /> },
  { id: "who", title: "Who spread it", short: "Who spread it", render: (p) => <WhoSpread {...p} /> },
  { id: "how", title: "How we know", short: "How we know", render: (p) => <HowWeKnow {...p} /> },
];
