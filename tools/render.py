"""Clip renderer: turn a gameplay section into a finished vertical short.

Features: 9:16 layouts (split facecam/gameplay, blurred fill, smart crop, letterbox),
word-by-word animated captions, hook title card, zoom "punch-ins" on key beats,
loudness normalisation (-14 LUFS, platform standard), cover image.

Usage:
  python tools/render.py frames --video sec.mp4 --out runs/<run>/frames/c01 [--count 4]
        -> PNG frames the clip-editor agent LOOKS AT to find the facecam box / action area
  python tools/render.py clip --video sec.mp4 --spec runs/<run>/specs/c01.json --out output/<...>/c01

Spec JSON (written by the clip-editor agent):
{
  "id": "c01",
  "trim": [2.5, 48.0],                 # seconds inside the section file (optional)
  "layout": "split",                   # split | blur | crop | facetrack | letterbox
  "facecam": [1480, 40, 420, 236],     # x,y,w,h in SOURCE pixels (split only)
  "face_ratio": 0.38,                  # share of the 1920 height for the facecam (split)
  "focus_x": 0.5,                      # horizontal focus 0..1 for crop / split gameplay
  "hook": "HE DIDN'T SEE THE 5TH GUY",  # top title for the first hook_seconds
  "hook_seconds": 3.0,
  "captions": true, "caption_font": "Arial Black", "highlight": "#FFE400",
  "caption_y": 0.62,                   # vertical position of captions (0 top .. 1 bottom)
  "words_per_line": 3,
  "punches": [[11.2, 12.0], [30.5, 31.3]],   # zoom punch-ins (seconds, after trim)
  "punch_zoom": 1.18,
  "language": "auto"
}
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from common import emit, exe, ffprobe_duration, log, read_json, run, write_json

W, H = 1080, 1920


def probe_size(path: Path) -> tuple[int, int]:
    out = run([exe("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=width,height", "-of", "csv=p=0", str(path)], capture=True).stdout.strip()
    w, h = out.split(",")[:2]
    return int(w), int(h)


def cmd_frames(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    dur = ffprobe_duration(Path(a.video))
    paths = []
    for i in range(a.count):
        t = dur * (i + 1) / (a.count + 1)
        p = out / f"frame_{i+1:02d}_{t:.1f}s.png"
        run([exe("ffmpeg"), "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", a.video, "-frames:v", "1", str(p)])
        paths.append(str(p))
    w, h = probe_size(Path(a.video))
    emit({"frames": paths, "source_size": [w, h], "duration": dur})


# ------------------------------------------------------------------ captions (ASS)
def ass_color(hex_rgb: str, alpha: str = "00") -> str:
    h = hex_rgb.lstrip("#")
    return f"&H{alpha}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def ts(t: float) -> str:
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(words: list[dict], spec: dict, duration: float) -> str:
    font = spec.get("caption_font", "Arial Black")
    hl = ass_color(spec.get("highlight", "#FFE400"))
    margin_v = int(H * (1 - spec.get("caption_y", 0.62)))
    hook_font = spec.get("hook_font", font)
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Cap,{font},92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,7,3,2,60,60,{margin_v},1",
        f"Style: Hook,{hook_font},78,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,22,0,8,70,70,170,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    hook = (spec.get("hook") or "").strip()
    if hook:
        hs = float(spec.get("hook_seconds", 3.0))
        lines.append(f"Dialogue: 1,{ts(0)},{ts(min(hs, duration))},Hook,,0,0,0,,"
                     f"{{\\fad(120,200)\\fscx92\\fscy92\\t(0,140,\\fscx100\\fscy100)}}{esc(hook.upper())}")
    if spec.get("captions", True) and words:
        n = max(1, int(spec.get("words_per_line", 3)))
        groups = [words[i:i + n] for i in range(0, len(words), n)]
        for gi, g in enumerate(groups):
            g_end = groups[gi + 1][0]["start"] if gi + 1 < len(groups) else g[-1]["end"] + 0.3
            g_end = min(g_end, g[-1]["end"] + 0.6)
            for wi, w in enumerate(g):
                st = w["start"]
                en = g[wi + 1]["start"] if wi + 1 < len(g) else g_end
                if en <= st:
                    continue
                parts = []
                for wj, w2 in enumerate(g):
                    word = esc(w2["word"].upper().strip(",.?!"))
                    parts.append(f"{{\\c{hl}\\fscx112\\fscy112}}{word}{{\\c&H00FFFFFF&\\fscx100\\fscy100}}"
                                 if wj == wi else word)
                pop = "{\\fscx88\\fscy88\\t(0,90,\\fscx100\\fscy100)}" if wi == 0 else ""
                lines.append(f"Dialogue: 0,{ts(st)},{ts(en)},Cap,,0,0,0,,{pop}{' '.join(parts)}")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ video graph
def layout_graph(spec: dict, sw: int, sh: int) -> str:
    layout = spec.get("layout", "blur")
    fx = float(spec.get("focus_x", 0.5))
    if layout == "split" and spec.get("facecam"):
        x, y, w, h = [int(v) for v in spec["facecam"]]
        fh = int(H * float(spec.get("face_ratio", 0.38))) // 2 * 2
        gh = H - fh
        return (f"[0:v]fps=30,split[a][b];"
                f"[a]crop={w}:{h}:{x}:{y},scale={W}:{fh}:force_original_aspect_ratio=increase,crop={W}:{fh}[cam];"
                f"[b]scale=-2:{gh},crop={W}:{gh}:(iw-{W})*{fx}:0[game];"
                f"[cam][game]vstack=inputs=2,setsar=1[v0]")
    if layout == "crop":
        return f"[0:v]fps=30,scale=-2:{H},crop={W}:{H}:(iw-{W})*{fx}:0,setsar=1[v0]"
    if layout == "letterbox":
        return f"[0:v]fps=30,scale={W}:-2,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1[v0]"
    # blur (default): enlarged gameplay over a blurred, darkened fill
    fg_w = int(W * float(spec.get("blur_fg_scale", 1.0))) // 2 * 2
    return (f"[0:v]fps=30,split[a][b];"
            f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=28,eq=brightness=-0.12[bg];"
            f"[b]scale={fg_w}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,crop={W}:{H},setsar=1[v0]")


def punch_graph(spec: dict) -> str:
    punches = spec.get("punches") or []
    if not punches:
        return "[v0]null[v1]"
    z = float(spec.get("punch_zoom", 1.18))
    cond = "+".join(f"between(it,{s:.2f},{e:.2f})" for s, e in punches)
    # zoompan with d=1 (one output frame per input frame); input is already fps=30
    return (f"[v0]zoompan=z='if({cond},{z},1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s={W}x{H}:fps=30[v1]")


def cmd_clip(a):
    spec = read_json(Path(a.spec), {})
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    src = Path(a.video).resolve()
    sw, sh = probe_size(src)
    trim = spec.get("trim")

    # 1) trimmed working copy (accurate seek, re-encode once)
    work = out / "_trim.mp4"
    cmd = [exe("ffmpeg"), "-v", "error", "-y"]
    if trim:
        cmd += ["-ss", f"{trim[0]:.2f}", "-to", f"{trim[1]:.2f}"]
    cmd += ["-i", str(src), "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-c:a", "aac", "-b:a", "192k", str(work)]
    run(cmd)
    dur = ffprobe_duration(work)

    # 1b) "facetrack" layout: face-following crop from vendor/AI-Youtube-Shorts-Generator
    if spec.get("layout") == "facetrack":
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vendor" / "AI-Youtube-Shorts-Generator"))
        from shorts_generator.local.clipper import _reframe_vertical
        tracked = out / "_tracked.mp4"
        _reframe_vertical(str(work.resolve()), str(tracked.resolve()), "9:16")
        work.unlink(missing_ok=True)
        tracked.rename(work)
        spec = {**spec, "layout": "crop", "focus_x": 0.5, "_engine": "facetrack"}

    # 2) captions from word timestamps of the trimmed clip
    words = []
    if spec.get("captions", True):
        from moments import transcribe
        from common import settings
        tr = transcribe(work, spec.get("whisper_model") or settings().get("whisper_model", "base"),
                        spec.get("language", "auto"))
        words = tr["words"]
        write_json(out / "transcript.json", tr)
    (out / "subs.ass").write_text(build_ass(words, spec, dur), encoding="utf-8")

    # 3) compose
    graph = ";".join([layout_graph(spec, sw, sh), punch_graph(spec),
                      "[v1]ass=subs.ass,format=yuv420p[v]"])
    final = out / "clip.mp4"
    run([exe("ffmpeg"), "-v", "error", "-y", "-i", work.name, "-filter_complex", graph, "-map", "[v]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", spec.get("preset", "veryfast"), "-crf", "19", "-r", "30",
         "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-movflags", "+faststart",
         final.name], cwd=out)

    # 4) cover image from the punchiest moment (or 1/3 in)
    t_cover = (spec.get("punches") or [[dur / 3]])[0][0]
    run([exe("ffmpeg"), "-v", "error", "-y", "-ss", f"{t_cover:.2f}", "-i", final.name, "-frames:v", "1",
         "-q:v", "2", "cover.jpg"], cwd=out)
    work.unlink(missing_ok=True)
    write_json(out / "spec.json", spec)
    log(f"rendered {final}")
    emit({"clip": str(final), "cover": str(out / "cover.jpg"), "duration": ffprobe_duration(final),
          "words": len(words), "layout": spec.get("layout", "blur")})


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("frames"); s.add_argument("--video", required=True); s.add_argument("--out", required=True)
    s.add_argument("--count", type=int, default=4); s.set_defaults(fn=cmd_frames)
    s = sub.add_parser("clip"); s.add_argument("--video", required=True); s.add_argument("--spec", required=True)
    s.add_argument("--out", required=True); s.set_defaults(fn=cmd_clip)
    a = p.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
