"""Moment finder: locate the hype moments inside a long stream recording.

Pipeline (CPU friendly):
  1. Decode audio to 8 kHz mono, compute loudness per second.
  2. Score "excitement" = loudness above the local baseline (rolling median),
     smoothed + sustained-energy bonus.  Streamers yell / chat-alert / music
     stings at highlights, so this finds clutches, fails, rage, laughs fast.
  3. Pick the top-K peaks (spaced apart), transcribe ONLY those windows with
     faster-whisper (word timestamps), boost windows with hype phrases.
  4. Write candidates.json -> the moment-hunter agent reads it and picks clips.

Usage:
  python tools/moments.py scan --audio runs/<run>/sources/x.m4a --out runs/<run>/candidates/x.json
        [--top 12] [--offset 0] [--url <vod url>] [--model base] [--lang auto]
  python tools/moments.py transcribe --media clip.mp4 --out words.json [--model base] [--lang auto]
"""
from __future__ import annotations

import argparse
import os
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
import re
import subprocess
from pathlib import Path

import numpy as np

from common import emit, exe, log, settings, write_json

SR = 8000
HYPE = [r"let'?s go+", r"oh my god", r"no way", r"what the", r"wtf", r"holy", r"clutch", r"ace", r"insane",
        r"are you kidding", r"bro+", r"oh no", r"lmao", r"lol", r"dude", r"crazy", r"shut up", r"yes+",
        r"no+ ?no+", r"how\??", r"one tap", r"1v[2-5]", r"gg", r"rage", r"chat", r"i'?m done", r"oh shit"]


def loudness_curve(audio: Path) -> np.ndarray:
    """Per-second RMS loudness in dB, streamed so multi-hour files fit in memory."""
    proc = subprocess.Popen([exe("ffmpeg"), "-v", "error", "-i", str(audio), "-ac", "1", "-ar", str(SR),
                             "-f", "s16le", "-"], stdout=subprocess.PIPE)
    out = []
    chunk = SR * 2 * 60  # 60 s of int16
    buf = b""
    while True:
        data = proc.stdout.read(chunk)
        if not data:
            break
        buf += data
        n = len(buf) // (SR * 2)
        if n:
            arr = np.frombuffer(buf[: n * SR * 2], dtype=np.int16).astype(np.float32).reshape(n, SR)
            rms = np.sqrt(np.mean(arr ** 2, axis=1)) + 1e-6
            out.append(20 * np.log10(rms / 32768.0))
            buf = buf[n * SR * 2:]
    proc.wait()
    return np.concatenate(out) if out else np.zeros(0)


def rolling(x: np.ndarray, win: int, fn) -> np.ndarray:
    pad = win // 2
    xp = np.pad(x, pad, mode="edge")
    from numpy.lib.stride_tricks import sliding_window_view
    return fn(sliding_window_view(xp, win), axis=1)[: len(x)]


