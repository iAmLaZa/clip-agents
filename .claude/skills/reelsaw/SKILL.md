---
name: reelsaw
description: Reelsaw (vendor/reelsaw) - self-hosted TypeScript clipper with the best reframing logic (per-segment face/split/stack/fit layouts, UltraFace CPU tracking, filler-word jump cuts, karaoke captions, hook overlay) and an MCP server. Optional Docker engine, fully local with Ollama. Use to borrow layout/caption rules, or when the user asks to run Reelsaw.
---

# Reelsaw (optional full engine and design reference)

The repo is in `vendor/reelsaw`. It's AGPL-3.0, TypeScript, run with Docker Compose.

**Its best ideas, which our clip-editor applies:**
- **Layout per segment** (`vendor/reelsaw/docs/LAYOUTS.md`):
  - **face:** follow the speaker with "heavy tripod" smoothing (dead zone, capped pan speed, snap at scene cuts). Ours is `facetrack`.
  - **split:** two speakers.
  - **stack:** screen on top, webcam tile below. This is our `split` for gameplay.
  - **fit:** the whole frame over a blurred background. This is our `blur`.
- **Filler and false-start jump cuts:** cut "um", repetitions and dead air inside a clip. The clip-editor can narrow `trim` to skip dead air at the start.
- **Word-highlight karaoke captions plus a hook overlay.** `render.py` already does both.
- **Fades:** a short fade-out at the end helps loops.

**Status on this PC:** not running. Docker Desktop is installed but stopped. A fully local setup needs Ollama plus local Whisper containers, several GB, with only 31 GB of disk free.

**To enable it later (free):**
1. Start Docker Desktop.
2. Follow `README.md` "Self-host", using local Ollama and Speaches models only, never paid providers.
3. Its MCP server at `http://localhost:<port>/api/mcp` can then be added to Claude Code.
