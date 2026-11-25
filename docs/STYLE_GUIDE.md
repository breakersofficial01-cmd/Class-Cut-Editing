# Breaking School: YouTube intro edit, house style

This is the approved result of a long review session with the owner. Follow it exactly. Don't "improve"
it with ideas the owner already rejected (see **Rejected**). The gold-standard example is
`projects/tarunasthi-mcq11/youtube.json` (MCQ 11, তরুণাস্থি). Render that file to see the target look.

## What the job is
- Input: the first ~20 s of a long (~5 min) Bangla classroom video for **YouTube** (16:9). The owner
  appends the rest of the long video after it.
- Goal: make those 20 s so engaging that anyone who lands on the video keeps watching.
- Output: one MP4 with the **same resolution, fps, speed, length and voice level** as the source, so the
  join is invisible.

## Hard rules (owner's explicit instructions)
1. **YouTube 16:9 only.** Never letterbox or reframe to 9:16 unless asked.
2. **No text banners** at the top or bottom of the frame. No question cards, progress bars, CTAs,
   "answer at the end", or 3-2-1 answer reveals. The video continues after the cut.
3. **Keep the voice untouched.** No speed-up or re-timing, and no loudness normalisation (only a peak limiter).
4. **Colors: WHITE text + YELLOW accent only.** Yellow glow, gold 3D extrusion, yellow marker bar,
   yellow light leaks. **No red, green, orange or any other color** in text or effects.
5. **Fonts: Li Ador Noirrit, three weights combined.**
   - Punch line: **Bold Italic**
   - Accent words inside a punch line (`[l]..[/l]`): **ExtraLight Italic**
   - Setup line: **Italic**, and marked words switch to **Bold Italic** over the yellow marker
6. **Wording:** use the English word **"Hard"** instead of **হঠাৎ** (for example "কেউ Hard প্রশ্ন করলে").
   Short, punchy, spoken-style Bangla. English subject words (MCQ, Hard) are fine.
7. Captions must say what the teacher actually means. The Whisper transcript is phonetic and messy, so
   rewrite it by meaning and never copy garbled words. Correct the science (check spellings against
   the slide, e.g. option "ল্যাকিউনি").

## Look (copied from the owner's reference video, first 20 s)
**Two-tier lower caption** (bottom-center, over the picture, never in a banner):
- Setup line: small (50), white, wipes in left to right in 0.3 s. It can mark 1-2 key words: a yellow
  highlighter bar sweeps behind them and they turn Bold Italic.
- Punch line: big (92), white 3D text that **slides up from behind an invisible baseline** (0.14 s),
  overshoots, then settles. It can mix weights: `"[l]কী কী[/l] প্রশ্ন আসে?"`.
- 3D text = white face + light bevel tint on the lower half, black outline, 7-step gold extrusion
  down-right, yellow glow, soft drop shadow.
- **Sticker:** one color emoji beside the punch line that matches the meaning (📚 new topic, 🦴 bone or
  cartilage, 🤔 question, ✍️ write it, 📖 book, 🧪 experiment, 🧮 maths, 💡 tip, ⚠️ trap). It pops with an elastic
  bounce and then floats.
- **"?!"** (white 3D + gold edge, snaps in with rotation) to the left of question punch lines
  (`"bang": true`), at most once or twice per intro, instead of a sticker.

**Picture:**
- Jump-zoom punch-ins with hard cuts between zoom levels: teacher at the board ~1.3x, the key board word
  ~1.5x, face close-up ~1.32x, slide fully visible 1.0x. Each segment drifts slowly (+0.04 to 0.06).
- **Light leaks** (yellow) at each idea change or slide change, about every 3-6 s, 0.45 s long.
- When a new MCQ or slide appears, stay at 1.0x for about 3 s with **no caption**, so viewers can read it.
- The last segment eases back to **zoom 1.0** and captions stop **~3 s before the end** (clean join).

**Sound** (synthesized, engine/youtube_intro.py `KIT`, mixed under the voice at `sfx_volume` 0.65):
- Light leak: sparkle (5 bright chime hits ~0.1 s apart) + swoosh
- Setup line: soft swish. Punch line: rising swoosh + thump. Sticker: bubble pop.
- Marker: highlighter stroke. "?!": bip-bip alert + low boom. Very first frame: soft boom.

## Caption writing recipe (20-21 s clip)
- 5-6 captions. Each = setup (<= 5 words) + punch (<= 4 words, the payoff word).
- Time the **setup** to when the teacher starts the phrase and the **punch** to the exact word timestamp of
  the payoff word (from transcript.json). `end` = the next idea, a cut, or a zoom change.
- Order of beats that works: new topic -> topic name -> "what comes from this" -> (slide, no caption) ->
  key concept question with ?! -> instruction ("এটাই লিখবে!") -> twist ("বইয়ে দেওয়া নাই!").
- Mark 1-2 setups with `mark` (the key nouns). Use `[l]..[/l]` on the soft lead-in words of 3-4 punches.
- Leave at least 0.15 s between one caption's `end` and the next `setup_at`.

## Rejected by the owner (do not do again)
- 9:16 vertical version with top question card, bottom captions, answer reveal and CTA ("don't add texts in
  the upper and lower part like that").
- Speeding the voice up.
- Plain Noto font captions ("don't look cool"), and Galada or Atma.
- Multi-color captions (yellow/green/red) and red highlights, red "?!", red or orange light leaks.
