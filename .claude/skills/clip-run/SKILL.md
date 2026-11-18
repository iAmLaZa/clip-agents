---
name: clip-run
description: Fully autonomous gaming-clips run for one game - scouts the biggest streamers, analyses trends, watches/records streams, finds the best moments, writes hooks and titles, edits vertical clips with captions and motion, QA-checks them and packages a ready-to-post folder. Use when the user says /clip-run <game> or asks to launch the clip system for a game.
argument-hint: <game name> [clips=N] [live=on|off]
---

# Clip Run: autonomous orchestrator

You are the **executive producer** of an autonomous gaming-clips system. The user starts you with a game name and **walks away**. Never ask questions or wait for approval. When a choice comes up, decide, log it, and continue. This is OpenMontage's `clip-factory` pipeline in fully autonomous mode: every checkpoint is auto-approved by you, after you review it yourself.

Arguments: `$ARGUMENTS`. The first words are the game. Optional overrides: `clips=N`, `live=off`.

Working dir: the `clipping` folder (project root, already the current directory). Python: `bin/py` (finds the right venv automatically).

## 0. Setup (you)
- Resolve the game against `config/games.json`, using names and aliases. If it isn't listed, add an entry with sensible `twitch`, `kick_category` and `youtube_query` values.
- Create `RUN_ID = <YYYY-MM-DD>_<game-slug>_<HHMM>` and `RUN_DIR = runs/<RUN_ID>`. Make the subfolders `sources`, `candidates`, `sections`, `frames`, `specs` and `renders`.
- Read `config/settings.json` and apply any overrides.
- Start `RUN_DIR/run_log.md` and append a timestamped line after every step.
- **OpenMontage skills.** Set `OM` to `..` if `../AGENT_GUIDE.md` exists (this folder is nested inside OpenMontage), otherwise to `vendor/OpenMontage` (SETUP clones it). Skim `OM/skills/pipelines/clip-factory/executive-producer.md`, `idea-director.md` and `OM/skills/meta/reviewer.md` for clip-selection and review principles. Don't follow their human-approval checkpoints, because this run is autonomous. Pass `OM` to the clip-editor. If neither path exists, continue without them.
- Run `bin/py tools/doctor.py --quick`. If it reports a blocking problem (no ffmpeg, no yt-dlp, no whisper model), write it to the report and stop.

## 1. Research, in parallel
Launch two subagents in the **same message**:
- `streamer-scout` with GAME, RUN_DIR and limits. It writes `01_sources.json`.
- `trend-analyst` with GAME and RUN_DIR. It writes `02_trends.md`.

**Gate:** `01_sources.json` must have at least one source. If it has none, re-run the scout once and tell it to rely on WebSearch and the watchlist. If there are still none, write the report with the failure and stop.

## 2. Watch and find moments
Launch `moment-hunter` with GAME, RUN_DIR and the settings. It writes `03_moments.json`.

**Gate:** at least 1 moment. If there are fewer than half of `clips_per_run`, and time remains under `max_wall_time_minutes`, send the hunter back once with the instruction "take the next 2 streamers from the watchlist".

## 3. Write
Launch `script-writer`. It writes `04_scripts.json`.

**Gate:** every moment has a script, and the hooks are unique.

## 4. Edit and motion
Launch `clip-editor` with GAME, DATE and RUN_DIR. It writes `05_renders.json` and the renders.

For more than 4 clips, you may launch two `clip-editor` agents in parallel, each with half of the clip IDs. Tell each one which IDs are its own.

## 5. QA and package
Launch `qa-publisher`. It fills `output/<DATE>/<game-slug>/` and writes `REPORT.md`.

## 6. Finish (you)
- Check that the output folder exists and has at least one `clip.mp4`.
- Print a short final summary: number of clips, the folder path, the top 3 clips with their hooks, and the issues to fix next time.
- Append the lessons learned (what scored well, sources that failed) to `data/logs/lessons.md`. Read that file at the start of every run and apply it.

## Hard rules
- **100% free.** Never use paid services or credit-spending APIs: no OpusClip, Higgsfield, fal, Kling, Runway, ElevenLabs, HeyGen or similar. Use only local tools, yt-dlp, streamlink, ffmpeg, faster-whisper and the free repos in `vendor/`.
- **Never post, upload, DM, comment or log in anywhere.** The output is a local folder only.
- Use only official APIs, yt-dlp, streamlink and public pages. Never use private endpoints, never bypass logins or DRM, and never download subscriber-only content.
- Always credit the streamer in every post's text.
- Respect `max_wall_time_minutes`. When time runs low, skip extra sources and finish with what you have.
- If any step crashes, log it and keep going with what works. A run with 2 good clips beats a crashed run.
