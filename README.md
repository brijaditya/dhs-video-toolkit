# DHS Video Toolkit (Digital Help Studio)

Turns long client videos (podcasts, webinars, talking-head videos) into short, captioned, face-centred clips
for TikTok, Reels, Shorts and LinkedIn - run by Claude Code on a Windows PC.

## Install (once)
1. Copy this whole folder to `C:\DHS`.
2. Right-click `setup.ps1` > **Run with PowerShell** (or: `powershell -ExecutionPolicy Bypass -File C:\DHS\setup.ps1`).
   It installs Git, FFmpeg and Python 3.12 if missing, builds the Python environment, sets up the effects skill (45 effects),
   runs a 30-second self-test and ends with **READY** or a clear error.
3. Open Claude Code in `C:\DHS` and say: *"New client drsmith. Here is the video: ..."*

## What is in here
| Path | What it is |
|---|---|
| `CLAUDE.md` | The rules Claude Code reads every session (specs, names, folders, style, tone) |
| `.claude/skills/repurpose/` | The 8-step workflow (SKILL.md + Python scripts) |
| `.claude/skills/effects/` | 45 video effects (zoom, spotlight, widgets...), copied from Vibha Ramprakash's open-source repo (MIT) |
| `.claude/agents/video-editor.md` | The DHS video editor agent |
| `check.py` | Checks every export: length, size, fps, codecs, loudness. Prints PASS/FAIL |
| `selftest.py` | 30-second health test of the whole chain (no client files needed) |
| `templates/client-brief-template.md` | Copy to `clients\<name>\brief.md` for each client |
| `assets/` | Bundled Montserrat font (SIL Open Font License) and the face-finder model |
| `clients/` | Client work. Stays on your PC, ignored by git. Never commit it |

## Folder per client
`clients\<name>\raw` (originals) - `transcripts` - `clips` (working files + clips.json) - `final` (finished, checked clips) - `brief.md` - `fonts` (optional brand fonts).

Works on Windows, Mac and Linux (needs Python 3.10+ and FFmpeg on Mac/Linux; run `python -m venv .venv`, install `requirements.txt`).
