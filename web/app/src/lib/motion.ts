import { useLayoutEffect, useRef, useState, type CSSProperties, type RefObject } from "react";

/** Stagger index and extra delay for the motion classes in styles/motion.css (`.in`, `.in-wipe`, `.grow`, ...). */
export function seq(i: number, delayMs = 0): CSSProperties {
  return { ["--i" as string]: i, ["--d" as string]: `${delayMs}ms` } as CSSProperties;
}

/**
 * Arms a block's entrance so it plays when the block is scrolled into view, not offscreen at load.
 * Content is visible by default: the block is only held back once JS has armed it, and a 6 s
 * fallback releases it even if IntersectionObserver never reports.
 * Returns a ref and the class to put on the block ("reveal", plus "is-armed" / "is-live").
 */
export function useReveal<T extends HTMLElement>(): [RefObject<T>, string] {
  const ref = useRef<T>(null);
  const [state, setState] = useState<"" | "armed" | "live">("");
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const r = el.getBoundingClientRect();
    if (r.top < window.innerHeight * 0.9) {
      setState("live");
      return;
    }
    setState("armed");
    const io = new IntersectionObserver(
      (es) => {
        if (es.some((e) => e.isIntersecting)) {
          setState("live");
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -12% 0px" },
    );
    io.observe(el);
    const t = window.setTimeout(() => setState("live"), 6000);
    return () => {
      io.disconnect();
      window.clearTimeout(t);
    };
  }, []);
  return [ref, `reveal${state === "armed" ? " is-armed" : state === "live" ? " is-live" : ""}`];
}
