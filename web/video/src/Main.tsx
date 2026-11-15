import React from 'react';
import {AbsoluteFill, Audio, CalculateMetadataFunction, Sequence, interpolate, staticFile} from 'remotion';
import {TransitionSeries, linearTiming} from '@remotion/transitions';
import {fade} from '@remotion/transitions/fade';
import '@fontsource/newsreader/500.css';
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-mono/400.css';
import {Edit, Timeline, VoiceTrack} from './lib/types';
import {resolveTime} from './lib/timeline';
import {Screen} from './components/Screen';
import {TitleCard} from './components/TitleCard';
import {Captions} from './components/Captions';

export type MainProps = {
  edit: Edit;
  tl?: Timeline;
  vo?: VoiceTrack;
  plan?: Plan;
};

type Plan = {
  titleFrames: number;
  screenFrames: number;
  outroFrames: number;
  transFrames: number;
  trimFrom: number;
  screenStart: number; // composition seconds where the screen segment starts
  voStart: number; // composition seconds where the VO starts
};

const FPS = 30;

/** Loads the capture timeline + VO timestamps and lays out the master timeline. */
export const calculateMainMetadata: CalculateMetadataFunction<MainProps> = async ({props}) => {
  const {edit} = props;
  const tl: Timeline = await (await fetch(staticFile(`${edit.capture}/timeline.json`))).json();
  const vo: VoiceTrack | undefined = edit.voiceover
    ? await (await fetch(staticFile(`vo/${edit.voiceover.id}.json`))).json()
    : undefined;
  const trimFrom = resolveTime(tl, edit.trim.from);
  const trimTo = Math.min(resolveTime(tl, edit.trim.to), tl.duration);
  const transFrames = Math.round(edit.transitionSeconds * FPS);
  const titleFrames = edit.title ? Math.round(edit.title.seconds * FPS) : 0;
  const outroFrames = edit.outro ? Math.round(edit.outro.seconds * FPS) : 0;
  const screenFrames = Math.round((trimTo - trimFrom) * FPS);
  const screenStart = edit.title ? (titleFrames - transFrames) / FPS : 0;
  let voStart = 0;
  if (edit.voiceover && vo) {
    const a = edit.voiceover.align;
    const captureT = resolveTime(tl, a.at, a.offset ?? 0);
    voStart = screenStart + (captureT - trimFrom) - vo.words[a.wordIndex].start;
  }
  const total = titleFrames + screenFrames + outroFrames - (edit.title ? transFrames : 0) - (edit.outro ? transFrames : 0);
  const plan: Plan = {titleFrames, screenFrames, outroFrames, transFrames, trimFrom, screenStart, voStart};
  return {durationInFrames: total, fps: FPS, props: {...props, tl, vo, plan}};
};

export const Main: React.FC<MainProps> = ({edit, tl, vo, plan}) => {
  if (!tl || !plan) return null;
  const total = plan.titleFrames + plan.screenFrames + plan.outroFrames;
  const voFrom = Math.round(plan.voStart * FPS);
  const voEnd = vo ? voFrom + Math.round(vo.duration * FPS) : 0;
  return (
    <AbsoluteFill style={{background: '#F7F5F0'}}>
      <TransitionSeries>
        {edit.title && (
          <TransitionSeries.Sequence durationInFrames={plan.titleFrames}>
            <TitleCard {...edit.title} />
          </TransitionSeries.Sequence>
        )}
        {edit.title && <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: plan.transFrames})} />}
        <TransitionSeries.Sequence durationInFrames={plan.screenFrames}>
          <Screen src={`${edit.capture}/video.mp4`} tl={tl} zooms={edit.zooms} trimFrom={plan.trimFrom} background={edit.background} cursorIdleHide={edit.cursorIdleHide} />
        </TransitionSeries.Sequence>
        {edit.outro && <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: plan.transFrames})} />}
        {edit.outro && (
          <TransitionSeries.Sequence durationInFrames={plan.outroFrames}>
            <TitleCard title={edit.outro.title} subtitle={edit.outro.subtitle} />
          </TransitionSeries.Sequence>
        )}
      </TransitionSeries>

      {edit.captions && vo && (
        <AbsoluteFill>
          <Captions words={vo.words} start={plan.voStart} />
        </AbsoluteFill>
      )}

      {edit.voiceover && vo && (
        <Sequence from={voFrom}>
          <Audio src={staticFile(`vo/${edit.voiceover.id}.mp3`)} volume={edit.voiceover.volume ?? 1} />
        </Sequence>
      )}

      {edit.music && (
        <Audio
          src={staticFile(edit.music.file)}
          volume={(f) => {
            const m = edit.music!;
            // duck under the VO with 0.4 s ramps, fade out over the last second
            const duck = vo
              ? interpolate(f, [voFrom - 12, voFrom, voEnd, voEnd + 12], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
              : 0;
            const fadeOut = interpolate(f, [total - 30, total], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
            return (m.volume + (m.duckTo - m.volume) * duck) * fadeOut;
          }}
        />
      )}
    </AbsoluteFill>
  );
};
