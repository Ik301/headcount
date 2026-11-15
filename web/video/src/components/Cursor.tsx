import React from 'react';

/** macOS-like arrow; (0,0) is the hotspot. Size is in viewport CSS px. */
export const Cursor: React.FC<{x: number; y: number; press: number; size?: number}> = ({x, y, press, size = 26}) => {
  const s = 1 - 0.18 * press;
  return (
    <svg
      width={size}
      height={size * 1.5}
      viewBox="0 0 20 30"
      style={{
        position: 'absolute',
        left: x,
        top: y,
        transform: `translate(-2px, -1px) scale(${s})`,
        transformOrigin: '2px 1px',
        filter: 'drop-shadow(0 2px 3px rgba(0,0,0,0.35))',
        pointerEvents: 'none',
      }}
    >
      <path d="M2 1 L2 23 L7.5 17.8 L11.2 26.5 L14.6 25 L11 16.6 L18.5 16.6 Z" fill="#111" stroke="#fff" strokeWidth={1.6} strokeLinejoin="round" />
    </svg>
  );
};

export const ClickRipple: React.FC<{x: number; y: number; age: number}> = ({x, y, age}) => {
  if (age < 0 || age > 0.55) return null;
  const u = age / 0.55;
  const r = 10 + 34 * u;
  return (
    <div
      style={{
        position: 'absolute',
        left: x - r,
        top: y - r,
        width: 2 * r,
        height: 2 * r,
        borderRadius: '50%',
        border: '3px solid rgba(217,71,43,0.85)',
        background: 'rgba(217,71,43,0.12)',
        opacity: 1 - u,
        pointerEvents: 'none',
      }}
    />
  );
};
