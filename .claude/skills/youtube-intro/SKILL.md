---
name: youtube-intro
description: Edit the first ~20 seconds of a Breaking School Bangla class video for YouTube in the approved house style (Li Ador 3D white+yellow captions, stickers, light leaks, jump zooms, synthesized SFX). Use when the user shares a video or Drive link and asks to edit / make engaging / "edit that 20 seconds" / make an intro.
---

# YouTube intro: one-shot workflow

Goal: render **once**, correctly, without asking the owner design questions. Every style decision is already
made in `docs/STYLE_GUIDE.md`. Read it fully before writing the config. Only ask the user something if a
step below is actually blocked (private link, missing fonts).

Work dir: `W=<scratchpad>/<slug>` (slug = short English name of the topic, e.g. `tarunasthi-mcq11`).

## 1. Setup (about 1 min)
```
bash engine/setup.sh
```
If it reports missing Li Ador fonts, ask the user to upload the three .ttf files (Bold Italic, Italic,
ExtraLight Italic) and copy them into `engine/fonts/` with the names it prints. Never substitute another font.

## 2. Get the video
```
bash engine/fetch.sh "<drive link or uploaded file path>" $W/src.mp4
```
If it fails with a sign-in page, ask for sharing set to "Anyone with the link can view".
If the clip is longer than ~25 s, cut the first 20-21 s at a sentence end only if the user asked for that.
Otherwise edit the whole clip they sent.

## 3. Understand the clip (run both, in parallel)
```
python3 -I engine/transcribe.py $W/src.mp4 $W/words.json      # Bangla word timestamps, ~5 min on CPU
python3 -I engine/analyze.py   $W/src.mp4 $W/an               # contact sheet, scene cuts, grid frames
```
Then **Read** `$W/an/contact.png` and the `grid_*.png` frames. Note:
- what is on screen when (board word, MCQ slide, teacher position, where the face is);
- slide changes from `report.json` `scene_cuts` (each gets a light leak + a ~3 s caption-free 1.0x hold);
- the meaning of each sentence (the transcript is phonetic; reconstruct the real Bangla).

## 4. Write `projects/<slug>/youtube.json`
Copy the structure of `projects/tarunasthi-mcq11/youtube.json` (the gold example). Style keys come from
`engine/style/house_style.json`, so the project file holds **content only**:
- `zooms`: `[start, end, z_start, z_end, cx, cy]` in **1280x720 design coords** (use the grid frames).
  Hard cuts between levels. Cover the whole clip. The last segment ends at 1.0 about 0.6 s before the end.
- `leaks`: `[[t, "yellow"], ...]` at each idea or slide change (3-5 total).
- `captions`: 5-6 objects `{setup_at, punch_at, end, setup, punch, color:"yellow", sticker | bang, mark?,
  mark_delay?}`. Follow the recipe and the **Hard rules** in the style guide (white+yellow only, "Hard" not
  হঠাৎ, `[l]..[/l]` light words, no caption during the first ~3 s of a new slide, last caption ends
  ~3 s before the clip end).
- `sfx`: `[["boom", 0.0, 0.5]]` (everything else is automatic).

## 5. Render
```
python3 -I engine/youtube_intro.py projects/<slug>/youtube.json $W/src.mp4 $W/<Slug>_YouTube_Intro.mp4
```
(~40 s). Output matches the source size, fps and audio rate automatically.

## 6. QC before sending (do not skip)
Extract one frame mid-way through every caption plus one at the end:
```
for t in <list>; do ffmpeg -v error -y -ss $t -i OUT.mp4 -frames:v 1 -vf scale=640:-1 $W/qc_$t.png; done
```
Tile them into one image with PIL and **Read** it. Check:
- Bangla conjuncts look right; no raw `{\...}` tag text visible; nothing cut off at the frame edges;
- setup and punch lines don't overlap; stickers and "?!" don't cover the text;
- only white and yellow text; the marker bar sits behind the marked words;
- zoom targets frame the face or the board word (not empty space);
- the last frame is unzoomed with no text (clean join).
Also run `ffmpeg -i OUT.mp4 -af ebur128=peak=true -f null -` and check the peak is at most -0.5 dBFS,
and that the duration matches the source to within 0.1 s.
Fix and re-render if anything fails. One extra QC loop is cheaper than a revision from the owner.

## 7. Deliver
- SendUserFile the MP4 (status normal) with a one-line caption.
- Short summary: the captions used (Bangla), where the zooms and leaks are, and anything uncertain in the
  transcript that the owner should double-check.
- Commit `projects/<slug>/youtube.json` (never commit videos or the Li Ador fonts) and push to the
  session's branch.
