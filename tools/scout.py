"""Streamer scout: find the biggest streamers for a game on Twitch, YouTube and Kick.

Data sources (official / public only):
  - Twitch: official Helix API  -> needs TWITCH_CLIENT_ID + TWITCH_CLIENT_SECRET (free, dev.twitch.tv)
  - Kick:   official public API -> needs KICK_CLIENT_ID + KICK_CLIENT_SECRET (free, kick.com dev settings)
  - YouTube: yt-dlp search of live streams (no key)
  - Without Twitch/Kick keys, the watchlist in config/games.json is used instead
    (the streamer-scout agent fills it with web research).

Usage:
  python tools/scout.py live  --game "VALORANT" [--limit 25] [--platforms twitch,youtube,kick]
  python tools/scout.py vods  --platform twitch|youtube|kick --channel <login|slug|channel URL> [--limit 5]
  python tools/scout.py clips --game "VALORANT" [--days 1] [--limit 30]      (Twitch, needs keys)
  python tools/scout.py watch --game "VALORANT" --add twitch:tenz youtube:https://www.youtube.com/@x
  python tools/scout.py status

Writes data/streamers/<game>_<date>.json (for `live`) and prints JSON on stdout.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

from common import (CONFIG, DATA, emit, exe, game_entry, games_config, helix, kick_api,
                    kick_keys, log, now_iso, read_json, run, slug, today, twitch_keys,
                    write_json)


# ---------------------------------------------------------------- yt-dlp helpers (no keys)
def ytdlp_flat(url: str, limit: int) -> list[dict]:
    res = run([exe("yt-dlp"), "--flat-playlist", "-J", "--playlist-end", str(limit),
               "--no-warnings", url], capture=True, check=False, timeout=180)
    if res.returncode != 0 or not (res.stdout or "").strip():
        log(f"yt-dlp listing failed for {url}: {(res.stderr or '')[-300:]}")
        return []
    try:
        return json.loads(res.stdout).get("entries") or []
    except json.JSONDecodeError:
        return []


def is_live(url: str) -> bool:
    """Check if a channel is live right now with streamlink (no download)."""
    res = run([exe("streamlink"), "--json", url], capture=True, check=False, timeout=60)
    try:
        return bool(json.loads(res.stdout or "{}").get("streams"))
    except json.JSONDecodeError:
        return False


# ---------------------------------------------------------------- Twitch (official Helix)
def twitch_game_id(name: str) -> tuple[str, str] | None:
    data = helix("games", name=name).get("data") or []
    if not data:
        data = helix("search/categories", query=name, first=5).get("data") or []
    return (data[0]["id"], data[0]["name"]) if data else None


def twitch_live(game: str, limit: int) -> list[dict]:
    gid = twitch_game_id(game)
    if not gid:
        log(f"twitch: category '{game}' not found")
        return []
    rows = helix("streams", game_id=gid[0], first=min(limit, 100), type="live").get("data") or []
    return [{
        "platform": "twitch", "channel": r["user_login"], "name": r["user_name"],
        "viewers": r["viewer_count"], "title": r["title"], "language": r["language"],
        "started": r["started_at"], "url": f"https://www.twitch.tv/{r['user_login']}", "live": True,
    } for r in rows]


def twitch_vods(channel: str, limit: int) -> list[dict]:
    if twitch_keys():
        users = helix("users", login=channel).get("data") or []
        if not users:
            return []
        rows = helix("videos", user_id=users[0]["id"], type="archive", first=limit).get("data") or []
        return [{"platform": "twitch", "channel": channel, "id": v["id"], "title": v["title"],
                 "duration": v["duration"], "views": v["view_count"], "created": v["created_at"],
                 "url": v["url"]} for v in rows]
    # keyless: yt-dlp lists the channel's past broadcasts page
    return [{"platform": "twitch", "channel": channel, "id": e.get("id"), "title": e.get("title"),
             "duration": e.get("duration"), "views": e.get("view_count"),
             "url": e.get("url") or f"https://www.twitch.tv/videos/{str(e.get('id', '')).lstrip('v')}"}
            for e in ytdlp_flat(f"https://www.twitch.tv/{channel}/videos?filter=archives&sort=time", limit)]


def twitch_top_clips(game: str, days: int, limit: int) -> list[dict]:
    gid = twitch_game_id(game)
    if not gid:
        return []
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = helix("clips", game_id=gid[0], started_at=start, first=min(limit, 100)).get("data") or []
    rows.sort(key=lambda r: r["view_count"], reverse=True)
    return [{"platform": "twitch", "id": r["id"], "title": r["title"], "views": r["view_count"],
             "duration": r["duration"], "created": r["created_at"], "language": r["language"],
             "channel": r["broadcaster_name"], "url": r["url"]} for r in rows]


# ---------------------------------------------------------------- Kick (official public API)
def kick_live(game: str, limit: int) -> list[dict]:
    cats = kick_api("categories", q=game).get("data") or []
    if not cats:
        log(f"kick: category '{game}' not found")
        return []
    rows = kick_api("livestreams", category_id=cats[0]["id"], limit=min(limit, 100),
                    sort="viewer_count").get("data") or []
    return [{
        "platform": "kick", "channel": r.get("slug"), "name": r.get("slug"),
        "viewers": r.get("viewer_count", 0), "title": r.get("stream_title"),
        "language": r.get("language"), "started": r.get("started_at"),
        "url": f"https://kick.com/{r.get('slug')}", "live": True,
    } for r in rows]


def kick_vods(channel: str, limit: int) -> list[dict]:
    return [{"platform": "kick", "channel": channel, "id": e.get("id"), "title": e.get("title"),
             "duration": e.get("duration"), "url": e.get("url")}
            for e in ytdlp_flat(f"https://kick.com/{channel}/videos", limit)]


# ---------------------------------------------------------------- YouTube (yt-dlp)
def youtube_live(query: str, limit: int) -> list[dict]:
    from urllib.parse import quote_plus
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp=EgJAAQ%253D%253D"  # filter: Live
    return [{
        "platform": "youtube", "channel": e.get("channel_url") or e.get("channel_id"),
        "name": e.get("channel") or e.get("uploader"),
        "viewers": e.get("concurrent_view_count") or e.get("view_count") or 0,
        "title": e.get("title"), "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
        "live": True,
    } for e in ytdlp_flat(url, limit)]


def youtube_channel_vods(channel_url: str, limit: int) -> list[dict]:
    if not channel_url.startswith("http"):
        channel_url = f"https://www.youtube.com/{channel_url if channel_url.startswith('@') else '@' + channel_url}"
    return [{"platform": "youtube", "id": e.get("id"), "title": e.get("title"),
             "duration": e.get("duration"), "views": e.get("view_count"),
             "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}"}
            for e in ytdlp_flat(channel_url.rstrip("/") + "/streams", limit)]


def channel_url(platform: str, channel: str) -> str:
    if channel.startswith("http"):
        return channel
    return {"twitch": f"https://www.twitch.tv/{channel}", "kick": f"https://kick.com/{channel}",
            "youtube": f"https://www.youtube.com/@{channel.lstrip('@')}"}[platform]


# ---------------------------------------------------------------- commands
def cmd_live(a):
    g = game_entry(a.game)
    rows, notes = [], []
    if "twitch" in a.platforms:
        if twitch_keys():
            try:
                rows += twitch_live(g.get("twitch") or g["name"], a.limit)
            except Exception as e:  # noqa: BLE001
                notes.append(f"twitch api error: {e}")
        else:
            notes.append("twitch: no API keys -> using watchlist")
    if "kick" in a.platforms:
        if kick_keys():
            try:
                rows += kick_live(g.get("kick_category") or g["name"], a.limit)
            except Exception as e:  # noqa: BLE001
                notes.append(f"kick api error: {e}")
        else:
            notes.append("kick: no API keys -> using watchlist")
    if "youtube" in a.platforms:
        rows += youtube_live(f"{g.get('youtube_query') or g['name']} live", a.limit)

    # watchlist channels for platforms we could not query officially
    have = {(r["platform"], r["channel"]) for r in rows}
    for w in g.get("watchlist", []):
        p, ch = w["platform"], w["channel"]
        if p not in a.platforms or (p, ch) in have:
            continue
        if (p == "twitch" and twitch_keys()) or (p == "kick" and kick_keys()):
            continue
        url = channel_url(p, ch)
        live = is_live(url) if a.check_live else None
        rows.append({"platform": p, "channel": ch, "name": w.get("name", ch), "viewers": w.get("avg_viewers", 0),
                     "url": url, "live": live, "source": "watchlist"})

    rows.sort(key=lambda r: (bool(r.get("live")), r.get("viewers") or 0), reverse=True)

    idx_path = DATA / "streamers" / "index.json"
    idx = read_json(idx_path, {}) or {}
    for r in rows:
        key = f"{r['platform']}:{r['channel']}"
        e = idx.setdefault(key, {"platform": r["platform"], "channel": r["channel"], "name": r.get("name"),
                                 "url": r["url"], "games": {}, "peak_viewers": 0})
        e["games"][g["name"]] = now_iso()
        e["peak_viewers"] = max(e.get("peak_viewers") or 0, r.get("viewers") or 0)
        e["last_seen"] = now_iso()
    write_json(idx_path, idx)

    result = {"game": g["name"], "date": today(), "count": len(rows), "notes": notes,
              "by_platform": {p: sum(1 for r in rows if r["platform"] == p) for p in ("twitch", "youtube", "kick")},
              "streamers": rows}
    result["saved_to"] = str(write_json(DATA / "streamers" / f"{slug(g['name'])}_{today()}.json", result))
    emit(result)


def cmd_vods(a):
    fn = {"twitch": twitch_vods, "youtube": youtube_channel_vods, "kick": kick_vods}[a.platform]
    emit({"platform": a.platform, "channel": a.channel, "vods": fn(a.channel, a.limit)})


def cmd_clips(a):
    if not twitch_keys():
        emit({"error": "twitch top clips need TWITCH_CLIENT_ID/SECRET; use trends.py youtube instead"})
        return
    g = game_entry(a.game)
    emit({"game": g["name"], "days": a.days, "clips": twitch_top_clips(g.get("twitch") or g["name"], a.days, a.limit)})


def cmd_watch(a):
    """Add channels to a game's watchlist in config/games.json."""
    cfg = games_config()
    g = game_entry(a.game)
    entry = cfg.setdefault(g["name"], {k: v for k, v in g.items() if k != "name"})
    wl = entry.setdefault("watchlist", [])
    for item in a.add:
        p, ch = item.split(":", 1)
        if not any(w["platform"] == p and w["channel"] == ch for w in wl):
            wl.append({"platform": p, "channel": ch, "added": today(), **({"note": a.note} if a.note else {})})
    write_json(CONFIG / "games.json", cfg)
    emit({"game": g["name"], "watchlist": wl})


