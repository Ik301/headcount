import type { CSSProperties } from "react";

/** Stagger index and extra delay for the motion classes in styles/motion.css (`.in`, `.in-wipe`, `.grow`, ...). */
export function seq(i: number, delayMs = 0): CSSProperties {
  return { ["--i" as string]: i, ["--d" as string]: `${delayMs}ms` } as CSSProperties;
}
