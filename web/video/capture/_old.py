"""Scripted, cursor-free browser capture for the composition (Playwright + CDP screencast).

Usage:
    python3 web/video/capture/capture.py test            # scenario name (see SCENARIOS below)
    WEB_BASE=http://127.0.0.1:4173 DSF=2 FPS=30 python3 web/video/capture/capture.py test

Output: web/video/public/capture/<scenario>/
    video.mp4      constant-frame-rate H.264, viewport * DSF pixels (3840x2160 at DSF=2)
    timeline.json  cursor moves, clicks, typing, scrolls and named focus boxes, in seconds
                   from the first frame of video.mp4 and in CSS pixels of the 1920x1080 viewport

Why a screencast instead of Playwright's record_video: record_video is capped at viewport size
and encodes low-bitrate VP8; CDP Page.startScreencast hands over every compositor frame as a
JPEG at device-pixel resolution, so 2x zooms stay sharp. Headless Chrome draws no cursor; the
composition renders one from the timeline, which is what makes the cursor smooth.
"""
import base64
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO_ROOT = os.path.dirname(HERE)
WEB = os.environ.get("WEB_BASE", "https://bring-fisher-headed-mill.trycloudflare.com")
DSF = float(os.environ.get("DSF", "2"))
FPS = int(os.environ.get("FPS", "30"))
JPEG_Q = int(os.environ.get("JPEG_Q", "85"))  # higher = sharper but slower frames at DSF 2
VW, VH = 1920, 1080


def ease_in_out_cubic(u):
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


class Recorder:
    """Drives the page and logs every action against the screencast clock."""

    def __init__(self, page, cdp, frames_dir):
        self.pg, self.cdp, self.frames_dir = page, cdp, frames_dir
        self.frames = []  # (epoch_seconds, path)
        self.events = []
        self.x, self.y = VW * 0.62, VH * 0.70  # where the cursor "rests" before the first move
        cdp.on("Page.screencastFrame", self._on_frame)

    # ---- screencast -------------------------------------------------------------------
    def _on_frame(self, ev):
        ts = ev["metadata"].get("timestamp") or time.time()
        path = os.path.join(self.frames_dir, f"{len(self.frames):06d}.jpg")
        with open(path, "wb") as f:
            f.write(base64.b64decode(ev["data"]))
        self.frames.append((ts, path))
        try:
            self.cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
        except Exception:
            pass

    def start(self):
        self.cdp.send("Page.startScreencast", {
            "format": "jpeg", "quality": JPEG_Q, "everyNthFrame": 1,
            "maxWidth": int(VW * DSF), "maxHeight": int(VH * DSF),
        })
        # wait for the first frame so t=0 is a real picture
        deadline = time.time() + 10
        while not self.frames and time.time() < deadline:
            self.pg.wait_for_timeout(50)
        self.t0 = self.frames[0][0] if self.frames else time.time()
        self.log("cursor", x=self.x, y=self.y)

    def stop(self):
        self.pg.wait_for_timeout(300)
        self.cdp.send("Page.stopScreencast")

    def now(self):
        return round(time.time() - self.t0, 3)

    def log(self, kind, **kw):
        self.events.append({"t": self.now(), "type": kind, **kw})

    # ---- actions ----------------------------------------------------------------------
    def wait(self, ms):
        self.pg.wait_for_timeout(ms)

    def box(self, target):
        loc = self.pg.locator(target).first if isinstance(target, str) else target
        loc.wait_for(state="visible", timeout=30000)
        b = loc.bounding_box()
        return {k: round(b[k], 1) for k in ("x", "y", "width", "height")}

    def focus(self, label, target, pad=24):
        """Record a named region (CSS px, viewport coords at this moment) for zoom targets."""
        b = self.box(target)
        self.log("focus", label=label, box={"x": b["x"] - pad, "y": b["y"] - pad,
                                            "width": b["width"] + 2 * pad, "height": b["height"] + 2 * pad})
        return b

    def move_to(self, target, duration_ms=700, anchor=(0.5, 0.5)):
        if isinstance(target, tuple):
            tx, ty = target
        else:
            b = self.box(target)
            tx, ty = b["x"] + b["width"] * anchor[0], b["y"] + b["height"] * anchor[1]
        sx, sy = self.x, self.y
        t_start = self.now()
        # slight arc so it reads as a hand, not a robot
        dx, dy = tx - sx, ty - sy
        arc = min(80.0, math.hypot(dx, dy) * 0.08)
        norm = math.hypot(dx, dy) or 1
        dur = duration_ms / 1000
        w0 = time.time()
        while True:  # time-based, so the move takes duration_ms even when each CDP call is slow
            raw = min(1.0, (time.time() - w0) / dur)
            u = ease_in_out_cubic(raw)
            bump = math.sin(math.pi * u) * arc
            self.pg.mouse.move(sx + dx * u - dy / norm * bump, sy + dy * u + dx / norm * bump)
            if raw >= 1.0:
                break
            self.pg.wait_for_timeout(12)
        self.x, self.y = tx, ty
        self.events.append({"t": t_start, "type": "move", "from": [round(sx, 1), round(sy, 1)],
                            "to": [round(tx, 1), round(ty, 1)], "t1": self.now(),
                            "easing": "easeInOutCubic", "arc": round(arc, 1)})

    def click(self, target=None, **move_kw):
        if target is not None:
            self.move_to(target, **move_kw)
        self.pg.wait_for_timeout(120)
        self.log("click", x=round(self.x, 1), y=round(self.y, 1))
        self.pg.mouse.down()
        self.pg.wait_for_timeout(70)
        self.pg.mouse.up()

    def type(self, text, delay_ms=55, target=None):
        t_start = self.now()
        self.pg.keyboard.type(text, delay=delay_ms)
        ev = {"t": t_start, "type": "type", "t1": self.now(), "text": text}
        if target:
            ev["box"] = self.box(target)
        self.events.append(ev)

    def scroll(self, dy, steps=30, pause_ms=16):
        t_start = self.now()
        for _ in range(steps):
            self.pg.mouse.wheel(0, dy / steps)
            self.pg.wait_for_timeout(pause_ms)
        self.events.append({"t": t_start, "type": "scroll", "t1": self.now(), "dy": dy})

    def mark(self, label):
        """Free-form marker the edit can refer to (e.g. 'result-visible')."""
        self.log("mark", label=label)