def score_curve(db: np.ndarray) -> np.ndarray:
    db = np.maximum(db, -70)
    base = rolling(db, min(301, max(31, len(db) // 4 * 2 + 1)), np.median)
    excess = np.clip(db - base, 0, None)
    short = rolling(excess, 3, np.mean)
    sustained = rolling(excess, 15, np.mean)
    return short + 0.6 * sustained


def pick_peaks(score: np.ndarray, top: int, gap: int, edge: int) -> list[int]:
    order = np.argsort(score)[::-1]
    chosen: list[int] = []
    for i in order:
        if i < edge or i > len(score) - 5:
            continue
        if all(abs(i - c) >= gap for c in chosen):
            chosen.append(int(i))
        if len(chosen) >= top:
            break
    return sorted(chosen)


_MODEL = {}


def whisper(model: str):
    if model not in _MODEL:
        from faster_whisper import WhisperModel
        log(f"loading faster-whisper '{model}' (cpu int8)")
        local = Path(__file__).resolve().parent.parent / "models" / f"whisper-{model}"
        if (local / ".complete").exists():
            _MODEL[model] = WhisperModel(str(local), device="cpu", compute_type="int8")
            return _MODEL[model]
        try:  # cached copy first: avoids a slow/blocked HuggingFace network check
            _MODEL[model] = WhisperModel(model, device="cpu", compute_type="int8", local_files_only=True)
        except Exception:  # noqa: BLE001
            log("model not cached yet -> downloading once")
            _MODEL[model] = WhisperModel(model, device="cpu", compute_type="int8")
    return _MODEL[model]


def transcribe(media: Path, model: str, lang: str | None, start: float | None = None,
               end: float | None = None) -> dict:
    """Transcribe a file (or a [start,end] window of it). Times are absolute in the file."""
    src = media
    tmp = None
    if start is not None:
        tmp = media.parent / f".win_{int(start)}_{int(end)}.wav"
        subprocess.run([exe("ffmpeg"), "-v", "error", "-y", "-ss", str(start), "-to", str(end), "-i", str(media),
                        "-ac", "1", "-ar", "16000", str(tmp)], check=True)
        src = tmp
    segs, info = whisper(model).transcribe(str(src), language=None if lang in (None, "auto") else lang,
                                           word_timestamps=True, vad_filter=True, beam_size=1)
    off = start or 0.0
    words, segments = [], []
    for s in segs:
        segments.append({"start": round(s.start + off, 2), "end": round(s.end + off, 2), "text": s.text.strip()})
        for w in s.words or []:
            words.append({"start": round(w.start + off, 2), "end": round(w.end + off, 2), "word": w.word.strip()})
    if tmp:
        tmp.unlink(missing_ok=True)
    return {"language": info.language, "segments": segments, "words": words}


def hype_hits(text: str) -> list[str]:
    t = text.lower()
    return [h for h in HYPE if re.search(r"\b" + h, t)]


def cmd_scan(a):
    st = settings()
    audio = Path(a.audio)
    log(f"loudness scan: {audio.name}")
    db = loudness_curve(audio)
    if len(db) < 30:
        emit({"error": "audio too short", "seconds": len(db)})
        return
    sc = score_curve(db)
    peaks = pick_peaks(sc, a.top, gap=a.gap, edge=a.pre)
    log(f"{len(db)/3600:.2f}h scanned, {len(peaks)} peaks; transcribing windows")
    cands = []
    for p in peaks:
        ws, we = max(0, p - a.pre), min(len(db), p + a.post)
        tr = transcribe(audio, a.model or st.get("whisper_model", "base"), a.lang, ws, we)
        text = " ".join(s["text"] for s in tr["segments"])
        hits = hype_hits(text)
        energy = float(sc[p])
        cands.append({
            "peak": p + a.offset, "window_start": ws + a.offset, "window_end": we + a.offset,
            "energy": round(energy, 2), "hype_words": hits,
            "score": round(energy + 1.5 * len(hits) + (2 if len(text) > 40 else 0), 2),
            "language": tr["language"], "text": text,
            "segments": [{**s, "start": s["start"] + a.offset, "end": s["end"] + a.offset} for s in tr["segments"]],
        })
    cands.sort(key=lambda c: c["score"], reverse=True)
    # loudness timeline at 10 s resolution so the agent can see the stream's shape
    timeline = [round(float(sc[i:i + 10].max()), 1) for i in range(0, len(sc), 10)]
    res = {"audio": str(audio), "url": a.url, "offset": a.offset, "seconds": len(db),
           "candidates": cands, "timeline_10s": timeline}
    write_json(Path(a.out), res)
    emit({"saved_to": a.out, "seconds": len(db),
          "candidates": [{k: c[k] for k in ("peak", "window_start", "window_end", "score", "hype_words")} |
                         {"text": c["text"][:160]} for c in cands]})


def cmd_transcribe(a):
    tr = transcribe(Path(a.media), a.model or settings().get("whisper_model", "base"), a.lang)
    write_json(Path(a.out), tr)
    emit({"saved_to": a.out, "language": tr["language"], "words": len(tr["words"]),
          "text": " ".join(s["text"] for s in tr["segments"])[:500]})


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("--audio", required=True); s.add_argument("--out", required=True)
    s.add_argument("--top", type=int, default=12); s.add_argument("--offset", type=float, default=0)
    s.add_argument("--url"); s.add_argument("--model"); s.add_argument("--lang", default="auto")
    s.add_argument("--pre", type=int, default=45, help="seconds before peak to transcribe")
    s.add_argument("--post", type=int, default=30, help="seconds after peak to transcribe")
    s.add_argument("--gap", type=int, default=90, help="min seconds between peaks")
    s.set_defaults(fn=cmd_scan)
    s = sub.add_parser("transcribe"); s.add_argument("--media", required=True); s.add_argument("--out", required=True)
    s.add_argument("--model"); s.add_argument("--lang", default="auto"); s.set_defaults(fn=cmd_transcribe)
    a = p.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
