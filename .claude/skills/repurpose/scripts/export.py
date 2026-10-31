"""Step 8: final export. Burns in captions + hook, sets loudness to -14 LUFS, names files per platform.

Usage:
  python export.py reframed.mp4 --client drsmith --topic sleep --clip 1 --platforms reels,tiktok,shorts \
      --ass clip.captions.ass --ass clip.hook.ass [--format vertical] [--quality fast|best]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path

from common import (FORMATS, FONTS_DIR, FPS, PLATFORMS, client_dirs, ensure_client, fail, ffmpeg, final_name,
                    normalize_platform, probe, run, run_main)

TARGET_I, TARGET_TP, TARGET_LRA = -14.0, -1.5, 11.0
QUALITY = {"fast": ["-preset", "veryfast", "-crf", "20"], "best": ["-preset", "slow", "-crf", "17"]}


def measure_loudness(src: Path) -> dict:
    p = run([ffmpeg(), "-hide_banner", "-nostats", "-i", src, "-vn", "-af",
             f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json", "-f", "null", "-"],
            what="Measuring loudness")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    if not m:
        fail("Could not measure the loudness.", "check the clip has a sound track.")
    d = json.loads(m.group(0))
    if d["input_i"] in ("-inf", "inf"):
        fail("The clip is completely silent.", "check the sound in the original video.")
    return d


def encode_final(src: Path, out: Path, fmt: str, ass_files: list[Path], extra_fonts: list[Path], quality: str = "fast") -> dict:
    W, H = FORMATS[fmt]
    src, out = Path(src).resolve(), Path(out).resolve()      # we run FFmpeg from a temp folder
    ass_files = [Path(a).resolve() for a in ass_files]
    m = measure_loudness(src)
    af = (f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:measured_I={m['input_i']}:"
          f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
          f"offset={m['target_offset']}:linear=true,aresample=48000")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dhs_") as tmp:
        work = Path(tmp)
        fonts = work / "fonts"
        fonts.mkdir()
        for folder in [FONTS_DIR, *extra_fonts]:
            for f in folder.glob("*"):
                if f.suffix.lower() in (".ttf", ".otf"):
                    shutil.copy2(f, fonts / f.name)
        vf = [f"scale={W}:{H}:force_original_aspect_ratio=decrease", f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2", "setsar=1"]
        for i, a in enumerate(ass_files):
            name = f"sub{i}.ass"
            shutil.copy2(a, work / name)
            vf.append(f"ass={name}:fontsdir=fonts")     # relative paths: avoids Windows drive-letter escaping
        vf += [f"fps={FPS}", "format=yuv420p"]
        tmp_out = work / "out.mp4"
        run([ffmpeg(), "-y", "-loglevel", "error", "-i", src, "-vf", ",".join(vf), "-af", af,
             "-c:v", "libx264", *QUALITY[quality], "-profile:v", "high", "-maxrate", "16M", "-bufsize", "32M",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", tmp_out],
            cwd=work, what="Final export")
        shutil.move(str(tmp_out), out)
    return {"measured_lufs": float(m["input_i"])}


def export_clip(src: Path, client: str, topic: str, clip_no: int, platforms: list[str], fmt: str | None,
                ass_files: list[Path], extra_fonts: list[Path] | None = None, quality: str = "fast",
                out_dir: Path | None = None) -> list[Path]:
    """Encode once per format, then save one file per platform with the right name."""
    d = ensure_client(client)
    out_dir = out_dir or d["final"]
    plats = [normalize_platform(p) for p in platforms]
    by_fmt: dict[str, list[str]] = {}
    for p in plats:
        by_fmt.setdefault(fmt or PLATFORMS[p], []).append(p)
    outputs = []
    for f, plist in by_fmt.items():
        first = out_dir / final_name(client, topic, clip_no, plist[0])
        encode_final(src, first, f, ass_files, extra_fonts or [], quality)
        outputs.append(first)
        for p in plist[1:]:
            dest = out_dir / final_name(client, topic, clip_no, p)
            shutil.copy2(first, dest)
            outputs.append(dest)
    dur = probe(outputs[0])["duration"]
    if dur >= 60:
        print(f"WARNING: the clip is {dur:.1f}s, short-form must stay under 60s. Choose a shorter moment.")
    return outputs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path)
    ap.add_argument("--client", required=True)
    ap.add_argument("--topic", required=True)
    ap.add_argument("--clip", type=int, required=True)
    ap.add_argument("--platforms", default="reels", help="comma list: tiktok,reels,shorts,linkedin,facebook,x,youtube,square,landscape")
    ap.add_argument("--format", choices=list(FORMATS), help="force one format for all listed platforms")
    ap.add_argument("--ass", action="append", type=Path, default=[])
    ap.add_argument("--quality", choices=list(QUALITY), default="fast")
    ap.add_argument("--out-dir", type=Path)
    a = ap.parse_args()
    extra = [f for f in [client_dirs(a.client)["fonts"]] if f.exists()]
    outs = export_clip(a.input, a.client, a.topic, a.clip, a.platforms.split(","), a.format, a.ass, extra,
                       a.quality, a.out_dir)
    for o in outs:
        print("Exported:", o)


if __name__ == "__main__":
    run_main(main)
