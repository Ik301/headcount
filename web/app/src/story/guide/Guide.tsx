import { useEffect, useMemo, useRef, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { SiteData } from "../../api/types";
import { Icon } from "../../components/Icons";
import { countWord } from "../../lib/format";
import { TopBar } from "../../components/Shell";
import type { DrawerContent } from "../Drawer";
import type { Model } from "../model";
import { CHAPTERS } from "./chapters";
import { buildGuide } from "./data";

/** Route "/story" by default: a guided story in six short chapters. ?ch=1..6 picks a chapter; the
 *  explore mode (?mode=explore) keeps the full dashboard. Left/right arrow keys step through. */
export function Guide({ data, m, openDrawer, children }: { data: SiteData; m: Model; openDrawer: (c: DrawerContent) => void; children?: ReactNode }) {
  const [params, setParams] = useSearchParams();
  const g = useMemo(() => buildGuide(data, m), [data, m]);
  const n = CHAPTERS.length;
  const ch = Math.min(n, Math.max(1, parseInt(params.get("ch") ?? "1", 10) || 1));
  const still = params.get("still") === "1";
  const top = useRef<HTMLDivElement>(null);
  const chapter = CHAPTERS[ch - 1];

  const href = (i: number) => {
    const p = new URLSearchParams(params);
    p.set("ch", String(i));
    p.delete("mode");
    p.delete("view");
    return `?${p.toString()}`;
  };
  const explore = (view: string) => `?mode=explore&view=${view}`;
  const go = (i: number) => {
    const p = new URLSearchParams(params);
    p.set("ch", String(i));
    setParams(p);
  };

  useEffect(() => {
    document.title = `${chapter.title} · ${g.title.split(",")[0]}`;
  }, [chapter, g.title]);

  useEffect(() => {
    window.scrollTo({ top: 0 });
    top.current?.focus({ preventScroll: true });
  }, [ch]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey || /INPUT|TEXTAREA|SELECT/.test(el.tagName) || el.getAttribute("role") === "slider" || document.querySelector(".drawer.on")) return;
      if (e.key === "ArrowRight" && ch < n) go(ch + 1);
      if (e.key === "ArrowLeft" && ch > 1) go(ch - 1);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  return (
    <div className="page story guide">
      <TopBar />
      <div className="g-top">
        <div className="g-wrap g-top-row">
          <p className="g-story">
            <span className="g-story-title">{g.title.split(",")[0]}</span>
            <span className="g-muted">
              {g.platform}, {g.windowLabel}, {g.year}
              {ch === 1 && <>. {countWord(n)} short chapters, about two minutes.</>}
            </span>
          </p>
          <nav className="g-mode" aria-label="How to read this story">
            <span aria-current="page">Guided story</span>
            <Link to={explore("replay")}>Explore all the data</Link>
          </nav>
        </div>
        <nav className="g-wrap g-steps" aria-label="Chapters">
          <ol>
            {CHAPTERS.map((c, i) => (
              <li key={c.id} className={i + 1 === ch ? "is-current" : i + 1 < ch ? "is-done" : ""}>
                <Link to={href(i + 1)} aria-current={i + 1 === ch ? "step" : undefined}>
                  <span className="g-step-n">{i + 1}</span>
                  <span className="g-step-t">{c.short}</span>
                </Link>
              </li>
            ))}
          </ol>
        </nav>
      </div>
      <main className="g-wrap g-main">
        <article className="g-chapter" key={chapter.id} ref={top} tabIndex={-1} aria-label={`Chapter ${ch}: ${chapter.title}`}>
          <p className="g-kicker">
            Chapter {ch} of {n}
            <span aria-hidden="true"> · </span>
            {chapter.title}
          </p>
          {chapter.render({ m, g, still, openDrawer, explore })}
        </article>
        <nav className="g-pager" aria-label="Chapter navigation">
          {ch > 1 ? (
            <Link className="g-prev" to={href(ch - 1)}>
              <span className="g-arrow-back">
                <Icon name="arrow" />
              </span>
              <span>
                <span className="g-pager-k">Back</span>
                {CHAPTERS[ch - 2].title}
              </span>
            </Link>
          ) : (
            <span />
          )}
          {ch < n ? (
            <Link className="g-next" to={href(ch + 1)}>
              <span>
                <span className="g-pager-k">Next</span>
                {CHAPTERS[ch].title}
              </span>
              <Icon name="arrow" />
            </Link>
          ) : (
            <Link className="g-next" to={explore("replay")}>
              <span>
                <span className="g-pager-k">Done</span>
                Explore all the data
              </span>
              <Icon name="arrow" />
            </Link>
          )}
        </nav>
        <p className="g-keys">Tip: the left and right arrow keys move between chapters.</p>
      </main>
      {children}
    </div>
  );
}