def cmd_status(_a):
    emit({"twitch_keys": bool(twitch_keys()), "kick_keys": bool(kick_keys()),
          "games": {k: len(v.get("watchlist", [])) for k, v in games_config().items()}})


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("live"); s.add_argument("--game", required=True); s.add_argument("--limit", type=int, default=25)
    s.add_argument("--platforms", default="twitch,youtube,kick")
    s.add_argument("--check-live", action="store_true", help="probe watchlist channels with streamlink")
    s.set_defaults(fn=cmd_live)
    s = sub.add_parser("vods"); s.add_argument("--platform", choices=["twitch", "youtube", "kick"], required=True)
    s.add_argument("--channel", required=True); s.add_argument("--limit", type=int, default=5); s.set_defaults(fn=cmd_vods)
    s = sub.add_parser("clips"); s.add_argument("--game", required=True); s.add_argument("--days", type=int, default=1)
    s.add_argument("--limit", type=int, default=30); s.set_defaults(fn=cmd_clips)
    s = sub.add_parser("watch"); s.add_argument("--game", required=True); s.add_argument("--add", nargs="+", required=True)
    s.add_argument("--note"); s.set_defaults(fn=cmd_watch)
    s = sub.add_parser("status"); s.set_defaults(fn=cmd_status)
    a = p.parse_args()
    if hasattr(a, "platforms"):
        a.platforms = [x.strip() for x in a.platforms.split(",")]
    a.fn(a)


if __name__ == "__main__":
    main()
