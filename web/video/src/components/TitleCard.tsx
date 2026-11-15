import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig, Easing} from 'remotion';

export const TitleCard: React.FC<{kicker?: string; title: string; subtitle?: string}> = ({kicker, title, subtitle}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const rise = (delay: number) => spring({frame: frame - delay, fps, config: {damping: 200}, durationInFrames: 24});
  const bar = interpolate(frame, [6, 30], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1)});
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        background: '#F7F5F0',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        padding: '0 220px',
        color: '#16181D',
      }}
    >
      {kicker && (
        <div style={{fontFamily: 'IBM Plex Mono', fontSize: 26, letterSpacing: 3, textTransform: 'uppercase', color: '#B3371E', opacity: rise(0), transform: `translateY(${(1 - rise(0)) * 16}px)`}}>
          {kicker}
        </div>
      )}
      <div style={{height: 4, width: 120 * bar, background: '#D9472B', margin: '28px 0 34px'}} />
      <div style={{fontFamily: 'Newsreader', fontWeight: 500, fontSize: 112, lineHeight: 1.02, letterSpacing: -1.5, opacity: rise(4), transform: `translateY(${(1 - rise(4)) * 24}px)`}}>
        {title}
      </div>
      {subtitle && (
        <div style={{fontFamily: 'IBM Plex Sans', fontSize: 40, lineHeight: 1.3, color: '#4A4F5A', marginTop: 30, maxWidth: 1250, opacity: rise(10), transform: `translateY(${(1 - rise(10)) * 20}px)`}}>
          {subtitle}
        </div>
      )}
    </div>
  );
};
