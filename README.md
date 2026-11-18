# 🎮 Clipping: an autonomous gaming-clips system (100% free)

Pick a game and press run. Six AI agents find the biggest streamers, study what's trending, watch and record streams, pick the best moments, write the hooks and titles, edit vertical 9:16 clips with captions and motion, check them, and leave a **ready-to-post folder**.

- **Free:** yt-dlp, streamlink, FFmpeg, local Whisper and open-source engines. No paid APIs.
- **No GPU needed:** runs on a normal Windows PC.
- **Never posts anything:** you upload the finished clips yourself.

---

## 🚀 Quick start on a new PC (3 steps)

**1. Get the folder**
```
git clone <your-repo-url> clipping
```
Or copy the `clipping` folder over.

**2. Double-click `SETUP.bat`.** It runs once and takes 10–30 minutes, depending on your internet. It installs, skipping anything already there:
- Git, FFmpeg, Node.js and Python 3.11 (via winget)
- A Python environment with the packages in `requirements.txt`
- The Claude Code CLI, which is the agents' brain
- The 5 open-source clipper engines, cloned into `vendor/`
- **OpenMontage**, cloned into `vendor/OpenMontage` for its clip-factory pipeline skills and video skills (FFmpeg, Remotion, HyperFrames). This is skipped if the folder already sits inside OpenMontage.
- The Whisper speech model (about 145 MB, resumable if your connection drops)

At the end it runs a health check, which should say **READY TO RUN**.

**3. Log in to Claude once**, by opening a terminal and running:
```
claude
```
Log in with your Claude account, then close it.

### ▶️ Run it
Double-click **`RUN_CLIPS.bat`** and type a game. Or from a terminal:
```
RUN_CLIPS.bat "VALORANT"
RUN_CLIPS.bat "Fortnite" clips=8 live=off
```
The window stays open while it works, from 30 to 180 minutes. When it finishes, the `output\` folder opens.

Inside Claude Code, opened in this folder, the same run is: `/clip-run VALORANT`

### 🩺 Something wrong?
Double-click **`DOCTOR.bat`**. It checks everything and prints the exact fix for each problem.

---

## 📦 What you get
```
output/2026-11-18/valorant/
├─ REPORT.md                       which clips, scores, suggested posting order
├─ 01_tenz_1v4-deagle-clutch/
│  ├─ clip.mp4                     1080x1920, captions, hook, zoom punches, -14 LUFS audio
│  ├─ cover.jpg                    thumbnail
│  ├─ post.txt                     titles + descriptions + hashtags for TikTok / Shorts / Reels
│  └─ metadata.json                source link, timestamps, streamer credit
└─ 02_.../
```

## 🤖 The agent team
| Step | Agent | What it does |
|---|---|---|
| 1 | **streamer-scout** | Finds the top streamers for the game on Twitch, YouTube and Kick, keeps the watchlist, and picks live streams and VODs |
| 1 | **trend-analyst** | What's going viral now: hooks, titles, length, hashtags, patches, drama |
| 2 | **moment-hunter** | Records live and pulls VOD audio, scans hours for hype (loudness + Whisper), and judges moments by the ViralCutter rules |
| 3 | **script-writer** | Hook text, titles per platform, descriptions, hashtags, pinned comment, streamer credit |
| 4 | **clip-editor** | Auto-detects the facecam, picks the layout (split / facetrack / blur), adds zoom punches and captions, renders |
| 5 | **qa-publisher** | Checks every clip, rejects bad ones, and packages the output and report |

The orchestrator is `.claude/skills/clip-run/SKILL.md`.

## 🔧 Engines (`vendor/` + `.claude/skills/`)
| Engine | How it's used |
|---|---|
| **AI-Youtube-Shorts-Generator** | ✅ Runs: the face-following crop (`facetrack` layout) and facecam detection |
| **ViralCutter** | Its viral-moment rules drive how moments are chosen |
| **Reelsaw** | Its layout rules: face → facetrack, screen + cam → split, no face → blur |
| **OpenShorts** | Its webcam-inset rules for gameplay, plus an optional Docker engine |
| **AutoClip** | Its cover, title and platform ideas, plus an optional engine (needs Ollama) |
| **OpenMontage** | Its clip-factory director skills (selection, editing, review) and video skills (FFmpeg, Remotion, HyperFrames) |

ViralCutter, Reelsaw, OpenShorts and AutoClip can run as full apps on a PC with a GPU, Docker or Ollama. Each skill file has the free install steps.

## ⚙️ Settings: `config/settings.json`
| Key | Default | Meaning |
|---|---|---|
| `clips_per_run` | 6 | finished clips per run |
| `max_streamers_per_run` | 4 | how many streamers to clip per run |
| `use_live_recording` | true | record live streams (streamlink) |
| `live_record_minutes` | 45 | minutes to record per live stream |
| `max_vod_hours` | 4 | how much of a VOD to scan |
| `clip_seconds` | 15 / 35 / 59 | min / ideal / max clip length |
| `whisper_model` | base | `small` gives better captions but runs slower (run `bin/py tools/doctor.py --get-model small`) |
| `default_layout` | split | split, blur, crop, facetrack or letterbox |
| `cleanup_sources_after_run` | true | delete big source files after a run |

Games, aliases and **streamer watchlists** live in `config/games.json`. The scout fills the watchlists automatically, and you can add your own favourites:
```
bin\py.bat tools\scout.py watch --game "VALORANT" --add twitch:tenz kick:somechannel
```

## 🔑 Optional free API keys (better streamer data)
Without keys, the scout uses web research plus the watchlist. With keys, it also gets live viewer counts and Twitch's top clips. Put them in `.env`; never share or commit that file.

| Platform | Where | Steps |
|---|---|---|
| Twitch | https://dev.twitch.tv/console/apps | Register app → redirect `http://localhost` → copy Client ID → **New Secret** |
| Kick | https://kick.com/settings/developer | Create app → redirect `http://localhost` → copy Client ID and Secret |

