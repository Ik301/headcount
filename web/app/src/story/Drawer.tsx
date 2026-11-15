import { useEffect, useRef } from "react";
import type { Evidence } from "../api/types";
import { Icon } from "../components/Icons";
import { handle, isoSec, postRef } from "../lib/format";
import { useCopy } from "../lib/useCopy";

export interface DrawerContent {
  from: string;
  title: string;
  meta?: [string, string][];
  quote?: string;
  reasons?: string[];
  evidence: Evidence[];
  cite?: string;
  foot?: string;
}

/** The one evidence drawer (DEMO H8): fed by the evidence arrays on narratives, archetypes and
 *  clusters. Private accounts render as "a private account"; DIDs inside post URIs are never shown. */
export function EvidenceDrawer({ content, onClose }: { content: DrawerContent | null; onClose: () => void }) {
  const ref = useRef<HTMLElement>(null);
  const last = useRef<Element | null>(null);
  const [copied, copy] = useCopy();
  const open = !!content;

  useEffect(() => {
    if (open) {
      last.current = document.activeElement;
      window.setTimeout(() => ref.current?.focus({ preventScroll: true }), 40);
    } else if (last.current instanceof HTMLElement) last.current.focus({ preventScroll: true });
  }, [open]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && open && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      <div className={`scrim${open ? " on" : ""}`} onClick={onClose} />
      <aside ref={ref} className={`drawer${open ? " on" : ""}`} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="dtitle" aria-hidden={!open}>
        {content && (
          <>
            <div className="dh">
              <div className="from">Opened from: {content.from}</div>
              <h2 id="dtitle">{content.title}</h2>
              <button className="btn icon x" onClick={onClose} aria-label="Close evidence">
                <Icon name="x" />
              </button>
            </div>
            <div className="db">
              {(content.meta?.length || content.cite) && (
                <div className="cite">
                  <dl className="cmeta">
                    {content.meta?.map(([k, v]) => (
                      <div key={k} className="cm">
                        <dt>{k}</dt>
                        <dd>{v}</dd>
                      </div>
                    ))}
                  </dl>
                  {content.cite && (
                    <div className="cbtns">
                      <button className="btn" onClick={() => copy("cite", content.cite!)}>
                        <Icon name="copy" />
                        <span>{copied === "cite" ? "Copied" : "Copy citation"}</span>
                      </button>
                    </div>
                  )}
                </div>
              )}
              {content.quote && <p className="quote">“{content.quote}”</p>}
              {!!content.reasons?.length && (
                <>
                  <h3 className="dsec">Accounts acting in lockstep</h3>
                  <ul className="reasons">
                    {content.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </>
              )}
              <h3 className="dsec">Posts behind the number</h3>
              {content.evidence.length ? (
                <ul className="evlist">
                  {content.evidence.map((e, i) => (
                    <li key={i}>
                      <div className="who">
                        {e.public_handle ? <span className="h">{handle(e.public_handle)}</span> : <span>a private account</span>}
                        <time dateTime={e.t}>
                          {isoSec(e.t)}
                        </time>
                        <span className="mono ref">{postRef(e.post_uri)}</span>
                        {e.p_automated != null && <span className={`score ${e.p_automated >= 0.5 ? "hi" : "lo"}`}>{e.p_automated.toFixed(2)}</span>}
                      </div>
                      {e.text && <blockquote>{e.text}</blockquote>}
                      {(e.note || e.trace) && <p className="why">{e.note || e.trace}</p>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="empty">The export has no evidence posts for this item yet.</p>
              )}
            </div>
            <div className="df">
              <p>{content.foot ?? "Signs of automation, not proof. We do not say who runs an account. Private accounts are counted, never named."}</p>
            </div>
          </>
        )}
      </aside>
    </>
  );
}
