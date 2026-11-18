"""Trend collector: what clips/shorts are performing right now for a game.

Collects raw signals (no keys needed); the trend-analyst agent turns them into insights.
  - YouTube Shorts + clips about the game (recent uploads, ranked by views)
  - Twitch top clips of the last N days (only if Twitch keys are set)

Usage:
  python tools/trends.py collect --game "VALORANT" [--limit 40] [--days 3]

Writes data/trends/<game>_<date>.json and prints a compact summary on stdout.
"""
from __future__ import annotations

import argparse
import re
from collections import Counter
from urllib.parse import quote_plus

from common import DATA, emit, game_entry, log, slug, today, twitch_keys, write_json
from scout import twitch_top_clips, ytdlp_flat

STOP = set("the a an and or of to in on for with is it this that my i you me we he she they at by from be are was "
           "his her their our your just so not no but get got what when how why who all out up new vs".split())


def yt_search(query: str, limit: int, sp: str | None) -> list[dict]:
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}" + (f"&sp={sp}" if sp else "")
    rows = []
    for e in ytdlp_flat(url, limit):
        rows.append({"platform": "youtube", "id": e.get("id"), "title": e.get("title") or "",
                     "views": e.get("view_count") or 0, "duration": e.get("duration"),
                     "channel": e.get("channel") or e.get("uploader"),
                     "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
                     "is_short": "/shorts/" in (e.get("url") or "") or (e.get("duration") or 999) <= 60})
    return rows


def title_patterns(titles: list[str]) -> dict:
    words = Counter()
    for t in titles:
        for w in re.findall(r"[a-zA-Z0-9']+", t.lower()):
            if w not in STOP and len(w) > 2:
                words[w] += 1
    caps = sum(1 for t in titles if sum(c.isupper() for c in t) > len(t) * 0.4)
    emoji = sum(1 for t in titles if re.search(r"[\U0001F300-\U0001FAFF]", t))
    return {"top_words": words.most_common(30),
            "share_all_caps": round(caps / max(len(titles), 1), 2),
            "share_with_emoji": round(emoji / max(len(titles), 1), 2),
            "avg_title_len": round(sum(map(len, titles)) / max(len(titles), 1), 1)}


def cmd_collect(a):
    g = game_entry(a.game)
    q = g.get("youtube_query") or g["name"]
    # sp=EgQIAxAB -> uploaded this week + type video;  CAMSAhAB -> sort by views
    shorts = yt_search(f"{q} shorts", a.limit, "EgQIAxAB")
    clips = yt_search(f"{q} stream highlights", a.limit, "EgQIAxAB")
    seen, yt = set(), []
    for r in shorts + clips:
        if r["id"] not in seen:
            seen.add(r["id"]); yt.append(r)
    yt.sort(key=lambda r: r["views"], reverse=True)

    tw = []
    if twitch_keys():
        try:
            tw = twitch_top_clips(g.get("twitch") or g["name"], a.days, a.limit)
        except Exception as e:  # noqa: BLE001
            log(f"twitch clips failed: {e}")

    all_titles = [r["title"] for r in yt[:30]] + [r["title"] for r in tw[:30]]
    chan = Counter(r["channel"] for r in yt + tw if r.get("channel"))
    result = {
        "game": g["name"], "date": today(),
        "youtube_top": yt[:a.limit], "twitch_top_clips": tw,
        "patterns": title_patterns(all_titles),
        "most_clipped_channels": chan.most_common(15),
        "avg_short_duration": round(sum((r["duration"] or 0) for r in yt if r["is_short"]) /
                                    max(sum(1 for r in yt if r["is_short"]), 1), 1),
    }
    path = write_json(DATA / "trends" / f"{slug(g['name'])}_{today()}.json", result)
    emit({"saved_to": str(path), "youtube_items": len(yt), "twitch_clips": len(tw),
          "top5": [(r["views"], r["title"]) for r in yt[:5]],
          "patterns": result["patterns"], "most_clipped_channels": result["most_clipped_channels"][:8]})


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("collect"); s.add_argument("--game", required=True)
    s.add_argument("--limit", type=int, default=40); s.add_argument("--days", type=int, default=3)
    s.set_defaults(fn=cmd_collect)
    a = p.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
