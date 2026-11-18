"""Engines: the useful parts of the 5 open-source clippers in vendor/, as free local CLIs.

  facecam    Auto-detect the streamer's webcam box in gameplay (for render.py "split").
             Technique from ViralCutter / AI-Youtube-Shorts-Generator face detection (OpenCV).
  facetrack  Face-following 9:16 crop with motion smoothing (AI-Youtube-Shorts-Generator
             local mode, called directly from vendor/). Best for IRL / just-chatting / reactions.
  status     Which vendor engines are installed and runnable on this PC.

Highlight picking is NOT done here: in this system the Claude agents are the LLM, so
nothing needs OpenAI/Gemini keys.

Usage:
  python tools/engines.py facecam   --video sec.mp4 [--samples 12]
  python tools/engines.py facetrack --video sec.mp4 --out tracked.mp4
  python tools/engines.py status
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from common import ROOT, emit, ffprobe_duration, log

VENDOR = ROOT / "vendor"


def _cv2():
    try:
        import cv2  # noqa: PLC0415
        return cv2
    except ImportError:
        sys.exit("[error] OpenCV missing: bin/py -m pip install 'opencv-python-headless<5'")


def cmd_facecam(a):
    """Find faces in sampled frames; a facecam is a small face cluster that stays put near an edge/corner."""
    cv2 = _cv2()
    cap = cv2.VideoCapture(a.video)
    sw, sh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dur = ffprobe_duration(Path(a.video))
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    hits = []
    for i in range(a.samples):
        cap.set(cv2.CAP_PROP_POS_MSEC, dur * 1000 * (i + 0.5) / a.samples)
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        for (x, y, w, h) in casc.detectMultiScale(gray, 1.1, 6, minSize=(max(24, sh // 30),) * 2):
            hits.append((x + w / 2, y + h / 2, w, h))
    cap.release()
    if not hits:
        emit({"facecam": None, "source_size": [sw, sh], "reason": "no face found -> use layout blur/crop"})
        return
    # cluster by grid cell, keep the most persistent cluster
    cell = lambda c: (int(c[0] // (sw / 6)), int(c[1] // (sh / 6)))  # noqa: E731
    groups: dict = {}
    for c in hits:
        groups.setdefault(cell(c), []).append(c)
    best = max(groups.values(), key=len)
    persistence = len(best) / a.samples
    cx = sum(c[0] for c in best) / len(best); cy = sum(c[1] for c in best) / len(best)
    fw = sorted(c[2] for c in best)[len(best) // 2]; fh = sorted(c[3] for c in best)[len(best) // 2]
    # webcam box ~ face * 2.6 wide, 16:9-ish; clamp to frame
    bw = min(sw, int(fw * 2.8)); bh = min(sh, int(bw * 9 / 16 * 1.15))
    x = int(max(0, min(sw - bw, cx - bw / 2))); y = int(max(0, min(sh - bh, cy - bh * 0.45)))
    is_cam = persistence >= 0.4 and fw < sw * 0.25
    emit({"facecam": [x, y, bw, bh] if is_cam else None, "face_center": [round(cx), round(cy)],
          "face_size": [fw, fh], "persistence": round(persistence, 2), "source_size": [sw, sh],
          "suggested_layout": "split" if is_cam else ("crop" if fw >= sw * 0.25 else "blur"),
          "note": "verify by Reading a frame; tighten the box to the webcam border if needed"})


def cmd_facetrack(a):
    _cv2()
    sys.path.insert(0, str(VENDOR / "AI-Youtube-Shorts-Generator"))
    try:
        from shorts_generator.local.clipper import _reframe_vertical  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        sys.exit(f"[error] could not load AI-Youtube-Shorts-Generator clipper: {e}")
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    log("face-tracking reframe (AI-Youtube-Shorts-Generator local engine)")
    _reframe_vertical(str(Path(a.video).resolve()), str(out.resolve()), a.aspect)
    emit({"video": str(out), "duration": ffprobe_duration(out), "engine": "AI-Youtube-Shorts-Generator/local"})


def cmd_status(_a):
    def has(mod):
        try:
            __import__(mod); return True
        except Exception:  # noqa: BLE001
            return False
    docker = shutil.which("docker") is not None
    emit({
        "opencv": has("cv2"),
        "engines": {
            "AI-Youtube-Shorts-Generator": {"present": (VENDOR / "AI-Youtube-Shorts-Generator").exists(),
                                            "runnable": has("cv2"), "used_for": "facetrack, facecam"},
            "ViralCutter": {"present": (VENDOR / "ViralCutter").exists(), "runnable": has("mediapipe") and has("whisperx"),
                            "used_for": "reference: viral-segment prompt, 1/2-face layouts, subtitle styles"},
            "autoclip": {"present": (VENDOR / "autoclip").exists(), "runnable": False,
                         "used_for": "optional full app (Docker/CLI+MCP, needs Ollama for free use)"},
            "reelsaw": {"present": (VENDOR / "reelsaw").exists(), "runnable": False, "docker_cli": docker,
                        "used_for": "optional full app (Docker + MCP, fully local with Ollama)"},
            "openshorts": {"present": (VENDOR / "openshorts").exists() and any((VENDOR / "openshorts").iterdir()),
                           "runnable": False, "docker_cli": docker, "used_for": "optional full app (Docker)"},
        }})


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("facecam"); s.add_argument("--video", required=True); s.add_argument("--samples", type=int, default=12)
    s.set_defaults(fn=cmd_facecam)
    s = sub.add_parser("facetrack"); s.add_argument("--video", required=True); s.add_argument("--out", required=True)
    s.add_argument("--aspect", default="9:16"); s.set_defaults(fn=cmd_facetrack)
    s = sub.add_parser("status"); s.set_defaults(fn=cmd_status)
    a = p.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
