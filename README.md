# Class-Cut Editing

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
