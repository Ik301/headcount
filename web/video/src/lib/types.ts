// Shapes of the JSON written by capture/capture.py and tts/tts.py, plus the edit spec.

export type Box = {x: number; y: number; width: number; height: number};

export type CaptureEvent =
  | {t: number; type: 'cursor'; x: number; y: number}
  | {t: number; type: 'move'; t1: number; from: [number, number]; to: [number, number]; easing: string; arc: number}
  | {t: number; type: 'click'; x: number; y: number}
  | {t: number; type: 'type'; t1: number; text: string; box?: Box}
  | {t: number; type: 'scroll'; t1: number; dy: number}
  | {t: number; type: 'focus'; label: string; box: Box}
  | {t: number; type: 'mark'; label: string};

export type Timeline = {
  scenario: string;
  viewport: {width: number; height: number};
  dsf: number;
  fps: number;
  duration: number;
  events: CaptureEvent[];
};

export type Word = {text: string; start: number; end: number};
export type VoiceTrack = {id: string; text: string; duration: number; words: Word[]};

/**
 * A time reference into the capture: a number (capture seconds) or a string
 *   'mark:<label>' | 'focus:<label>' | 'click:<n>' | 'type:<n>' | 'move:<n>' | 'end'
 * (n counts from 0 in event order). `offset` is added in seconds.
 */
export type TimeRef = number | string;

export type Zoom = {
  at: TimeRef; // when the zoom starts ramping in
  offset?: number;
  hold: number; // seconds fully zoomed before ramping out
  scale: number; // 1.0 = no zoom; 1.6-2.0 reads well
  target: string; // 'focus:<label>' (box from the timeline) or 'cursor' (follow the cursor)
  ramp?: number; // seconds for the in/out move, default 0.9
};

export type Edit = {
  capture: string; // folder under public/, e.g. 'capture/test'
  trim: {from: TimeRef; to: TimeRef}; // portion of the capture to use
  title?: {kicker?: string; title: string; subtitle?: string; seconds: number};
  outro?: {title: string; subtitle?: string; seconds: number};
  transitionSeconds: number;
  zooms: Zoom[];
  voiceover?: {
    id: string; // public/vo/<id>.mp3 + .json
    // place the VO so that word #wordIndex starts exactly at capture time `at`
    align: {wordIndex: number; at: TimeRef; offset?: number};
    volume?: number;
  };
  music?: {file: string; volume: number; duckTo: number};
  captions: boolean;
  background: string; // CSS background behind the framed screen
  cursorIdleHide?: number; // fade the cursor after this many still seconds (default 1.6)
};
