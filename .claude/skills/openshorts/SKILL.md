---
name: openshorts
description: OpenShorts (vendor/openshorts) - open-source 9:16 shorts generator with AI moment detection, face tracking, subtitles and an MCP server/API for agents. Optional Docker engine. Use when the user asks to run OpenShorts or to compare its output with ours.
---

# OpenShorts (optional engine)

The repo is in `vendor/openshorts`. It's MIT licensed and self-hosted with Docker.

**What it is:** long video in, viral 9:16 shorts out, with AI moment detection, face tracking, subtitles and dubbing. It has an MCP server and an API for AI agents.

**Free use only:**
- Self-host it with Docker.
- Its moment detection uses an LLM (Gemini by default). Gemini's free tier needs a free Google AI Studio key; the user decides whether to add one.
- **Never** use the paid OpenShorts cloud ($12/mo).

**Status on this PC:** not running, because Docker Desktop is stopped. Read `vendor/openshorts/README.md` for setup.

**Best file for gaming clips:** `vendor/openshorts/camera_inset.py`. It finds the webcam inset in a gameplay or screen recording and frames the two apart. Its detector needs YOLO and torch, which aren't installed. Its rules are plain logic and worth applying when you verify `tools/engines.py facecam` results:
- An inset is small, off-centre and near a corner (`is_cornered`, `CORNER_MARGIN` 0.20).
- It must agree across several samples (`stable_box`).
- Pad the box around the subject (`inset_box`).

Also see `active_speaker.py` (who is talking) and `clip_selection.py` (moment selection ideas).

**In the clip system:** our own pipeline (moments, render) covers the same job for free. Use OpenShorts only as an alternative engine when the user asks, or to compare results.
