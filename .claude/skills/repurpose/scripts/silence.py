"""Step 4: remove silences and dead pauses with auto-editor.

Usage:
  python silence.py input.mp4 output.mp4 [--level gentle|normal|tight]
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from common import fail, probe, run, run_main

# how much breathing room is kept around speech
LEVELS = {"gentle": "0.25sec", "normal": "0.15sec", "tight": "0.08sec"}


def find_auto_editor() -> str:
    exe = "auto-editor.exe" if os.name == "nt" else "auto-editor"
    local = Path(sys.executable).parent / exe
    if local.exists():
        return str(local)
    found = shutil.which("auto-editor")
    if found:
        return found
    fail("auto-editor is not installed.", "run setup.ps1 again (it installs auto-editor).")


def remove_silence(src: Path, dst: Path, level: str = "normal", threshold: float = 0.04) -> dict:
    before = probe(src)["duration"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    run([find_auto_editor(), src, "--edit", f"audio:threshold={threshold}", "--margin", LEVELS[level],
         "--when-silent", "cut", "-c:v", "libx264", "-b:v", "25M", "-c:a", "aac", "-b:a", "256k",
         "--progress", "none", "--no-open", "-o", dst], what="Silence removal (auto-editor)")
    if not dst.exists():
        fail("auto-editor did not create the output file.", "run it again; if it keeps failing the clip may have no speech.")
    after = probe(dst)["duration"]
    if after < 3:
        fail(f"Only {after:.1f}s was left after removing silence.", "the sound may be too quiet; try --level gentle or a louder clip.")
    return {"before": before, "after": after}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--level", choices=list(LEVELS), default="normal")
    ap.add_argument("--threshold", type=float, default=0.04, help="volume counted as silence (default 0.04)")
    a = ap.parse_args()
    r = remove_silence(a.input, a.output, a.level, a.threshold)
    print(f"Silence removed: {r['before']:.1f}s -> {r['after']:.1f}s. Saved: {a.output}")


if __name__ == "__main__":
    run_main(main)
