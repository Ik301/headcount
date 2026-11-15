import { useEffect, useId, useRef, useState, type ReactNode } from "react";

/* Provenance receipts: any number can carry its own receipt. Tap or click the number and a small
 * monospace ticket unfolds under it: where the number comes from, how many posts or accounts it rests on,
 * how its interval was computed, which model scored it. Tap, not hover, so it works on a phone and on a
 * projector. Every line is passed in by the caller from the same JSON the number came from; the component
 * never makes a number up and never shows a handle (callers pass counts and methods only). */

export type ReceiptLine = [label: string, value: ReactNode];

export function Receipt({ lines, children, title, className, align }: { lines: (ReceiptLine | null | false | undefined)[]; children: ReactNode; title?: string; className?: string; align?: "left" | "right" }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const box = useRef<HTMLSpanElement>(null);
  const shown = lines.filter(Boolean) as ReceiptLine[];

  useEffect(() => {
    if (!open) return;
    const away = (e: Event) => box.current && !box.current.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  if (!shown.length) return <>{children}</>;
  return (
    <span className={`rc${open ? " is-open" : ""}${align === "right" ? " rc-right" : ""}${className ? ` ${className}` : ""}`} ref={box}>
      <button type="button" className="rc-num" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)} title="Where this number comes from">
        {children}
      </button>
      {open && (
        <span className="rc-ticket" id={id} role="note">
          <span className="rc-head">{title ?? "Receipt"}</span>
          {shown.map(([k, v], i) => (
            <span className="rc-line" key={i}>
              <span className="rc-k">{k}</span>
              <span className="rc-dots" aria-hidden="true" />
              <span className="rc-v">{v}</span>
            </span>
          ))}
          <span className="rc-foot">Every number on this page has a receipt. Tap one.</span>
        </span>
      )}
    </span>
  );
}
