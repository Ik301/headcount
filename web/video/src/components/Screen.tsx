import React from 'react';
import {OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Timeline, Zoom} from '../lib/types';
import {cameraAt} from '../lib/camera';
import {cursorAt, cursorIdle, lastClick} from '../lib/timeline';
import {ClickRipple, Cursor} from './Cursor';

/**
 * The recording inside a rounded frame on a soft background, with a moving camera and a
 * rendered cursor. `trimFrom` is the capture time shown at local frame 0.
 */
export const Screen: React.FC<{
  src: string;
  tl: Timeline;
  zooms: Zoom[];
  trimFrom: number;
  background: string;
  cursorIdleHide?: number;
}> = ({src, tl, zooms, trimFrom, background, cursorIdleHide = 1.6}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = trimFrom + frame / fps;
  const W = tl.viewport.width;
  const H = tl.viewport.height;
  const frameW = width * 0.9;
  const k = frameW / W; // CSS px -> composition px
  const frameH = H * k;
  const cam = cameraAt(tl, zooms, t);
  const tx = W / 2 - cam.cx * cam.scale;
  const ty = H / 2 - cam.cy * cam.scale;
  const cur = cursorAt(tl, t);
  const click = lastClick(tl, t);
  const press = click.age < 0.12 ? 1 - click.age / 0.12 : 0;
  // Screen-Studio-style: the cursor fades out when it has been still for a while
  const idle = cursorIdle(tl, t);
  const cursorOpacity = 1 - Math.min(1, Math.max(0, (idle - cursorIdleHide) / 0.4));

  return (
    <div style={{position: 'absolute', inset: 0, background}}>
      <div
        style={{
          position: 'absolute',
          left: (width - frameW) / 2,
          top: (height - frameH) / 2,
          width: frameW,
          height: frameH,
          borderRadius: 18,
          overflow: 'hidden',
          boxShadow: '0 30px 80px rgba(22,24,29,0.28), 0 0 0 1px rgba(22,24,29,0.08)',
          background: '#F7F5F0',
        }}
      >
        {/* layer in viewport CSS px, scaled to the frame, then moved by the camera */}
        <div
          style={{
            position: 'absolute',
            width: W,
            height: H,
            transformOrigin: '0 0',
            transform: `scale(${k}) translate(${tx}px, ${ty}px) scale(${cam.scale})`,
          }}
        >
          <OffthreadVideo
            src={staticFile(src)}
            trimBefore={Math.round(trimFrom * fps)}
            muted
            style={{position: 'absolute', left: 0, top: 0, width: W, height: H}}
          />
          <ClickRipple x={click.x} y={click.y} age={click.age} />
          <div style={{opacity: cursorOpacity}}>
            <Cursor x={cur.x} y={cur.y} press={press} />
          </div>
        </div>
      </div>
    </div>
  );
};
