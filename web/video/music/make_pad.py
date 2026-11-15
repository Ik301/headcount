"""Placeholder music bed: a soft synthesized pad (original, so no licence questions).

Usage: python3 web/video/music/make_pad.py [seconds] -> web/video/public/music/pad.mp3
Swap in a real track for the final cut (see README "Music"); keep the same path or change
`music` in the edit file.
"""
import os
import subprocess
import sys
import wave

import numpy as np

SR = 44100
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 24
out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "music")
os.makedirs(out_dir, exist_ok=True)

# Am - F - C - G, two octaves of chord tones, 4 s per chord with long crossfades
CHORDS = [[220.0, 261.63, 329.63, 440.0], [174.61, 220.0, 261.63, 349.23],
          [196.0, 261.63, 329.63, 392.0], [196.0, 246.94, 293.66, 392.0]]
n = int(secs * SR)
t = np.arange(n) / SR
mix = np.zeros(n)
seg = 4.0
for k in range(int(np.ceil(secs / seg)) + 1):
    start = k * seg - 1.0
    env = np.clip((t - start) / 1.5, 0, 1) * np.clip((start + seg + 2.0 - t) / 1.5, 0, 1)
    env = np.sin(env * np.pi / 2) ** 2
    for f in CHORDS[k % 4]:
        for detune in (-0.6, 0.6):
            mix += env * np.sin(2 * np.pi * (f + detune) * t + k) * (0.6 if f > 300 else 1.0)
    mix += env * 0.5 * np.sin(2 * np.pi * CHORDS[k % 4][0] / 2 * t)  # sub
mix *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.15 * t)  # slow swell
fade = np.minimum(1, np.minimum(t / 2.0, (secs - t) / 3.0))
mix *= fade
mix /= np.max(np.abs(mix)) + 1e-9
pcm = (mix * 0.5 * 32767).astype(np.int16)
wav = os.path.join(out_dir, "pad.wav")
with wave.open(wav, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
mp3 = os.path.join(out_dir, "pad.mp3")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-af",
                "lowpass=f=2200,aecho=0.8:0.7:120|260:0.25|0.15,volume=0.9", "-ac", "2",
                "-b:a", "192k", mp3], check=True)
os.remove(wav)
print(mp3)
