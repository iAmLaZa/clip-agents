"""Doctor: check that this PC can run the clip system, and fetch the Whisper model.

Usage:
  bin/py tools/doctor.py                 full check, human readable
  bin/py tools/doctor.py --quick         JSON, only blocking problems (used by /clip-run)
  bin/py tools/doctor.py --get-model base   download faster-whisper model into models/ (resumable)
"""
from __future__ import annotations

import argparse
import importlib
import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import exe as _exe, twitch_keys, kick_keys  # noqa: E402

MODEL_FILES = ["config.json", "tokenizer.json", "vocabulary.txt", "model.bin"]
VENDOR = {
    "AI-Youtube-Shorts-Generator": "https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator.git",
    "ViralCutter": "https://github.com/RafaelGodoyEbert/ViralCutter.git",
    "autoclip": "https://github.com/zhouxiaoka/autoclip.git",
    "openshorts": "https://github.com/mutonby/openshorts.git",
    "reelsaw": "https://github.com/osbytes/reelsaw.git",
}


def which(name: str) -> str | None:
    try:
        return _exe(name)
    except SystemExit:
        return None


def get_model(size: str) -> Path:
    dest = ROOT / "models" / f"whisper-{size}"
    dest.mkdir(parents=True, exist_ok=True)
    base = f"https://huggingface.co/Systran/faster-whisper-{size}/resolve/main/"
    for f in MODEL_FILES:
        target = dest / f
        for attempt in range(60):
            have = target.stat().st_size if target.exists() else 0
            try:
                head = urllib.request.Request(base + f, method="HEAD", headers={"User-Agent": "clipper"})
                with urllib.request.urlopen(head, timeout=30) as r:
                    total = int(r.headers.get("Content-Length") or 0)
                if total and have >= total:
                    break
                req = urllib.request.Request(base + f, headers={"User-Agent": "clipper", "Range": f"bytes={have}-"})
                with urllib.request.urlopen(req, timeout=60) as r, open(target, "ab" if have else "wb") as out:
                    if have and r.status != 206:  # server ignored range -> restart
                        out.seek(0); out.truncate()
                    done = have
                    while True:
                        chunk = r.read(1 << 16)
                        if not chunk:
                            break
                        out.write(chunk); done += len(chunk)
                        if total:
                            print(f"\r  {f}: {done/1e6:6.1f} / {total/1e6:.1f} MB", end="", flush=True)
                print()
                if not total or target.stat().st_size >= total:
                    break
            except Exception as e:  # noqa: BLE001
                print(f"\n  {f}: retry {attempt+1} ({str(e)[:80]})")
                time.sleep(3)
    (dest / ".complete").write_text("ok")
    print(f"model ready: {dest}")
    return dest


def checks() -> list[dict]:
    res = []

    def add(name, ok, fix="", blocking=True, info=""):
        res.append({"check": name, "ok": bool(ok), "blocking": blocking, "fix": fix, "info": info})

    add("python >= 3.10", sys.version_info >= (3, 10), "Install Python 3.11 (SETUP.bat does it)", info=sys.version.split()[0])
    for mod, pip in [("numpy", "numpy"), ("faster_whisper", "faster-whisper"), ("yt_dlp", "yt-dlp"),
                     ("streamlink", "streamlink"), ("cv2", "opencv-python-headless"), ("dotenv", "python-dotenv")]:
        try:
            importlib.import_module(mod); ok = True
        except Exception:  # noqa: BLE001
            ok = False
        add(f"python package {pip}", ok, "bin/py -m pip install '" + pip + ("<5" if pip.startswith("opencv") else "") + "'", blocking=mod not in ("cv2", "dotenv", "streamlink"))
    for b, blocking, fix in [("ffmpeg", True, "winget install Gyan.FFmpeg"), ("ffprobe", True, "winget install Gyan.FFmpeg"),
                             ("yt-dlp", True, "bin/py -m pip install yt-dlp"), ("streamlink", False, "bin/py -m pip install streamlink")]:
        add(f"binary {b}", which(b), fix, blocking)
    add("claude CLI", shutil.which("claude"), "npm install -g @anthropic-ai/claude-code  then run: claude (log in once)", blocking=False)
    add("git", shutil.which("git"), "winget install Git.Git", blocking=False)
    m = ROOT / "models" / "whisper-base"
    add("whisper model (base)", (m / ".complete").exists(),
        "bin/py tools/doctor.py --get-model base")
    for name in VENDOR:
        d = ROOT / "vendor" / name
        add(f"vendor/{name}", d.exists() and any(d.iterdir()), f"git clone --depth 1 {VENDOR[name]} vendor/{name}", blocking=False)
    om = (ROOT.parent / "AGENT_GUIDE.md").exists() or (ROOT / "vendor" / "OpenMontage" / "AGENT_GUIDE.md").exists()
    add("OpenMontage skills (nested or vendor/OpenMontage)", om,
        "git clone --depth 1 https://github.com/calesthio/OpenMontage.git vendor/OpenMontage", blocking=False)
    free = shutil.disk_usage(ROOT).free / 1e9
    add("free disk >= 10 GB", free >= 10, "free some disk space (VOD audio + renders need room)", blocking=False, info=f"{free:.0f} GB")
    add("Twitch API keys (optional)", twitch_keys(), "see .env.example", blocking=False)
    add("Kick API keys (optional)", kick_keys(), "see .env.example", blocking=False)
    add("permissions file", (ROOT / ".claude" / "settings.json").exists(),
        "copy config/permissions.suggested.json to .claude/settings.json", blocking=False)
    return res


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--quick", action="store_true"); p.add_argument("--get-model")
    a = p.parse_args()
    if a.get_model:
        get_model(a.get_model); return
    res = checks()
    if a.quick:
        bad = [r for r in res if r["blocking"] and not r["ok"]]
        print(json.dumps({"ready": not bad, "blocking_problems": bad}, indent=2)); return
    print("\n  CLIP SYSTEM DOCTOR\n  ------------------")
    for r in res:
        mark = "OK " if r["ok"] else ("XX " if r["blocking"] else "-- ")
        line = f"  [{mark}] {r['check']}" + (f"  ({r['info']})" if r["info"] else "")
        if not r["ok"]:
            line += f"\n         fix: {r['fix']}"
        print(line)
    bad = [r for r in res if r["blocking"] and not r["ok"]]
    print("\n  READY TO RUN" if not bad else f"\n  NOT READY: {len(bad)} blocking problem(s) above")


if __name__ == "__main__":
    main()
