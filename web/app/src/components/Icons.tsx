/* One stroke icon set (1.6px, round caps), drawn for this app. Use <Icon name="..." />. */
const PATHS: Record<string, JSX.Element> = {
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  chev: <path d="M6 9l6 6 6-6" />,
  share: (
    <>
      <path d="M12 15V4M7.5 8.5L12 4l4.5 4.5" />
      <path d="M5 13v5.5A1.5 1.5 0 006.5 20h11a1.5 1.5 0 001.5-1.5V13" />
    </>
  ),
  msg: <path d="M4.5 6.5A2 2 0 016.5 4.5h11a2 2 0 012 2v8a2 2 0 01-2 2H10l-4.5 3.5v-3.5h0a1 1 0 01-1-1z" />,
  scale: (
    <>
      <path d="M12 4v16M8 20h8M5 7h14" />
      <path d="M5 7l-2.5 6a2.5 2.5 0 005 0zM19 7l-2.5 6a2.5 2.5 0 005 0z" />
    </>
  ),
  lock: (
    <>
      <rect x="5.5" y="10.5" width="13" height="9" rx="1.5" />
      <path d="M8.5 10.5V8a3.5 3.5 0 017 0v2.5" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v4.5l3 1.8" />
    </>
  ),
  ext: <path d="M10 6H6.5A1.5 1.5 0 005 7.5v10A1.5 1.5 0 006.5 19h10a1.5 1.5 0 001.5-1.5V14M13 5h6v6M19 5l-8 8" />,
  copy: (
    <>
      <rect x="8.5" y="8.5" width="11" height="11" rx="1.5" />
      <path d="M15.5 5.5h-9a1.5 1.5 0 00-1.5 1.5v9" />
    </>
  ),
  link: <path d="M10 14l4-4M8.5 11.5L6.6 13.4a3 3 0 004.2 4.2l1.9-1.9M15.5 12.5l1.9-1.9a3 3 0 00-4.2-4.2l-1.9 1.9" />,
  x: <path d="M6 6l12 12M18 6L6 18" />,
  play: <path d="M8 5.5v13l10.5-6.5z" fill="currentColor" />,
  pause: <path d="M7.5 5.5h3v13h-3zM13.5 5.5h3v13h-3z" fill="currentColor" />,
  alert: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v5M12 16v.01" />
    </>
  ),
  chart: <path d="M5 19V11M10 19V6M15 19v-9M20 19v-5M3 20.5h18" />,
};

export function Icon({ name, className = "i", label }: { name: keyof typeof PATHS | string; className?: string; label?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden={label ? undefined : true} role={label ? "img" : undefined} aria-label={label}>
      {PATHS[name]}
    </svg>
  );
}

export function Mark() {
  return (
    <svg viewBox="0 0 22 22" aria-hidden="true" className="mark-ic">
      <g stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
        <path d="M3 17V13" />
        <path d="M7 17V9" />
        <path d="M11 17V5" />
        <path d="M15 17V10" />
        <path d="M19 17V14" />
      </g>
      <path d="M2 19.5h18" stroke="currentColor" strokeWidth="1" opacity=".35" />
    </svg>
  );
}
