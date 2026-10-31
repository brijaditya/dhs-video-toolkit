"""Add a 3-second end card ("Watch the full video on my YouTube channel" + bouncing down arrow).

Usage (from the toolkit folder, with the toolkit Python):
  .venv/bin/python .claude/skills/repurpose/scripts/endcard.py --client NAME --clips 1,3,4 [--secs 3]
        [--line1 "Watch the full video"] [--line2 "on my YouTube channel"]

The last picture is frozen and dimmed for a few seconds, a clean card appears and an arrow bounces
downward. The original export is kept as clips/<topic>/clipNN/before_endcard.mp4 and the final file
is replaced (same name). Run check.py afterwards.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[4]
FONT = ROOT / "assets" / "fonts" / "Montserrat-ExtraBold.ttf"
NAVY = (20, 32, 46, 245)
WHITE = (255, 255, 255, 255)
YELLOW = (255, 201, 40, 255)


def build_card(path, line1, line2):
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = (80, 640, 1000, 1040)
    d.rounded_rectangle(box, radius=36, fill=NAVY)
    d.rounded_rectangle((box[0], box[1], box[0] + 14, box[3]), radius=6, fill=YELLOW)
    f1 = ImageFont.truetype(str(FONT), 80)
    f2 = ImageFont.truetype(str(FONT), 62)
    for text, font, fill, y in ((line1, f1, WHITE, 740), (line2, f2, YELLOW, 880)):
        w = d.textlength(text, font=font)
        d.text(((1080 - w) / 2, y), text, font=font, fill=fill)
    img.save(path)


def build_arrow(path):
    img = Image.new("RGBA", (260, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((95, 0, 165, 150), radius=14, fill=YELLOW)
    d.polygon([(10, 130), (250, 130), (130, 290)], fill=YELLOW)
    img.save(path)


def duration(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout
    return float(out.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", required=True)
    ap.add_argument("--clips", required=True, help="clip numbers, e.g. 1,3,4")
    ap.add_argument("--secs", type=float, default=3.0)
    ap.add_argument("--line1", default="Watch the full video")
    ap.add_argument("--line2", default="on my YouTube channel")
    a = ap.parse_args()

    cdir = ROOT / "clients" / a.client
    final = cdir / "final"
    work = cdir / "clips" / "_endcard"
    work.mkdir(parents=True, exist_ok=True)
    card, arrow = work / "card.png", work / "arrow.png"
    build_card(card, a.line1, a.line2)
    build_arrow(arrow)

    for n in [int(x) for x in a.clips.split(",")]:
        pat = re.compile(rf"_clip{n:02d}_")
        files = [f for f in sorted(final.glob("*.mp4")) if pat.search(f.name)]
        if not files:
            print(f"Clip {n}: no finished file found, skipped")
            continue
        for src in files:
            topic = src.name.split("_clip")[0].split("_", 1)[-1]
            keep = cdir / "clips" / topic / f"clip{n:02d}" / "before_endcard.mp4"
            if not keep.parent.exists():
                keep = work / f"clip{n:02d}_{src.name}"
            if not keep.exists():
                shutil.copy2(src, keep)
            base = keep  # always start from the untouched export
            D = duration(base)
            S = a.secs
            tmp = work / src.name
            fc = (
                f"[0:v]tpad=stop_mode=clone:stop_duration={S},fps=30,"
                f"boxblur=luma_radius=40:luma_power=3:enable='gte(t,{D:.3f})',"
                f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.6:t=fill:enable='gte(t,{D:.3f})'[v0];"
                f"[1:v]format=rgba,fade=in:st={D:.3f}:d=0.35:alpha=1[card];"
                f"[2:v]format=rgba,fade=in:st={D + 0.2:.3f}:d=0.35:alpha=1[arr];"
                f"[v0][card]overlay=0:0:eof_action=pass[v1];"
                f"[v1][arr]overlay=x=(W-w)/2:y='1560+30*sin(9*(t-{D:.3f}))':eof_action=pass,format=yuv420p[v]"
            )
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(base),
                   "-loop", "1", "-framerate", "30", "-t", f"{D + S:.3f}", "-i", str(card),
                   "-loop", "1", "-framerate", "30", "-t", f"{D + S:.3f}", "-i", str(arrow),
                   "-filter_complex", fc, "-map", "[v]", "-map", "0:a:0",
                   "-af", f"apad=pad_dur={S}", "-t", f"{D + S:.3f}",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-profile:v", "high",
                   "-r", "30", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                   "-movflags", "+faststart", str(tmp)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"Clip {n}: PROBLEM adding the end card: {r.stderr.strip()[-300:]}")
                sys.exit(1)
            shutil.move(str(tmp), str(src))
            print(f"Clip {n}: end card added ({D:.1f}s -> {D + S:.1f}s)  {src.name}")


if __name__ == "__main__":
    main()
