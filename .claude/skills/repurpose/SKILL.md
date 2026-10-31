---
name: repurpose
description: Turn a long client video (podcast, webinar, talking-head) into 5-10 short, captioned, face-centred vertical clips with a hook line on screen, exported per platform at -14 LUFS. Use when the owner gives a video to repurpose, asks for clips/shorts/reels, a new client video, or square/landscape versions of existing clips.
---

# Repurpose: long video -> short clips

Follow CLAUDE.md for specs, style, file names and how to talk to the owner (simple words, one-line failures with the fix).
All commands run from the toolkit folder (the one holding CLAUDE.md) with the toolkit Python:
`PY` = `.venv\Scripts\python.exe` on Windows, `.venv/bin/python` on Mac/Linux.
`S` = `.claude\skills\repurpose\scripts` (use `/` on Mac/Linux). Never use bash-only commands.

## Before you start
1. Client name = lowercase, no spaces (`drsmith`). Video goes in `clients\<name>\raw\`. If the owner gave a path elsewhere, COPY it there (never move or edit the original).
   **If the owner gave a LINK instead of a file:** `PY S\fetch.py --client drsmith --url "<link>" --name sleep_podcast` saves it in `raw\`. It handles direct links, Dropbox, Google Drive ("anyone with the link") and YouTube/Vimeo/Loom pages (the client's own videos only). In the cloud the website must be in the environment's Allowed domains (the error message says which one to add and how). Google Drive and YouTube downloads are untested; if one fails, ask the owner for the file or a Dropbox/direct link.
2. If `clients\<name>\brief.md` exists, read it (colors, fonts, platforms). If not, create it from `templates\client-brief-template.md` with what you know.
3. Topic = short lowercase word(s) from the video's subject (`sleep`, `pricing`). It becomes part of every file name.

## The 8 steps

### 1. Transcribe (word timestamps)
```
PY S\repurpose.py transcribe --client drsmith --video clients\drsmith\raw\sleep_podcast.mp4 --topic sleep
```
Saves `transcripts\sleep_podcast.json` (word times) and `.txt` (readable, with time stamps). First run downloads the speech model (needs internet once). Long videos (1 hour+) take several minutes - tell the owner it is working.

### 2. Pick the 5-10 strongest moments - then STOP for approval
Read the `.txt` transcript fully. Choose moments with: a hook in the first 3 seconds, one complete idea, an emotional or useful takeaway, 20-55 seconds long, starting and ending on full sentences. Rank them by likely performance (best = 1): strong opening claim/question, clear payoff, relatable pain, shareable, no need for visuals.

Write `clients\<name>\clips\<topic>\clips.json`:
```json
{"client": "drsmith", "topic": "sleep",
 "source": "clients/drsmith/raw/sleep_podcast.mp4",
 "transcript": "clients/drsmith/transcripts/sleep_podcast.json",
 "clips": [
  {"rank": 1, "start": 125.4, "end": 171.0,
   "hook": "You are probably sleeping wrong",
   "title": "Why 8 hours is a myth",
   "caption": "Sleep quality beats sleep hours. Here is what to track instead. Save this for tonight.",
   "hashtags": ["#sleep", "#health", "#wellness"],
   "why": "Bold claim, one clear idea, useful tip"}
 ]}
```
Times are seconds from the start of the source video (or `"mm:ss"`). Hook = max 14 words, on-screen text shown for 3 seconds (it should match or sharpen what is said). Caption = 1-3 short sentences in the client's voice. 3-5 hashtags.

Then:
```
PY S\clips.py validate clients\drsmith\clips\sleep\clips.json
```
It moves cut points to word edges, checks lengths/hashtags and prints the ranked list. If it reports a problem, fix `clips.json` and run again.
**Show the owner the ranked list** (timestamps, hook, title, caption, hashtags) in the chat, also save it to `clients\<name>\transcripts\<topic>_clips.txt`:
```
PY S\clips.py show clients\drsmith\clips\sleep\clips.json
```
Ask: "Which ones should I make? (all / numbers)". **Do not cut anything until they answer.** After they answer:
```
PY S\clips.py approve clients\drsmith\clips\sleep\clips.json --ids 1,2,5     (or --all)
```
If they want a change (different moment, another hook), edit clips.json, validate and show again.

### 3-8. Make the approved clips
```
PY S\repurpose.py make --client drsmith --topic sleep
```
This runs for every approved clip: **3** cut (FFmpeg, 30 fps, "um/uh" removed) -> **4** silence removal (auto-editor) -> **5** reframe with face tracking (OpenCV, smoothed; centre crop if no face) -> **6** captions (ASS file from word times, Montserrat ExtraBold or the brand font, current word highlighted, lower-middle, moved below the face if needed) -> **7** hook text for the first 3 seconds -> **8** export per platform, loudness -14 LUFS, correct name. It finishes by running `check.py` and printing the PASS/FAIL table.

Options (add only when needed):
- `--platforms reels,tiktok,shorts` (default: the platforms in brief.md, else `reels`). One platform in another shape: `--platforms linkedin:square`.
- `--also square,landscape` adds square (1080x1080) and/or landscape (1920x1080) versions.
- `--clips 1,3` only those clips. `--quality best` only if the owner asks. `--silence gentle|normal|tight` (tight = faster pace, also shortens a clip that is slightly over 60 s).
- `--no-hook`, `--no-highlight`, `--uppercase` for style changes. `--force` redo everything (otherwise finished steps are reused, so a re-run after a fix is quick).

Each step also works alone (`cut.py`, `silence.py`, `reframe.py`, `captions.py`, `hook.py`, `export.py` - run with `--help`).

## After export
- Every file must be PASS in the table (under 60 s, 1080x1920 / 1080x1080 / 1920x1080, 30 fps, H.264 + AAC, about -14 LUFS, correct name). Fix and redo any FAIL. Re-check with `PY check.py clients\<name>\final`.
- Look at one frame from each clip if you can (`ffmpeg -ss 1.5 -i file.mp4 -frames:v 1 frame.png`): text readable, not over the face.
- Report in simple words: how many clips, where (`clients\<name>\final\`), the notes the script printed (e.g. "no face found, centre crop used"), and the ranked list again with the final file names.

## Brand and style
Colors/fonts come from `brief.md` automatically: `Primary` = hook box, `Accent` = highlighted word, `Caption text` = caption color, `Caption font`/`Hook font` (put the .ttf/.otf in `clients\<name>\fonts\`). Without them: white captions, yellow highlight, dark-navy hook box, Montserrat.

## Troubleshooting (say the cause in one line + the fix)
- Speech model won't load -> internet needed once. - "auto-editor not installed" / FFmpeg missing -> run `setup.ps1`.
- Captions show wrong words -> re-run transcribe with `--model medium` (slower, more accurate), then `make --force`.
- Two people on screen and the crop follows the wrong one -> tell the owner; use `reframe.py ... --no-track` for a centre crop.
