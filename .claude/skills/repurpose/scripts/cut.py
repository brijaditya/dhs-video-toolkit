"""Step 3: cut one clip out of the long video with FFmpeg (30 fps, filler words "um/uh" removed).

Usage:
  python cut.py --clips-json clients/drsmith/clips/sleep/clips.json --clip 1
"""
from __future__ import annotations

import argparse
from pathlib import Path

from common import FPS, ffmpeg, load_json, run, run_main, fail, topic_dir, ROOT, words_in_range

FILLERS = {"um", "uh", "uhm", "umm", "uhh", "er", "erm", "ah", "hmm", "mm", "mhm", "eh"}


def filler_cuts(words: list, start: float, end: float) -> list:
    """(start, end) ranges inside the clip occupied by filler words like um/uh."""
    cuts = []
    for w in words_in_range(words, start, end):
        token = w["word"].lower().strip(" .,!?;:-…")
        if token in FILLERS and w["end"] - w["start"] >= 0.12:
            cuts.append((max(start, w["start"] - 0.03), min(end, w["end"] + 0.05)))
    return cuts


def keep_segments(start: float, end: float, cuts: list) -> list:
    segs, cur = [], start
    for a, b in sorted(cuts):
        if a - cur >= 0.4:
            segs.append((cur, a))
        cur = max(cur, b)
    if end - cur >= 0.2:
        segs.append((cur, end))
    return segs or [(start, end)]


ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart"]


def cut_clip(source: Path, start: float, end: float, out: Path, words: list | None = None) -> dict:
    cuts = filler_cuts(words or [], start, end)
    segs = keep_segments(start, end, cuts)
    out.parent.mkdir(parents=True, exist_ok=True)
    if len(segs) == 1:
        s, e = segs[0]
        run([ffmpeg(), "-y", "-loglevel", "error", "-ss", f"{s:.3f}", "-i", source, "-t", f"{e - s:.3f}",
             "-vf", f"fps={FPS}", *ENC, out], what="Cutting the clip")
    else:
        parts, labels = [], ""
        for i, (s, e) in enumerate(segs):
            d = e - s
            parts.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}]")
            parts.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:d=0.01,afade=t=out:st={max(d - 0.01, 0):.3f}:d=0.01[a{i}]")
            labels += f"[v{i}][a{i}]"
        parts.append(f"{labels}concat=n={len(segs)}:v=1:a=1[vc][ac];[vc]fps={FPS}[vo]")
        run([ffmpeg(), "-y", "-loglevel", "error", "-i", source, "-filter_complex", ";".join(parts),
             "-map", "[vo]", "-map", "[ac]", *ENC, out], what="Cutting the clip")
    return {"fillers_removed": len(cuts), "segments": len(segs)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clips-json", type=Path, required=True)
    ap.add_argument("--clip", type=int, required=True)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    from clips import resolve
    data = load_json(resolve(str(a.clips_json)))
    clip = next((c for c in data["clips"] if c["id"] == a.clip), None)
    if not clip:
        fail(f"There is no clip number {a.clip} in clips.json.", "check the numbers with: clips.py show.")
    source = resolve(data["source"])
    if not source.exists():
        fail(f"The source video {source} was not found.", "put the video in the client's raw folder.")
    words = []
    if data.get("transcript") and resolve(data["transcript"]).exists():
        words = load_json(resolve(data["transcript"])).get("words", [])
    out = a.out or topic_dir(data["client"], data["topic"]) / f"clip{clip['id']:02d}" / "1_cut.mp4"
    info = cut_clip(source, clip["start"], clip["end"], out, words)
    print(f"Cut saved: {out}  (removed {info['fillers_removed']} filler words)")


if __name__ == "__main__":
    run_main(main)
