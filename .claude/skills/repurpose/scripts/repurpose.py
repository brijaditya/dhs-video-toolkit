"""Run the repurpose workflow. Steps 3-8 for every APPROVED clip in clips.json.

  python repurpose.py transcribe --client drsmith --video clients/drsmith/raw/sleep_podcast.mp4
  python repurpose.py make --client drsmith --topic sleep [--clips 1,2] [--platforms reels,tiktok,shorts]
                           [--platforms linkedin:square] [--also square,landscape] [--quality fast|best]
                           [--silence gentle|normal|tight] [--no-hook] [--no-highlight] [--force]

Finished files go to clients/<client>/final/ and are named  clientname_topic_clipNN_platform.mp4
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from captions import build_captions
from clips import resolve
from common import (FORMATS, PLATFORMS, PLATFORM_ALIASES, ROOT, client_dirs, ensure_client, fail, find_brand_fonts, load_brief,
                    load_json, normalize_platform, run_main, save_json, slug, topic_dir)
from cut import cut_clip
from export import QUALITY, export_clip
from hook import build_hook
from reframe import reframe
from silence import LEVELS, remove_silence


def say(msg: str):
    print(msg, flush=True)


def parse_targets(specs: list[str], also: list[str], brief: dict) -> list[tuple[str, str]]:
    """-> list of (platform, format). Extra shapes from --also are added to the normal platforms."""
    out = []
    for s in specs:
        plat, _, f = s.partition(":")
        plat = normalize_platform(plat)
        f = f.strip().lower() or PLATFORMS[plat]
        if f not in FORMATS:
            fail(f"'{f}' is not a picture shape I know.", "use vertical, square or landscape.")
        out.append((plat, f))
    if not out:
        known = set(PLATFORMS) | set(PLATFORM_ALIASES)
        for p in brief.get("platforms") or []:
            if p.strip().lower() in known:
                n = normalize_platform(p)
                out.append((n, PLATFORMS[n]))
        out = out or [("reels", "vertical")]
    for f in also:
        f = f.strip().lower()
        if f not in ("square", "landscape"):
            fail(f"'{f}' cannot be added with --also.", "use square or landscape.")
        out.append((f, f))
    seen, uniq = set(), []
    for t in out:
        if t[0] not in seen:
            seen.add(t[0])
            uniq.append(t)
    return uniq


def do_transcribe(a):
    from transcribe import transcribe_file, readable_text
    video = resolve(str(a.video))
    d = ensure_client(a.client)
    if not video.exists():
        fail(f"The video {video} was not found.", "put it in the client's raw folder and check the name.")
    topic = slug(a.topic or video.stem)
    out = d["transcripts"] / f"{slug(video.stem)}.json"
    say(f"Listening to the video (this takes a few minutes the first time)...")
    data = transcribe_file(video, a.model, a.language)
    if not data["words"]:
        fail("No speech was found in this video.", "check the sound is on and the language is right (try --language en).")
    save_json(out, data)
    out.with_suffix(".txt").write_text(readable_text(data), encoding="utf-8")
    cdir = topic_dir(a.client, topic)
    cdir.mkdir(parents=True, exist_ok=True)
    say(f"Transcript saved: {out}")
    say(f"Readable version: {out.with_suffix('.txt')}")
    say(f"Next: write the best moments to {cdir / 'clips.json'} (topic = {topic})")


def make_one(clip: dict, data: dict, targets, args, brief, notes_all):
    from transcribe import transcribe_file
    client, topic = data["client"], data["topic"]
    cdir = topic_dir(client, topic) / f"clip{clip['id']:02d}"
    cdir.mkdir(parents=True, exist_ok=True)
    source = resolve(data["source"])
    words = load_json(resolve(data["transcript"])).get("words", []) if data.get("transcript") else []

    cut = cdir / "1_cut.mp4"
    if args.force or not cut.exists():
        say(f"  Clip {clip['id']}: cutting...")
        info = cut_clip(source, clip["start"], clip["end"], cut, words)
        if info["fillers_removed"]:
            say(f"    removed {info['fillers_removed']} filler words (um/uh)")
    tight = cdir / "2_tight.mp4"
    if args.force or not tight.exists():
        say(f"  Clip {clip['id']}: removing silences...")
        r = remove_silence(cut, tight, args.silence)
        say(f"    {r['before']:.0f}s -> {r['after']:.0f}s")
    wjson = cdir / "words.json"
    if args.force or not wjson.exists():
        say(f"  Clip {clip['id']}: timing the captions...")
        save_json(wjson, transcribe_file(tight, args.model))
    words_clip = load_json(wjson)["words"]

    extra_fonts = [f for f in [find_brand_fonts(client)] if f]
    groups: dict[str, list[str]] = {}
    for plat, f in targets:
        groups.setdefault(f, []).append(plat)
    outputs = []
    for f, plats in groups.items():
        say(f"  Clip {clip['id']}: {f} version ({', '.join(plats)})...")
        framed = cdir / f"3_{f}.mp4"
        track = cdir / f"3_{f}_face.json"
        if args.force or not framed.exists():
            res = reframe(tight, framed, f, track)
            if not res["face_found"]:
                notes_all.append(f"Clip {clip['id']} ({f}): no face found, centre crop used.")
        boxes = load_json(track).get("boxes") if track.exists() else None
        W, H = FORMATS[f]
        notes: list = []
        ass_files = []
        cap_ass, _ = build_captions(words_clip, W, H, brief, client, boxes, not args.no_highlight, args.uppercase, notes)
        (cdir / f"4_{f}_captions.ass").write_text(cap_ass, encoding="utf-8")
        ass_files.append(cdir / f"4_{f}_captions.ass")
        if not args.no_hook and clip.get("hook"):
            hook_ass, _ = build_hook(clip["hook"], W, H, brief, client, boxes, notes=notes)
            (cdir / f"4_{f}_hook.ass").write_text(hook_ass, encoding="utf-8")
            ass_files.append(cdir / f"4_{f}_hook.ass")
        notes_all += [f"Clip {clip['id']} ({f}): {n}" for n in dict.fromkeys(notes)]
        outputs += export_clip(framed, client, topic, clip["id"], plats, f, ass_files, extra_fonts, args.quality)
    return outputs


def do_make(a):
    cj = topic_dir(a.client, a.topic) / "clips.json" if not a.clips_json else resolve(str(a.clips_json))
    data = load_json(cj)
    if a.clips:
        want = {int(x) for x in a.clips.split(",")}
        chosen = [c for c in data["clips"] if c["id"] in want]
    else:
        chosen = [c for c in data["clips"] if c.get("approved")]
    if not chosen:
        fail("No clips are approved yet.", "show the list to the owner, then run: clips.py approve <clips.json> --ids 1,2 (or --all).")
    brief = load_brief(a.client)
    if brief:
        say("Using the client's brand brief (colors and fonts).")
    targets = parse_targets(a.platforms or [], (a.also or "").split(",") if a.also else [], brief)
    say(f"Making {len(chosen)} clip(s) for: " + ", ".join(f"{p} ({f})" for p, f in targets))
    start, notes, outputs = time.time(), [], []
    for clip in chosen:
        outputs += make_one(clip, data, targets, a, brief, notes)
    say(f"\nDone in {(time.time() - start) / 60:.1f} minutes. Files:")
    for o in outputs:
        say(f"  {o}")
    for n in notes:
        say(f"NOTE: {n}")
    say("\nChecking every file...")
    check = ROOT / "check.py"
    code = subprocess.run([sys.executable, str(check), *map(str, outputs)]).returncode
    return code


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("transcribe")
    t.add_argument("--client", required=True)
    t.add_argument("--video", type=Path, required=True)
    t.add_argument("--topic")
    t.add_argument("--model", default="small")
    t.add_argument("--language")
    m = sub.add_parser("make")
    m.add_argument("--client", required=True)
    m.add_argument("--topic", required=True)
    m.add_argument("--clips-json", type=Path)
    m.add_argument("--clips", help="clip numbers, e.g. 1,3. Default: all approved")
    m.add_argument("--platforms", action="append", type=lambda s: s.split(","), help="e.g. reels,tiktok,shorts or linkedin:square")
    m.add_argument("--also", help="extra shapes: square,landscape")
    m.add_argument("--quality", choices=list(QUALITY), default="fast")
    m.add_argument("--silence", choices=list(LEVELS), default="normal")
    m.add_argument("--model", default="small")
    m.add_argument("--no-hook", action="store_true")
    m.add_argument("--no-highlight", action="store_true")
    m.add_argument("--uppercase", action="store_true")
    m.add_argument("--force", action="store_true", help="redo every step, ignore saved work")
    a = ap.parse_args()
    a.client = slug(a.client)
    if getattr(a, "platforms", None):
        a.platforms = [p for grp in a.platforms for p in grp]
    if a.cmd == "transcribe":
        return do_transcribe(a)
    return do_make(a)


if __name__ == "__main__":
    run_main(main)