# ---- scenarios ------------------------------------------------------------------------
def scenario_test(r):
    pg = r.pg
    pg.goto(WEB + "/", wait_until="networkidle")
    r.start()
    r.mark("home")
    r.wait(900)
    r.focus("input", "textarea")
    r.click("textarea", duration_ms=900, anchor=(0.18, 0.5))
    r.wait(250)
    r.type("Was Jensen Huang's mistress a Chinese spy?", delay_ms=60, target="textarea")
    r.wait(350)
    r.click(pg.locator("button", has_text="Check").first, duration_ms=650)
    pg.wait_for_url(re.compile(r".*/claim/[0-9a-f]+"), timeout=75000)
    pg.wait_for_selector("text=matching posts", timeout=75000)
    r.mark("result-visible")
    headline = pg.locator("h1", has_text="Bluesky posts").first
    r.focus("headline", headline)
    r.wait(400)
    r.move_to(headline, duration_ms=1000, anchor=(-0.1, 0.45))  # park in the margin, off the text
    r.wait(3300)
    r.mark("end")


SCENARIOS = {"test": scenario_test}


def encode(frames, t0, t_end, out_mp4, fps):
    """Resample variable-rate screencast frames onto a constant fps grid via the concat demuxer."""
    frames = sorted(frames)  # screencast frames can arrive slightly out of order
    lst = out_mp4 + ".txt"
    n = max(1, int(math.ceil((t_end - t0) * fps)))
    idx, chosen = 0, []
    for k in range(n):
        t = t0 + k / fps
        while idx + 1 < len(frames) and frames[idx + 1][0] <= t:
            idx += 1
        chosen.append(frames[idx][1])
    with open(lst, "w") as f:
        # collapse runs of the same frame into one entry with a longer duration
        run_path, run_len = chosen[0], 0
        for p in chosen + [None]:
            if p == run_path:
                run_len += 1
                continue
            f.write(f"file '{run_path}'\nduration {run_len / fps:.6f}\n")
            run_path, run_len = p, 1
        f.write(f"file '{chosen[-1]}'\n")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
        "-vf", f"fps={fps},format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "14",
        "-movflags", "+faststart", out_mp4], check=True)
    os.remove(lst)
    return n / fps


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "test"
    out_dir = os.path.join(VIDEO_ROOT, "public", "capture", name)
    frames_dir = os.path.join(os.environ.get("TMPDIR", "/tmp"), f"sbt_capture_{name}")
    shutil.rmtree(frames_dir, ignore_errors=True)
    os.makedirs(frames_dir)
    os.makedirs(out_dir, exist_ok=True)
    wall0 = time.time()
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", args=["--hide-scrollbars", "--force-color-profile=srgb",
                                                       # without this the screencast ships DIP-size (1920) frames
                                                       # even when the page renders at devicePixelRatio 2
                                                       f"--force-device-scale-factor={DSF:g}"])
        ctx = b.new_context(viewport={"width": VW, "height": VH}, device_scale_factor=DSF)
        pg = ctx.new_page()
        cdp = ctx.new_cdp_session(pg)
        r = Recorder(pg, cdp, frames_dir)
        SCENARIOS[name](r)
        t_end = time.time()
        r.stop()
        b.close()
    frames = r.frames
    duration = encode(frames, r.t0, t_end, os.path.join(out_dir, "video.mp4"), FPS)
    gaps = [b[0] - a[0] for a, b in zip(frames, frames[1:])]
    timeline = {
        "scenario": name, "web": WEB, "viewport": {"width": VW, "height": VH}, "dsf": DSF,
        "fps": FPS, "duration": round(duration, 3), "events": r.events,
        "stats": {"frames": len(frames), "max_gap_s": round(max(gaps), 3) if gaps else None,
                  "capture_wall_s": round(time.time() - wall0, 1),
                  "frame_times": [round(f[0] - r.t0, 3) for f in frames]},
    }
    with open(os.path.join(out_dir, "timeline.json"), "w") as f:
        json.dump(timeline, f, indent=1)
    shutil.rmtree(frames_dir, ignore_errors=True)
    stats = {k: v for k, v in timeline["stats"].items() if k != "frame_times"}
    print(json.dumps({"out": out_dir, **stats, "duration": timeline["duration"],
                      "events": len(r.events)}))


if __name__ == "__main__":
    main()
