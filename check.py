"""Check every exported clip: length, size, frame rate, codecs, loudness. Prints a simple PASS/FAIL table.

Usage:
  python check.py clients\\drsmith\\final            (a whole folder)
  python check.py clip1.mp4 clip2.mp4              (single files)
  python check.py                                   (every client's final folder)

Needs only FFmpeg/FFprobe. Exit code is 0 when everything passes, 1 otherwise.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAX_SECONDS = 60.0
SIZES = {(1080, 1920): "9:16", (1080, 1080): "1:1", (1920, 1080): "16:9"}
TARGET_LUFS, LUFS_TOLERANCE = -14.0, 1.5
NAME_RE = re.compile(r"^[a-z0-9]+_[a-z0-9]+_clip\d{2}_[a-z0-9]+\.mp4$")


def tool(name: str) -> str:
    p = shutil.which(name)
    if not p:
        print(f"PROBLEM: {name} is not installed or not on the PATH.\nFIX: run setup.ps1 again, then reopen the window.")
        sys.exit(2)
    return p


def probe(path: Path) -> dict:
    out = subprocess.run([tool("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                          str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(out.stdout or "{}") if out.returncode == 0 else {}


def loudness(path: Path):
    p = subprocess.run([tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    if not m:
        return None
    v = json.loads(m.group(0))["input_i"]
    return None if v in ("-inf", "inf") else float(v)


def check_file(path: Path) -> list:
    """Return a list of (label, ok, shown_value)."""
    data = probe(path)
    if not data:
        return [("File", False, "cannot be read")]
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    rows = []
    dur = float(data.get("format", {}).get("duration") or 0)
    rows.append(("Length", 0 < dur < MAX_SECONDS, f"{dur:.1f}s"))
    if v:
        size = (int(v["width"]), int(v["height"]))
        rows.append(("Size", size in SIZES, f"{size[0]}x{size[1]}"))
        num, _, den = (v.get("avg_frame_rate") or "0/1").partition("/")
        fps = float(num) / float(den) if float(den or 0) else 0.0
        rows.append(("FPS", abs(fps - 30) < 0.1, f"{fps:.2f}"))
        rows.append(("Video", v.get("codec_name") == "h264" and v.get("pix_fmt") == "yuv420p",
                     f"{v.get('codec_name')}/{v.get('pix_fmt')}"))
    else:
        rows += [("Size", False, "no picture"), ("FPS", False, "-"), ("Video", False, "none")]
    rows.append(("Audio", bool(a) and a.get("codec_name") == "aac", a.get("codec_name") if a else "none"))
    lufs = loudness(path) if a else None
    rows.append(("Loudness", lufs is not None and abs(lufs - TARGET_LUFS) <= LUFS_TOLERANCE,
                 f"{lufs:.1f} LUFS" if lufs is not None else "silent"))
    rows.append(("Name", bool(NAME_RE.match(path.name)), "ok" if NAME_RE.match(path.name) else "wrong pattern"))
    return rows


def collect(args: list) -> list:
    paths = []
    targets = [Path(a) for a in args] or sorted((ROOT / "clients").glob("*/final"))
    for t in targets:
        t = t if t.is_absolute() or t.exists() else ROOT / t
        if t.is_dir():
            paths += sorted(t.glob("*.mp4"))
        elif t.exists():
            paths.append(t)
        else:
            print(f"PROBLEM: {t} does not exist.\nFIX: check the folder or file name.")
            sys.exit(2)
    return paths


def main() -> int:
    files = collect(sys.argv[1:])
    if not files:
        print("No exported clips found to check.")
        return 1
    cols = ["Length", "Size", "FPS", "Video", "Audio", "Loudness", "Name"]
    results = {f: dict((r[0], r) for r in check_file(f)) for f in files}
    namew = max(len(f.name) for f in files)
    head = f"{'File':<{namew}}  " + "  ".join(f"{c:<16}" for c in cols) + "  Result"
    print(head)
    print("-" * len(head))
    bad = 0
    for f, r in results.items():
        cells, ok_all = [], True
        for c in cols:
            _, ok, val = r.get(c, (c, False, "-"))
            ok_all &= ok
            cells.append(f"{('PASS' if ok else 'FAIL') + ' ' + str(val):<16}")
        bad += not ok_all
        print(f"{f.name:<{namew}}  " + "  ".join(cells) + f"  {'PASS' if ok_all else 'FAIL'}")
    print("-" * len(head))
    print(f"{len(files) - bad} of {len(files)} clips passed." + ("" if not bad else f" {bad} need fixing."))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
