# Class-Cut Editing (Breaking School)

Video editing engine for **Breaking School**, a Bangladeshi edtech brand (MCQ Booster series, Bangla-medium
science and maths classes). The owner posts on YouTube, Instagram, Facebook and TikTok and wants content that
gets views and shares and drives course sales. Claude acts as the editor and runs this pipeline on its own.

## Default task
When the owner sends a class video or Drive link and says something like "edit the first 20 seconds" or
"make this engaging", use the **`youtube-intro` skill** (`.claude/skills/youtube-intro/SKILL.md`) and
follow `docs/STYLE_GUIDE.md` exactly. The goal is one render that is right first time. Don't re-ask
style questions: they were settled with the owner and are written down there.

## Key rules (details in docs/STYLE_GUIDE.md)
- YouTube 16:9, same resolution, fps, length, speed and voice level as the source. The owner appends the
  rest of the long video after it.
- No top or bottom banners, CTAs or answer reveals. Captions sit in the lower third.
- Li Ador Noirrit (Bold Italic / Italic / ExtraLight Italic) **white 3D text with yellow glow**. Yellow is
  the only accent color.
- Write "Hard" instead of হঠাৎ.

## Layout
- `engine/youtube_intro.py`: the renderer (zooms, light leaks, stickers, 3D captions, SFX kit, mix).
- `engine/style/house_style.json`: approved style values (fonts, sizes, glow, SFX level).
- `engine/setup.sh`, `fetch.sh`, `transcribe.py`, `analyze.py`: session setup, Drive download,
  Bangla transcript, clip analysis.
- `projects/<slug>/youtube.json`: per-video content (zooms, leaks, captions). The gold example is
  `projects/tarunasthi-mcq11/`.
- `engine/render.py`, `overlays.py`, `build.sh`: older 9:16 shorts pipeline (rejected for YouTube intros;
  keep it only for Reels/TikTok if asked).

## Environment notes
- Network hosts needed (already allowed on the owner's Default cloud environment): drive.google.com,
  drive.usercontent.google.com, huggingface.co, us.aws.cdn.hf.co (+ package registries).
- Li Ador Noirrit fonts are licensed (Lipighor) and **git-ignored**. If `engine/fonts/LiAdorNoirrit-*.ttf`
  are missing, ask the owner to upload them
  (the owner re-uploads them every session by choice; `engine/setup.sh` auto-installs uploads).
- Never commit videos, audio or fonts. Work in the scratchpad and deliver with SendUserFile.
