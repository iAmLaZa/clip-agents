---
name: autoclip
description: AutoClip (vendor/autoclip) - full open-source clipping app with CLI and MCP server, covers, publish copy and multi-platform presets. Optional heavy engine; free only with a local Ollama model. Use when the user explicitly wants to run AutoClip, or to borrow its cover/caption/publishing-copy ideas.
---

# AutoClip (optional full engine)

The repo is in `vendor/autoclip`. It's MIT licensed, about 10k stars, and Python 3.11.

**What it is:** a desktop, Docker or CLI+MCP app that takes a long video and produces clips, subtitles, covers and publish copy for Douyin, TikTok, Reels and Shorts. Docs: `vendor/autoclip/README-EN.md`, `docs/CLI_AND_MCP.md`.

**Status on this PC:** not installed. It needs an LLM. The only free route is **Ollama** with a local model, which isn't installed. That model is a 2–5 GB download and runs slowly with 8 GB RAM and no GPU. Never configure a paid provider such as qwen-plus or Bailian cloud ASR.

**Use it today as a reference:**
- **Covers and titles:** look at its cover-template and copywriting logic in `backend/` for ideas the script-writer can reuse.
- **Platform presets:** borrow its aspect, length and caption conventions per platform.

**To enable it later (free):**
1. Install Ollama and pull a small model, e.g. `qwen2.5:3b`.
2. Follow `README-EN.md`, the "Batch / agents: CLI / MCP" route: Python 3.11 + FFmpeg, no Redis.
3. In AutoClip settings, choose Ollama at `http://localhost:11434/v1`.
