---
name: ai-shorts-generator
description: AI-Youtube-Shorts-Generator engine (vendor/AI-Youtube-Shorts-Generator) - free local face-tracking 9:16 reframe with motion smoothing and webcam/face detection. Use when a clip needs a crop that follows a face (IRL, just chatting, reaction, full-screen facecam) or to auto-detect the facecam box.
---

# AI-Youtube-Shorts-Generator engine (installed, free, CPU)

The repo is in `vendor/AI-Youtube-Shorts-Generator`. It's MIT licensed.

**What we use from it:** its local-mode OpenCV face tracker, which slides a 9:16 window to keep the biggest face centred, with smoothing. It needs no API key.

**How to call it:**
- **Face-following crop as a render layout:** in a render spec, set `"layout": "facetrack"`. `tools/render.py` runs the engine and then adds captions, hook and punches as usual.
- **Standalone:** `bin/py tools/engines.py facetrack --video in.mp4 --out out.mp4`
- **Auto-detect the facecam box for `split`:** `bin/py tools/engines.py facecam --video sec.mp4`. It returns `facecam [x,y,w,h]` and `suggested_layout`. Always confirm the box by Reading a frame.

**Don't use** its highlight picker (`highlights.py`). It needs OpenAI, Gemini or MuAPI keys, which cost money. In this system, the Claude agents pick the highlights.

**When to choose `facetrack`:**
- The face fills a big part of the frame: IRL, just chatting, a reaction cam, or a full-screen face moment.
- Not for gameplay with a small corner webcam. Use `split` for that.
