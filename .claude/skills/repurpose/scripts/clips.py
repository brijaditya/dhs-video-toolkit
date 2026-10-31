"""Step 2 helper: check clips.json, snap cuts to word edges, show the ranked list, record approval.

clips.json format (Claude writes it after reading the transcript):
{
  "client": "drsmith", "topic": "sleep", "source": "clients/drsmith/raw/sleep_podcast.mp4",
  "transcript": "clients/drsmith/transcripts/sleep_podcast.json",
  "clips": [
    {"rank": 1, "start": 125.4, "end": 171.0, "hook": "You are sleeping wrong",
     "title": "Why 8 hours is a myth", "caption": "Sleep quality beats hours. ...",
     "hashtags": ["#sleep", "#health", "#wellness"], "why": "Strong claim, full idea, useful tip"}
  ]
}

Usage:
  python clips.py validate clients/drsmith/clips/sleep/clips.json     (fixes cut points, checks fields)
  python clips.py show     clients/drsmith/clips/sleep/clips.json     (the list to show the owner)
  python clips.py approve  clients/drsmith/clips/sleep/clips.json --ids 1,2,5   (or --all)
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import ToolkitError, fail, fmt_time, load_json, parse_time, run_main, save_json, slug, ROOT

MIN_LEN, MAX_LEN = 12.0, 58.0   # seconds, before silence removal (final must be < 60)
START_PAD, END_PAD = 0.12, 0.30


def resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() or path.exists() else ROOT / path


def snap(clip: dict, words: list) -> None:
    """Move the start to the beginning of a word and the end to the end of a word."""
    s, e = parse_time(clip["start"]), parse_time(clip["end"])
    if words:
        starts = [w for w in words if w["end"] > s] or words
        w0 = min(starts, key=lambda w: abs(w["start"] - s) if w["start"] >= s - 0.5 else 1e9)
        s = max(0.0, w0["start"] - START_PAD)
        ends = [w for w in words if w["start"] < e] or words
        w1 = min(ends, key=lambda w: abs(w["end"] - e) if w["end"] <= e + 0.5 else 1e9)
        e = w1["end"] + END_PAD
        if words and e > words[-1]["end"] + 1.0:
            e = words[-1]["end"] + 0.5
    clip["start"], clip["end"] = round(s, 2), round(e, 2)


def clean_tags(tags) -> list:
    if isinstance(tags, str):
        tags = re.split(r"[,\s]+", tags)
    out = []
    for t in tags:
        t = "#" + re.sub(r"[^A-Za-z0-9_]", "", str(t))
        if len(t) > 1 and t.lower() not in [x.lower() for x in out]:
            out.append(t)
    return out


def validate(path: Path) -> dict:
    data = load_json(path)
    for key in ("client", "topic", "source", "clips"):
        if key not in data:
            fail(f"clips.json is missing '{key}'.", "add it and run validate again.")
    words = []
    if data.get("transcript"):
        tpath = resolve(data["transcript"])
        if tpath.exists():
            words = load_json(tpath).get("words", [])
    problems = []
    for i, c in enumerate(data["clips"], 1):
        for f in ("start", "end", "hook", "title", "caption"):
            v = c.get(f)
            if v is None or v == "" or (f != "start" and not v):
                problems.append(f"clip {i}: '{f}' is empty")
        if problems and problems[-1].startswith(f"clip {i}"):
            continue
        snap(c, words)
        c["hashtags"] = clean_tags(c.get("hashtags", []))
        length = c["end"] - c["start"]
        if length < MIN_LEN:
            problems.append(f"clip {i}: only {length:.0f}s long (needs at least {MIN_LEN:.0f}s)")
        if length > MAX_LEN:
            problems.append(f"clip {i}: {length:.0f}s is too long (max {MAX_LEN:.0f}s so the final stays under 60s)")
        if not 3 <= len(c["hashtags"]) <= 5:
            problems.append(f"clip {i}: needs 3 to 5 hashtags (has {len(c['hashtags'])})")
        if len(c["hook"].split()) > 14:
            problems.append(f"clip {i}: hook is too long for the screen (max 14 words)")
    if problems:
        fail("clips.json has problems: " + "; ".join(problems) + ".", "correct those clips and run validate again.")
    data["clips"].sort(key=lambda c: c.get("rank", 999))
    for n, c in enumerate(data["clips"], 1):
        c["rank"] = n
        c["id"] = n
        c.setdefault("approved", False)
    save_json(path, data)
    return data


def show(data: dict) -> str:
    out = [f"Ranked clips for {data['client']} / {data['topic']}  (best first)", ""]
    for c in data["clips"]:
        out += [
            f"#{c['rank']}  {fmt_time(c['start'])} - {fmt_time(c['end'])}  ({c['end'] - c['start']:.0f}s)"
            + ("   [APPROVED]" if c.get("approved") else ""),
            f"   Hook:     {c['hook']}",
            f"   Title:    {c['title']}",
            f"   Caption:  {c['caption']}",
            f"   Hashtags: {' '.join(c['hashtags'])}",
        ]
        if c.get("why"):
            out.append(f"   Why:      {c['why']}")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["validate", "show", "approve"])
    ap.add_argument("clips_json", type=Path)
    ap.add_argument("--ids", help="comma list of clip numbers to approve")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    path = resolve(str(a.clips_json))
    if a.action == "validate":
        data = validate(path)
        print("clips.json is OK. Cut points were moved to the nearest word edges.\n")
        print(show(data))
    elif a.action == "show":
        print(show(load_json(path)))
    else:
        data = load_json(path)
        ids = {int(x) for x in a.ids.split(",")} if a.ids else set()
        if not (a.all or ids):
            fail("No clips were chosen to approve.", "use --ids 1,2,3 or --all.")
        for c in data["clips"]:
            if a.all or c["id"] in ids:
                c["approved"] = True
        save_json(path, data)
        print("Approved clips:", ", ".join(str(c["id"]) for c in data["clips"] if c.get("approved")))


if __name__ == "__main__":
    run_main(main)
