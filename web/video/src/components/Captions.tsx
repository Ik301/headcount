import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {Word} from '../lib/types';

/** Split words into short caption pages: break after sentence/clause punctuation or ~6 words. */
export function pages(words: Word[], maxWords = 7, maxChars = 44): Word[][] {
  const out: Word[][] = [];
  let cur: Word[] = [];
  for (const w of words) {
    const chars = cur.map((x) => x.text).join(' ').length + w.text.length + 1;
    if (cur.length && (cur.length >= maxWords || chars > maxChars)) {
      out.push(cur);
      cur = [];
    }
    cur.push(w);
    if (/[.?!]$/.test(w.text) || (/[,;:]$/.test(w.text) && cur.length >= 3)) {
      out.push(cur);
      cur = [];
    }
  }
  if (cur.length) out.push(cur);
  return out;
}

/** Burned-in captions; `start` is the composition time (s) where the VO audio begins. */
export const Captions: React.FC<{words: Word[]; start: number}> = ({words, start}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps - start;
  const pg = pages(words);
  const idx = pg.findIndex((p, i) => t >= p[0].start - 0.05 && t < (pg[i + 1]?.[0].start ?? p[p.length - 1].end + 0.6) - 0.05);
  if (idx < 0) return null;
  const page = pg[idx];
  return (
    <div style={{position: 'absolute', left: 0, right: 0, bottom: 92, display: 'flex', justifyContent: 'center'}}>
      <div
        style={{
          background: 'rgba(22,24,29,0.82)',
          borderRadius: 14,
          padding: '14px 28px',
          fontFamily: 'IBM Plex Sans',
          fontWeight: 500,
          fontSize: 44,
          lineHeight: 1.25,
          color: '#fff',
          boxShadow: '0 10px 30px rgba(0,0,0,0.25)',
        }}
      >
        {page.map((w, i) => (
          <span key={i} style={{opacity: t >= w.start ? 1 : 0.45, transition: 'none'}}>
            {w.text}
            {i < page.length - 1 ? ' ' : ''}
          </span>
        ))}
      </div>
    </div>
  );
};
