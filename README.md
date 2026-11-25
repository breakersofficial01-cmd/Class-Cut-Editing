# Class-Cut Editing

**New session? Just say:** "edit the first 20 seconds of this video: <Drive link>".
Claude Code reads `CLAUDE.md`, runs the `youtube-intro` skill (`.claude/skills/youtube-intro/SKILL.md`) and
follows `docs/STYLE_GUIDE.md` (the approved house style). One render, QC'd, delivered.

Quick manual run:
```
bash engine/setup.sh
bash engine/fetch.sh "<drive link>" work/src.mp4
python3 -I engine/transcribe.py work/src.mp4 work/words.json
python3 -I engine/analyze.py   work/src.mp4 work/an
# write projects/<slug>/youtube.json (copy projects/tarunasthi-mcq11/youtube.json)
python3 -I engine/youtube_intro.py projects/<slug>/youtube.json work/src.mp4 work/out.mp4
```

---
## History / older pipelines

Turns raw Breaking School class clips into hook-first vertical shorts (Reels / TikTok / Shorts).

## Edit formula (applied automatically)
1. **Cold open (0–1.6 s):** freeze on the clean MCQ + "এই MCQ-তে অনেকেই ভুল করে! / তুমি পারবে?", flash, shake, impact SFX.
2. **Open loop:** question card pinned on top for the whole video + pulsing "উত্তর ভিডিওর একদম শেষে!".
3. **Pace:** speech 1.1× (pitch kept), jump-zoom punch-ins on key words, whoosh on slide changes, top progress bar.
4. **Captions:** big Bangla kinetic captions (Noto Sans Bengali Black), keywords in brand yellow, pop-in + SFX.
5. **Payoff:** "আগে নিজে ভাবো!" → ৩-২-১ ticks → correct option turns green, others dim, ding → 1-line explanation.
6. **CTA:** "কমেন্টে লেখো তুমি কোনটা দিয়েছিলে!" + Follow (comments = reach).
7. Audio cleaned, compressed, mastered to -14 LUFS.

## Usage
```
engine/build.sh <source.mp4> projects/<name> <work_dir>   # -> <work_dir>/final_9x16.mp4
```
Each video gets a `projects/<name>/config.json` (zooms, captions, hook/question/answer text, SFX cues).
Captions are timed from a faster-whisper large-v3 transcript, then corrected by hand.

## YouTube long-form intro (16:9, no text)
For the first ~20 s of a long video that continues after the cut:
```
python3 -I engine/youtube_intro.py projects/<name>/youtube.json <source.mp4> <out.mp4>
```
Keeps original speed, length, 1280x720@30, 44.1 kHz audio so the rest of the video appends seamlessly.
Style = the channel's reference video (first 20 s):
- Two-tier lower captions: small white setup line + big punch line (yellow / green / red, thick black
  outline, pop-in), color-emoji sticker beside it, red "?!" on question beats.
- Warm light-leak transitions (yellow / red / orange) at each idea change, with whoosh.
- Jump-zoom punch-ins (teacher, board word, face close-up); pop SFX on each punch line.
- Captions stop ~3 s before the end and zoom eases back to 1.0, so the join is invisible.
- No top/bottom banners, no answer reveal, speech speed & level untouched.

## Fonts (bundled in `engine/fonts`, all SIL OFL)
Set in `caption_style` (`setup_font`, `punch_font` = file name in engine/fonts):
CCGalada (stylish calligraphic), CCAtmaBold (playful bold), CCBalooBold (rounded), CCAnekBlack / CCAnekSemi
(modern condensed), CCMinaBold, CCHindBold, NotoSansBengali-Black / SemiBold.
Sizes are libass sizes; widths are measured per font, so stickers / "?!" / marker bars stay aligned.

## Current house style (v5): Li Ador Noirrit, white 3D text
- Punch line: Li Ador Noirrit **Bold Italic**; accent words `[l]..[/l]` in **ExtraLight Italic**.
- Setup line: Li Ador Noirrit **Italic**; `mark` words switch to Bold Italic over the red marker sweep.
- Palette: WHITE text + ONE accent, YELLOW only (yellow glow, gold 3D extrusion, yellow marker, yellow leaks).
  No red / green / other colors. 3D = white face, black outline, 7-step gold extrusion, yellow glow, soft shadow.
- Li Ador fonts are licensed by Lipighor (no redistribution), so they are **git-ignored**. Put the three
  .ttf files in `engine/fonts/` as LiAdorNoirrit-BoldItalic.ttf / -Italic.ttf / -ExtraLightItalic.ttf.
