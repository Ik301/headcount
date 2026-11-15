import { useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";

/* Provenance receipts: any number can carry its own receipt. Tap or click the number and a small
 * monospace ticket unfolds under it: where the number comes from, how many posts or accounts it rests on,
 * how its interval was computed, which model scored it. Tap, not hover, so it works on a phone and on a
 * projector. Every line is passed in by the caller from the same JSON the number came from; the component
 * never makes a number up and never shows a handle (callers pass counts and methods only).
 *
 * The ticket is portalled to <body> and placed in page coordinates under the number, clamped to the
 * viewport. Inline, an animated headline's clip-path cut it off, later rows painted over it, and on a
 * phone a ticket under a number near the right edge ran off the screen. */

export type ReceiptLine = [label: string, value: ReactNode];

const GAP = 8; // number to ticket
const EDGE = 12; // ticket to viewport edge

export function Receipt({ lines, children, title, className, align }: { lines: (ReceiptLine | null | false | undefined)[]; children: ReactNode; title?: string; className?: string; align?: "left" | "right" }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<CSSProperties | null>(null);
  const id = useId();
  const box = useRef<HTMLSpanElement>(null);
  const btn = useRef<HTMLButtonElement>(null);
  const ticket = useRef<HTMLSpanElement>(null);
  const shown = lines.filter(Boolean) as ReceiptLine[];

  useEffect(() => {
    if (!open) return;
    const inside = (t: EventTarget | null) => !!t && t instanceof Node && (!!box.current?.contains(t) || !!ticket.current?.contains(t));
    const away = (e: Event) => !inside(e.target) && setOpen(false);
    const esc = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOpen(false);
      btn.current?.focus();
    };
    // The ticket rides the page scroll; a scrolling panel (the evidence drawer) would leave it behind, so close.
    const scrolled = (e: Event) => e.target !== document && !inside(e.target) && setOpen(false);
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    document.addEventListener("scroll", scrolled, true);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", esc);
      document.removeEventListener("scroll", scrolled, true);
    };
  }, [open]);

  // Place the ticket under the number, inside the viewport; re-place on resize and rotation.
  useLayoutEffect(() => {
    if (!open) return setPos(null);
    const place = () => {
      const b = btn.current?.getBoundingClientRect();
      if (!b) return;
      const vw = document.documentElement.clientWidth;
      const w = Math.min(360, vw - 2 * EDGE);
      const want = align === "right" ? b.right - w : b.left;
      const left = Math.max(EDGE, Math.min(want, vw - w - EDGE));
      setPos({ top: b.bottom + window.scrollY + GAP, left: left + window.scrollX, width: w });
    };
    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [open, align]);

  if (!shown.length) return <>{children}</>;
  return (
    <span className={`rc${open ? " is-open" : ""}${className ? ` ${className}` : ""}`} ref={box}>
      <button type="button" ref={btn} className="rc-num" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)} title="Where this number comes from">
        {children}
      </button>
      {open &&
        pos &&
        createPortal(
          <span className="rc-ticket" id={id} role="note" ref={ticket} style={pos}>
            <span className="rc-head">{title ?? "Receipt"}</span>
            {shown.map(([k, v], i) => (
              <span className="rc-line" key={i}>
                <span className="rc-k">{k}</span>
                <span className="rc-dots" aria-hidden="true" />
                <span className="rc-v">{v}</span>
              </span>
            ))}
            <span className="rc-foot">Every number on this page has a receipt. Tap one.</span>
          </span>,
          document.body,
        )}
    </span>
  );
}
