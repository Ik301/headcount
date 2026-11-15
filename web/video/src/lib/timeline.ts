import {Box, CaptureEvent, TimeRef, Timeline} from './types';

export const easeInOutCubic = (u: number) => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2);
export const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export function resolveTime(tl: Timeline, ref: TimeRef, offset = 0): number {
  if (typeof ref === 'number') return ref + offset;
  if (ref === 'end') return tl.duration + offset;
  const [kind, arg] = ref.split(':');
  let hit: CaptureEvent | undefined;
  if (kind === 'mark' || kind === 'focus') {
    hit = tl.events.find((e) => e.type === kind && (e as {label: string}).label === arg);
  } else {
    const n = Number(arg ?? 0);
    hit = tl.events.filter((e) => e.type === kind)[n];
  }
  if (!hit) throw new Error(`time ref not found in timeline: ${ref}`);
  return hit.t + offset;
}

export function focusBox(tl: Timeline, label: string): Box {
  const e = tl.events.find((x) => x.type === 'focus' && x.label === label);
  if (!e || e.type !== 'focus') throw new Error(`focus box not found: ${label}`);
  return e.box;
}

/** Cursor position (CSS px) at capture time t, replaying the exact curve capture.py drove. */
export function cursorAt(tl: Timeline, t: number): {x: number; y: number} {
  let x = tl.viewport.width * 0.62;
  let y = tl.viewport.height * 0.7;
  for (const e of tl.events) {
    if (e.t > t) break;
    if (e.type === 'cursor' || e.type === 'click') {
      x = e.x;
      y = e.y;
    } else if (e.type === 'move') {
      const [sx, sy] = e.from;
      const [tx, ty] = e.to;
      if (t >= e.t1) {
        x = tx;
        y = ty;
      } else {
        const u = easeInOutCubic(clamp((t - e.t) / (e.t1 - e.t), 0, 1));
        const dx = tx - sx;
        const dy = ty - sy;
        const len = Math.hypot(dx, dy) || 1;
        const bump = Math.sin(Math.PI * u) * e.arc;
        x = sx + dx * u + (-dy / len) * bump;
        y = sy + dy * u + (dx / len) * bump;
      }
    }
  }
  return {x, y};
}

/** Seconds since the most recent click at or before t (Infinity if none) and where it was. */
export function lastClick(tl: Timeline, t: number): {age: number; x: number; y: number} {
  let best = {age: Infinity, x: 0, y: 0};
  for (const e of tl.events) {
    if (e.type === 'click' && e.t <= t) best = {age: t - e.t, x: e.x, y: e.y};
  }
  return best;
}

/** Seconds the cursor has been still at time t (moves and clicks reset it). */
export function cursorIdle(tl: Timeline, t: number): number {
  let lastActive = 0;
  for (const e of tl.events) {
    if (e.t > t) break;
    if (e.type === 'move') lastActive = Math.min(t, e.t1);
    else if (e.type === 'click' || e.type === 'cursor') lastActive = e.t;
  }
  return t - lastActive;
}
