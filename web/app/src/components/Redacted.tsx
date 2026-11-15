import type { ReactNode } from "react";

/* The API and the export mask what privacy rules keep out of example posts: "@[account]" or
 * "@[a private account]" where an @mention was, "[link]" where a private author's link was. Show those as
 * quiet placeholders so they read as deliberate redactions, not broken handles or links. */
const MASK = /@\[[^\]\n]{1,40}\]|\[link\]/g;

export function Redacted({ text }: { text: string }) {
  const out: ReactNode[] = [];
  let last = 0;
  for (const mt of text.matchAll(MASK)) {
    const i = mt.index ?? 0;
    if (i > last) out.push(text.slice(last, i));
    const link = mt[0] === "[link]";
    out.push(
      <span key={i} className="redacted" title={link ? "Link removed: private author" : "Mention removed: not a public account"}>
        {link ? "link removed" : "@ account"}
      </span>,
    );
    last = i + mt[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return <>{out}</>;
}