```
TWITCH_CLIENT_ID=...
TWITCH_CLIENT_SECRET=...
KICK_CLIENT_ID=...
KICK_CLIENT_SECRET=...
```

## 🗂️ Folder structure
```
clipping/
├─ SETUP.bat / setup.ps1   one-time setup on a new PC
├─ RUN_CLIPS.bat           one-click run
├─ DOCTOR.bat              health check
├─ CLAUDE.md               rules for Claude in this folder
├─ requirements.txt        python packages
├─ bin/py, bin/py.bat      portable python launcher (finds the venv)
├─ config/                 settings.json, games.json, permissions.suggested.json
├─ tools/                  scout, trends, fetch, moments, render, engines, doctor
├─ .claude/agents/         the 6 agents
├─ .claude/skills/         clip-run orchestrator + 5 engine skills
├─ .claude/settings.json   permissions so runs need no clicks
├─ data/                   streamer index, trend history, processed VODs, logs   (kept)
├─ runs/                   per-run working files                                 (git-ignored)
├─ output/                 ✅ finished clips                                      (git-ignored)
├─ models/                 Whisper model                                          (git-ignored, SETUP downloads it)
├─ vendor/                 5 open-source engines                                  (git-ignored, SETUP clones them)
└─ workspace/              your own manual projects                               (git-ignored)
```

## 🛠️ Tools by hand (optional)
```
bin\py.bat tools\scout.py live --game "VALORANT" --check-live
bin\py.bat tools\trends.py collect --game "VALORANT"
bin\py.bat tools\fetch.py audio --url <vod-url> --out runs\test
bin\py.bat tools\moments.py scan --audio runs\test\x.m4a --out runs\test\cand.json
bin\py.bat tools\engines.py facecam --video section.mp4
bin\py.bat tools\render.py clip --video section.mp4 --spec spec.json --out runs\test\render
```
Each tool's `--help` shows all of its options.

## ⚠️ Notes
- **Respect creators.** Credit the streamer (the system adds it to every post). Some streamers don't allow re-uploads, so check before posting.
- **Live recording** needs disk space: about 1–2 GB per hour at 1080p.
- **Inside OpenMontage:** if this folder sits in an OpenMontage checkout, the agents also read its clip-factory skills. Standalone works too.
