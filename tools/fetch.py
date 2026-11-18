"""Source fetcher: VOD audio for analysis, video sections for clips, and live recording.

Strategy (keeps disk + time low on a CPU-only machine):
  1. `audio`   -> download ONLY the audio of a long VOD (small), analyse it with moments.py
  2. `section` -> download ONLY the video windows that contain the chosen moments
  3. `live`    -> record a live stream for N minutes with streamlink (then same as 1-2 on the file)

Usage:
  python tools/fetch.py audio   --url <vod url> --out runs/<run>/sources [--max-hours 4] [--from-end]
  python tools/fetch.py section --url <vod url> --start 3725 --end 3800 --out runs/<run>/sections/c01.mp4 [--height 1080]
  python tools/fetch.py live    --url https://www.twitch.tv/<ch> --minutes 60 --out runs/<run>/sources
  python tools/fetch.py file    --url <short clip url> --out runs/<run>/sources       (whole file, e.g. a Twitch clip)
  python tools/fetch.py seen    --url <vod url>      (has this VOD already been processed?)
  python tools/fetch.py mark    --url <vod url> --run <run id>

All media paths are printed as JSON on stdout.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import DATA, emit, exe, ffprobe_duration, log, now_iso, read_json, run, slug, write_json

LEDGER = DATA / "processed.json"


def meta(url: str) -> dict:
    res = run([exe("yt-dlp"), "-J", "--no-warnings", "--no-playlist", url], capture=True, check=False, timeout=180)
    try:
        d = json.loads(res.stdout or "{}")
    except json.JSONDecodeError:
        d = {}
    return {"id": d.get("id"), "title": d.get("title"), "duration": d.get("duration"),
            "uploader": d.get("uploader") or d.get("channel"), "is_live": d.get("is_live"),
            "extractor": d.get("extractor_key")}


def cmd_audio(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    m = meta(a.url)
    dur = m.get("duration") or 0
    name = slug(f"{m.get('uploader') or 'src'}-{m.get('id') or 'vod'}")
    target = out / f"{name}.m4a"
    cmd = [exe("yt-dlp"), "--no-warnings", "--no-playlist", "-f", "bestaudio/worst",
           "-x", "--audio-format", "m4a", "--audio-quality", "5",
           "--ffmpeg-location", str(Path(exe("ffmpeg")).parent), "-o", str(out / f"{name}.%(ext)s")]
    offset = 0
    if dur and a.max_hours and dur > a.max_hours * 3600:
        span = int(a.max_hours * 3600)
        offset = int(dur - span) if a.from_end else 0
        cmd += ["--download-sections", f"*{offset}-{offset + span}"]
        log(f"VOD is {dur/3600:.1f}h; analysing {a.max_hours}h window starting at {offset}s")
    run(cmd + [a.url], timeout=6 * 3600)
    emit({"audio": str(target), "offset": offset, "duration": ffprobe_duration(target), "meta": m, "url": a.url})


def cmd_section(a):
    outp = Path(a.out); outp.parent.mkdir(parents=True, exist_ok=True)
    fmt = f"bv*[height<={a.height}]+ba/b[height<={a.height}]/best"
    run([exe("yt-dlp"), "--no-warnings", "--no-playlist", "-f", fmt,
         "--download-sections", f"*{a.start}-{a.end}", "--force-keyframes-at-cuts",
         "--merge-output-format", "mp4", "--ffmpeg-location", str(Path(exe("ffmpeg")).parent),
         "-o", str(outp), a.url], timeout=3600)
    emit({"video": str(outp), "start": a.start, "end": a.end, "duration": ffprobe_duration(outp)})


def cmd_local_section(a):
    """Cut a section from a local file (e.g. a live recording)."""
    outp = Path(a.out); outp.parent.mkdir(parents=True, exist_ok=True)
    run([exe("ffmpeg"), "-y", "-ss", str(a.start), "-to", str(a.end), "-i", a.input,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", str(outp)])
    emit({"video": str(outp), "start": a.start, "end": a.end, "duration": ffprobe_duration(outp)})


def cmd_live(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    name = slug(a.url.rstrip("/").split("/")[-1]) + f"-live-{now_iso()[:16].replace(':', '')}"
    target = out / f"{name}.ts"
    hh, mm = divmod(int(a.minutes), 60)
    res = run([exe("streamlink"), "--hls-duration", f"{hh:02d}:{mm:02d}:00", "--retry-open", "3",
               "-o", str(target), a.url, a.quality], check=False, timeout=a.minutes * 60 + 600)
    if res.returncode != 0 or not target.exists():
        emit({"error": "recording failed (channel offline?)", "url": a.url})
        return
    mp4 = target.with_suffix(".mp4")
    run([exe("ffmpeg"), "-y", "-i", str(target), "-c", "copy", str(mp4)], check=False)
    final = mp4 if mp4.exists() and mp4.stat().st_size > 0 else target
    if final == mp4:
        target.unlink(missing_ok=True)
    audio = final.with_suffix(".m4a")
    run([exe("ffmpeg"), "-y", "-i", str(final), "-vn", "-c:a", "aac", "-b:a", "128k", str(audio)])
    emit({"video": str(final), "audio": str(audio), "offset": 0, "duration": ffprobe_duration(final), "url": a.url})


def cmd_file(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    res = run([exe("yt-dlp"), "--no-warnings", "--no-playlist", "-f", "bv*[height<=1080]+ba/b",
               "--merge-output-format", "mp4", "--ffmpeg-location", str(Path(exe("ffmpeg")).parent),
               "--print", "after_move:filepath", "-o", str(out / "%(uploader)s-%(id)s.%(ext)s"), a.url],
              capture=True, timeout=3600)
    path = (res.stdout or "").strip().splitlines()[-1]
    emit({"video": path, "duration": ffprobe_duration(Path(path))})


def cmd_seen(a):
    led = read_json(LEDGER, {}) or {}
    emit({"url": a.url, "seen": a.url in led, "info": led.get(a.url)})


def cmd_mark(a):
    led = read_json(LEDGER, {}) or {}
    led[a.url] = {"run": a.run, "at": now_iso()}
    write_json(LEDGER, led)
    emit({"marked": a.url})


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("audio"); s.add_argument("--url", required=True); s.add_argument("--out", required=True)
    s.add_argument("--max-hours", type=float, default=4); s.add_argument("--from-end", action="store_true")
    s.set_defaults(fn=cmd_audio)
    s = sub.add_parser("section"); s.add_argument("--url", required=True); s.add_argument("--start", type=float, required=True)
    s.add_argument("--end", type=float, required=True); s.add_argument("--out", required=True)
    s.add_argument("--height", type=int, default=1080); s.set_defaults(fn=cmd_section)
    s = sub.add_parser("local-section"); s.add_argument("--input", required=True)
    s.add_argument("--start", type=float, required=True); s.add_argument("--end", type=float, required=True)
    s.add_argument("--out", required=True); s.set_defaults(fn=cmd_local_section)
    s = sub.add_parser("live"); s.add_argument("--url", required=True); s.add_argument("--minutes", type=int, default=60)
    s.add_argument("--quality", default="best"); s.add_argument("--out", required=True); s.set_defaults(fn=cmd_live)
    s = sub.add_parser("file"); s.add_argument("--url", required=True); s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_file)
    s = sub.add_parser("seen"); s.add_argument("--url", required=True); s.set_defaults(fn=cmd_seen)
    s = sub.add_parser("mark"); s.add_argument("--url", required=True); s.add_argument("--run", required=True)
    s.set_defaults(fn=cmd_mark)
    a = p.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
