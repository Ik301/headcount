import { useEffect, useState } from "react";
import { fmtInt } from "../lib/format";

/** A whole number that counts up from 0 once, fast (650 ms, ease-out). Static under reduced motion. The final
 *  value is in the DOM for screen readers from the start. */
export function CountUp({ value, ms = 650 }: { value: number; ms?: number }) {
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const [v, setV] = useState(reduced ? value : 0);
  useEffect(() => {
    if (reduced) return setV(value);
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - t0) / ms);
      setV(Math.round(value * (1 - Math.pow(1 - t, 3))));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, ms, reduced]);
  return (
    <>
      <span aria-hidden="true">{fmtInt(v)}</span>
      <span className="sr-only">{fmtInt(value)}</span>
    </>
  );
}
