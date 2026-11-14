import { useCallback, useRef, useState } from "react";

/** Copy text; returns [copiedKey, copy]. copiedKey resets after 1.6 s. */
export function useCopy(): [string | null, (key: string, text: string) => Promise<boolean>] {
  const [copied, setCopied] = useState<string | null>(null);
  const timer = useRef<number>();
  const copy = useCallback(async (key: string, text: string) => {
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch {
      // Fallback for http origins without clipboard permission.
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        ok = document.execCommand("copy");
      } catch {
        ok = false;
      }
      ta.remove();
    }
    setCopied(ok ? key : `${key}:failed`);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setCopied(null), 1600);
    return ok;
  }, []);
  return [copied, copy];
}
