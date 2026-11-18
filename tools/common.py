"""Shared helpers for the clipping system tools.

All tools are plain CLIs run through the portable launcher:
    bin/py tools/<tool>.py --help        (bash)      bin\\py.bat tools\\<tool>.py --help   (cmd)
Works standalone (clipping/.venv) or inside OpenMontage (../.venv).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # .../clipping
OM_ROOT = ROOT.parent                                   # parent (OpenMontage when nested)
# the venv that is running us first, then clipping/.venv, then ../.venv
VENV_DIRS = [Path(sys.executable).parent, ROOT / ".venv" / "Scripts", ROOT / ".venv" / "bin",
             OM_ROOT / ".venv" / "Scripts", OM_ROOT / ".venv" / "bin"]
DATA = ROOT / "data"
RUNS = ROOT / "runs"
OUTPUT = ROOT / "output"
CONFIG = ROOT / "config"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def load_env() -> None:
    """Load KEY=VALUE pairs from OpenMontage/.env and clipping/.env (no overrides)."""
    for f in (OM_ROOT / ".env", ROOT / ".env"):
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip().strip('"').strip("'")
            if v and not os.environ.get(k.strip()):
                os.environ[k.strip()] = v


load_env()


def exe(name: str) -> str:
    """Resolve a binary, preferring the OpenMontage venv."""
    for d in VENV_DIRS:
        for cand in (d / f"{name}.exe", d / name):
            if cand.exists():
                return str(cand)
    found = shutil.which(name)
    if not found:
        sys.exit(f"[error] '{name}' not found. Install it (see clipping/README.md).")
    return found


def run(cmd: list[str], cwd: Path | None = None, check: bool = True,
        capture: bool = False, timeout: float | None = None) -> subprocess.CompletedProcess:
    log(" ".join(str(c) for c in cmd)[:400])
    return subprocess.run([str(c) for c in cmd], cwd=cwd, check=check, timeout=timeout,
                          capture_output=capture, text=capture, encoding="utf-8" if capture else None,
                          errors="replace" if capture else None)


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def slug(text: str, maxlen: int = 60) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return s[:maxlen] or "item"


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, obj) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def http_json(url: str, data: dict | list | None = None, headers: dict | None = None,
              retries: int = 2, timeout: float = 20):
    hdrs = {"User-Agent": UA, "Accept": "application/json"}
    hdrs.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        hdrs["Content-Type"] = "application/json"
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"request failed: {url}: {last}")


_TOKENS: dict[str, str] = {}


def _client_credentials(token_url: str, cid: str, secret: str) -> str:
    from urllib.parse import urlencode
    body = urlencode({"client_id": cid, "client_secret": secret,
                      "grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(token_url, data=body, headers={
        "User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())["access_token"]


def twitch_keys() -> tuple[str, str] | None:
    cid, sec = os.environ.get("TWITCH_CLIENT_ID"), os.environ.get("TWITCH_CLIENT_SECRET")
    return (cid, sec) if cid and sec else None


def helix(path: str, **params):
    """Official Twitch Helix API (free keys from dev.twitch.tv/console)."""
    from urllib.parse import urlencode
    keys = twitch_keys()
    if not keys:
        raise RuntimeError("TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET not set")
    if "twitch" not in _TOKENS:
        _TOKENS["twitch"] = _client_credentials("https://id.twitch.tv/oauth2/token", *keys)
    q = urlencode([(k, v) for k, vals in params.items() if vals is not None
                   for v in (vals if isinstance(vals, list) else [vals])])
    return http_json(f"https://api.twitch.tv/helix/{path}?{q}", headers={
        "Client-ID": keys[0], "Authorization": f"Bearer {_TOKENS['twitch']}"})


def kick_keys() -> tuple[str, str] | None:
    cid, sec = os.environ.get("KICK_CLIENT_ID"), os.environ.get("KICK_CLIENT_SECRET")
    return (cid, sec) if cid and sec else None


def kick_api(path: str, **params):
    """Official Kick public API (free app keys from kick.com developer settings)."""
    from urllib.parse import urlencode
    keys = kick_keys()
    if not keys:
        raise RuntimeError("KICK_CLIENT_ID / KICK_CLIENT_SECRET not set")
    if "kick" not in _TOKENS:
        _TOKENS["kick"] = _client_credentials("https://id.kick.com/oauth/token", *keys)
    q = urlencode({k: v for k, v in params.items() if v is not None})
    return http_json(f"https://api.kick.com/public/v1/{path}?{q}",
                     headers={"Authorization": f"Bearer {_TOKENS['kick']}"})


def games_config() -> dict:
    return read_json(CONFIG / "games.json", {}) or {}


def settings() -> dict:
    return read_json(CONFIG / "settings.json", {}) or {}


def game_entry(game: str) -> dict:
    """Look up a game in config/games.json (case-insensitive), else build defaults."""
    cfg = games_config()
    for key, val in cfg.items():
        if key.lower() == game.lower() or game.lower() in [a.lower() for a in val.get("aliases", [])]:
            return {"name": key, **val}
    return {"name": game, "twitch": game, "kick": slug(game), "youtube_query": game}


def ffprobe_duration(path: Path) -> float:
    out = run([exe("ffprobe"), "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)], capture=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


def emit(obj) -> None:
    """Print a JSON result on stdout (agents parse this)."""
    print(json.dumps(obj, indent=2, ensure_ascii=False))
