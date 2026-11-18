---
name: viralcutter
description: ViralCutter knowledge (vendor/ViralCutter) - the "ViralCutter Standard" rules for judging viral segments (hook start, standalone test, narrative arc, duration math), plus its 1-face/2-face layout and subtitle ideas. Use when judging moments (moment-hunter) or designing layouts and captions (clip-editor).
---

# ViralCutter (reference engine)

The repo is in `vendor/ViralCutter`. It's GPL-3.0.

**Status on this PC:** not installed. Its full install needs whisperx, insightface, mediapipe and torch (several GB), and an NVIDIA GPU is recommended. With 8 GB RAM, no GPU and a slow connection, we use its **ideas**, not its runtime.

## Use its moment rules (moment-hunter)
Read `vendor/ViralCutter/prompt.txt` and apply its rules when you score candidates:
1. **No garbage starts.** Never open on filler ("um", "so...", "and then") or a low-energy intro. Start on a hook: a statement, a question, or action.
2. **Standalone test.** A stranger must understand the clip with zero context, so there are no unexplained "he" or "that".
3. **Narrative arc.** A hook in the first 0–3 s, then the story or tension, then the payoff. Never cut mid-sentence.
4. **Duration math.** Respect min and max, and compute from the timestamps.

## Layout ideas (clip-editor)
- `scripts/one_face.py`: one face, crop and centre it. Our equivalent is `facetrack`.
- `scripts/two_face.py`: two people stacked. Our equivalent is `split` with the facecam on top.
- `scripts/burn_subtitles.py` and `adjust_subtitles.py`: subtitle styling ideas, such as word highlight and position.

## If the user later gets a GPU
Run `vendor/ViralCutter/install_dependencies.bat`, then `run_webui.bat`. For free use, pick a local GGUF model in `models/`. Never use paid API keys.
