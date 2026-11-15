import {Easing} from 'remotion';
import {Timeline, Zoom} from './types';
import {clamp, cursorAt, focusBox, resolveTime} from './timeline';

const ease = Easing.bezier(0.65, 0, 0.35, 1);

export type Camera = {scale: number; cx: number; cy: number}; // center in CSS px of the viewport

/**
 * Screen-Studio-style camera: each zoom ramps in over `ramp` s toward its target, holds, and
 * ramps back out. Targets are a focus box (centered, scale capped so the box still fits) or
 * the live cursor position. Overlapping zooms: the later one wins.
 */
export function cameraAt(tl: Timeline, zooms: Zoom[], t: number): Camera {
  const W = tl.viewport.width;
  const H = tl.viewport.height;
  let cam: Camera = {scale: 1, cx: W / 2, cy: H / 2};
  for (const z of zooms) {
    const ramp = z.ramp ?? 0.9;
    const t0 = resolveTime(tl, z.at, z.offset ?? 0);
    const t1 = t0 + ramp + z.hold;
    if (t < t0 || t > t1 + ramp) continue;
    const pIn = ease(clamp((t - t0) / ramp, 0, 1));
    const pOut = ease(clamp((t - t1) / ramp, 0, 1));
    const p = pIn * (1 - pOut);
    let tx: number;
    let ty: number;
    let s = z.scale;
    if (z.target === 'cursor') {
      ({x: tx, y: ty} = cursorAt(tl, t));
    } else {
      const b = focusBox(tl, z.target.replace(/^focus:/, ''));
      tx = b.x + b.width / 2;
      ty = b.y + b.height / 2;
      s = Math.min(s, W / b.width, H / b.height); // never crop the thing we zoom to
    }
    const scale = 1 + (s - 1) * p;
    // keep the visible window inside the recording
    const halfW = W / (2 * scale);
    const halfH = H / (2 * scale);
    const cx = clamp(W / 2 + (tx - W / 2) * p, halfW, W - halfW);
    const cy = clamp(H / 2 + (ty - H / 2) * p, halfH, H - halfH);
    cam = {scale, cx, cy};
  }
  return cam;
}
