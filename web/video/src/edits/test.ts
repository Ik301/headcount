import {Edit} from '../lib/types';

// 10-15 s pipeline test: title card -> claim typed -> result -> zoom on the headline.
export const testEdit: Edit = {
  capture: 'capture/test',
  trim: {from: 1.1, to: 'mark:end'},
  title: {
    kicker: 'HackPrinceton 2026',
    title: 'Headcount',
    subtitle: 'Volume is not consensus.',
    seconds: 2.6,
  },
  transitionSeconds: 0.5,
  zooms: [
    // ramp in 0.35 s after the result renders, hold on the headline, ramp out at the end
    {at: 'mark:result-visible', offset: 0.35, ramp: 1.0, hold: 2.3, scale: 1.8, target: 'focus:headline'},
  ],
  voiceover: {
    id: 'test-river',
    // word 7 is "In" ("In about a second, ...") -> lands just before the click on Check (click #1)
    align: {wordIndex: 7, at: 'click:1', offset: -0.45},
  },
  music: {file: 'music/pad.mp3', volume: 0.16, duckTo: 0.07},
  captions: true,
  background: 'linear-gradient(135deg, #EFE9DD 0%, #E6DFD1 55%, #DCD3C2 100%)',
};
