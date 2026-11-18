# Clip system: instructions for Claude in this folder

This folder is an **autonomous gaming-clips system**. When working here, these rules take precedence over the parent OpenMontage `CLAUDE.md` and `AGENT_GUIDE.md`.

- **The pipeline is `/clip-run <game>`** (`.claude/skills/clip-run/SKILL.md`). It is OpenMontage's clip-factory in autonomous mode. Don't ask the user questions or wait for checkpoint approvals during a run.
- **Agents:** `.claude/agents/`, which are streamer-scout, trend-analyst, moment-hunter, script-writer, clip-editor and qa-publisher.
- **Engine skills:** `.claude/skills/`, which are ai-shorts-generator, viralcutter, reelsaw, autoclip and openshorts.
- **Python:** always `bin/py tools/<tool>.py ...`, which finds the right venv. Tools print JSON on stdout.
- **100% free:** never call paid APIs or providers.
- **Never post, upload or log in anywhere.** The output is the local `output/` folder.
- Only official APIs, yt-dlp, streamlink and public pages; no private endpoints.
- **Setup and health:** `SETUP.bat` sets up a new PC; `bin/py tools/doctor.py` checks this one.
