"""Podcast shorts, fully produced: two speakers stacked, slow push-in, branded header with hook,
pop-in captions, original music that ducks under speech, whoosh/ding sound effects, and an end banner
(channel name + person + Subscribe).

Usage (toolkit Python, from the toolkit folder):
  .venv/bin/python .claude/skills/repurpose/scripts/podcast_stack.py --client deanmarjanovic --topic mortgage \
      --ids 1,2,3 --brand "Dean Marjanovic" --role "Ottawa REALTOR" --handle "@the613realtor"

Reads clients/<client>/clips/<topic>/clips.json (times in seconds of the source video), works in
clients/<client>/clips/<topic>/work/, and exports to clients/<client>/final/ (per export.py naming).
Layout assumes a wide two-shot (host left, guest right). Adjust --left/--right crop positions if needed.
"""
import argparse
import json
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[4]
PY = str(ROOT / ".venv" / "bin" / "python")
S = ROOT / ".claude" / "skills" / "repurpose" / "scripts"
FONT = ROOT / "assets" / "fonts" / "Montserrat-ExtraBold.ttf"
YEL, WHITE, NAVY, RED = (255, 201, 40, 255), (255, 255, 255, 255), (20, 32, 46, 245), (229, 72, 77, 255)
BANNER_SECS = 3.6
HDR_H, PANEL_H = 300, 810


def run(cmd, **kw):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print("PROBLEM running:", " ".join(str(c) for c in cmd)[:200], "\n", (r.stderr or r.stdout)[-600:])
        sys.exit(1)
    return r.stdout


def duration(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).strip())


def fmt(t):
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def banner_pngs(work, brand, role, handle):
    f = lambda s: ImageFont.truetype(str(FONT), s)
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((70, 560, 1010, 1260), radius=40, fill=NAVY)
    d.rounded_rectangle((70, 560, 84, 1260), radius=6, fill=YEL)
    def center(txt, y, size, fill):
        font = f(size)
        w = d.textlength(txt, font=font)
        while w > 860 and size > 24:
            size -= 2
            font = f(size)
            w = d.textlength(txt, font=font)
        d.text(((1080 - w) / 2, y), txt, font=font, fill=fill)
    center(brand.upper(), 640, 70, WHITE)
    center(role.upper(), 740, 44, YEL)
    center(handle, 820, 52, WHITE)
    center("NEW VIDEOS EVERY WEEK", 1170, 30, (159, 179, 200, 255))
    img.save(work / "banner.png")
    for name, label, bg in (("sub1", "SUBSCRIBE", RED), ("sub2", "SUBSCRIBED", (58, 74, 92, 255))):
        im = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        dd = ImageDraw.Draw(im)
        dd.rounded_rectangle((200, 930, 880, 1080), radius=75, fill=bg)
        font = f(60)
        w = dd.textlength(label, font=font)
        dd.text(((1080 - w) / 2 + 36, 970), label, font=font, fill=WHITE)
        # bell
        dd.pieslice((278, 972, 338, 1036), 180, 360, fill=WHITE)
        dd.rectangle((278, 1004, 338, 1030), fill=WHITE)
        dd.ellipse((299, 1030, 317, 1046), fill=WHITE)
        im.save(work / f"{name}.png")


def header_ass(path, D, hook, title, brand, role):
    hook_l = r"\N".join(textwrap.wrap(hook.upper(), 26))
    title_l = r"\N".join(textwrap.wrap(title.upper(), 24))
    tag = f"{brand.upper()}  |  {role.upper()}"
    doc = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Tag,Montserrat ExtraBold,30,&H0028C9FF,&H0028C9FF,&H00000000,&H00000000,0,0,0,0,100,100,3,0,1,0,0,5,0,0,0,1
Style: Hook,Montserrat ExtraBold,56,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,0,0,5,0,0,0,1
Style: Title,Montserrat ExtraBold,48,&H0028C9FF,&H0028C9FF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{fmt(0)},{fmt(D)},Tag,,0,0,0,,{{\\pos(540,50)\\fad(300,200)}}{tag}
Dialogue: 1,{fmt(0)},{fmt(3.0)},Hook,,0,0,0,,{{\\pos(540,185)\\fscx55\\fscy55\\t(0,180,\\fscx110\\fscy110)\\t(180,320,\\fscx100\\fscy100)\\fad(0,250)}}{hook_l}
Dialogue: 1,{fmt(3.1)},{fmt(D)},Title,,0,0,0,,{{\\pos(540,185)\\fad(350,200)}}{title_l}
"""
    Path(path).write_text(doc, encoding="utf-8")


def build_clip(a, c, work):
    n = c["rank"]
    cw = work / f"c{n:02d}"
    cw.mkdir(parents=True, exist_ok=True)
    cut, tight = cw / "cut.mp4", cw / "tight.mp4"
    start, end = float(c["start"]), float(c["end"])
    print(f"Clip {n}: cutting {start:.1f}-{end:.1f}s ...", flush=True)
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", start, "-i", a.source, "-t", f"{end - start:.3f}", "-vf", "fps=30",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", cut])
    print(f"Clip {n}: removing silences ...", flush=True)
    run([PY, S / "silence.py", cut, tight, "--level", "normal"])
    D = duration(tight)
    T = D + BANNER_SECS
    print(f"Clip {n}: {D:.1f}s of talking, timing the captions ...", flush=True)
    words = cw / "words.json"
    run([PY, S / "transcribe.py", "--audio-from", tight, "--out", words])
    music = cw / "music.wav"
    run([PY, S / "make_music.py", "--secs", f"{T:.2f}", "--out", music, "--seed", n, "--bpm", 90 + (n % 4) * 3])
    banner_pngs(cw, a.brand, a.role, a.handle)
    zoom = f"(1+0.06*t/{D:.3f})"
    def panel(src_label, x, out):
        return (f"[{src_label}]crop=800:600:{x}:156,"
                f"scale=w='trunc(1080*{zoom}/2)*2':h='trunc(810*{zoom}/2)*2':eval=frame,crop=1080:{PANEL_H},setsar=1[{out}]")
    fc = ";".join([
        "[0:v]split=2[va][vb]",
        panel("va", a.left, "top"),
        panel("vb", a.right, "bot"),
        f"[5:v][top][bot]vstack=inputs=3[stk]",
        f"[stk]drawbox=x=0:y={HDR_H - 3}:w=1080:h=6:color=0xFFC928:t=fill,drawbox=x=0:y={HDR_H + PANEL_H - 3}:w=1080:h=6:color=0xFFC928:t=fill,"
        f"tpad=stop_mode=clone:stop_duration={BANNER_SECS},"
        f"boxblur=luma_radius=40:luma_power=3:enable='gte(t,{D:.3f})',"
        f"drawbox=x=0:y=0:w=1080:h=1920:color=black@0.62:t=fill:enable='gte(t,{D:.3f})'[base]",
        f"[6:v]format=rgba,fade=in:st={D:.3f}:d=0.4:alpha=1[ban]",
        f"[7:v]format=rgba,fade=in:st={D + 0.3:.3f}:d=0.3:alpha=1[s1]",
        f"[8:v]format=rgba,fade=in:st={D + 1.7:.3f}:d=0.2:alpha=1[s2]",
        "[base][ban]overlay=0:0:eof_action=pass[o1]",
        f"[o1][s1]overlay=0:0:eof_action=pass:enable='lt(t,{D + 1.7:.3f})'[o2]",
        "[o2][s2]overlay=0:0:eof_action=pass,format=yuv420p[v]",
        # audio: voice, ducked music, whoosh at start and at the banner, ding on subscribe
        f"[0:a]apad=pad_dur={BANNER_SECS},asplit=2[voice][sc]",
        "[1:a]volume=0.50[mus]",
        "[mus][sc]sidechaincompress=threshold=0.015:ratio=9:attack=15:release=400:makeup=1[duck]",
        "[2:a]volume=0.55,asplit=2[w1][w2]",
        f"[w2]adelay={int(D * 1000)}|{int(D * 1000)}[w2d]",
        f"[3:a]volume=0.5,adelay={int((D + 1.7) * 1000)}|{int((D + 1.7) * 1000)}[dd]",
        "[voice][duck][w1][w2d][dd]amix=inputs=5:duration=longest:normalize=0,alimiter=limit=0.95[aout]",
    ])
    comp = cw / "composite.mp4"
    print(f"Clip {n}: building the picture, music and effects ...", flush=True)
    run(["ffmpeg", "-y", "-loglevel", "error",
         "-i", tight, "-i", music, "-i", work / "sfx" / "whoosh.wav", "-i", work / "sfx" / "ding.wav",
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
         "-f", "lavfi", "-i", f"color=c=0x0E1722:s=1080x{HDR_H}:r=30:d={D:.3f}",
         "-loop", "1", "-framerate", "30", "-t", f"{T:.3f}", "-i", cw / "banner.png",
         "-loop", "1", "-framerate", "30", "-t", f"{T:.3f}", "-i", cw / "sub1.png",
         "-loop", "1", "-framerate", "30", "-t", f"{T:.3f}", "-i", cw / "sub2.png",
         "-filter_complex", fc, "-map", "[v]", "-map", "[aout]", "-t", f"{T:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", "-r", "30",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", comp])
    caps, hdr = cw / "captions.ass", cw / "header.ass"
    run([PY, S / "captions_pop.py", "--words", words, "--out", caps, "--res", "1080x1920", "--y", "1800", "--size", "68",
         "--max-chars", "17", "--max-words", "3", "--keys", a.keys])
    header_ass(hdr, D, c["hook"], c["title"], a.brand, a.role)
    print(f"Clip {n}: final export ...", flush=True)
    out = run([PY, S / "export.py", comp, "--client", a.client, "--topic", a.topic, "--clip", n, "--platforms", "reels",
               "--ass", caps, "--ass", hdr])
    print(out.strip().splitlines()[-1] if out.strip() else "exported", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", required=True)
    ap.add_argument("--topic", required=True)
    ap.add_argument("--ids", default="")
    ap.add_argument("--brand", default="Dean Marjanovic")
    ap.add_argument("--role", default="Ottawa REALTOR")
    ap.add_argument("--handle", default="@the613realtor")
    ap.add_argument("--left", type=int, default=140, help="x of the left speaker's crop (800x600) in the 1920x1080 source")
    ap.add_argument("--right", type=int, default=1120, help="x of the right speaker's crop")
    ap.add_argument("--keys", default="condo fee,30K,crypto,three months,co-signing,penalty,variable,fixed,prepayment,lowest rate,forever home,rate hold,lawyer,approved,pre-approval")
    a = ap.parse_args()
    base = ROOT / "clients" / a.client / "clips" / a.topic
    data = json.load(open(base / "clips.json"))
    a.source = str(ROOT / data["source"])
    work = base / "work"
    (work / "sfx").mkdir(parents=True, exist_ok=True)
    if not (work / "sfx" / "whoosh.wav").exists():
        run([PY, S / "make_music.py", "--sfx-dir", work / "sfx"])
    ids = [int(x) for x in a.ids.split(",") if x] or [c["rank"] for c in data["clips"]]
    for c in data["clips"]:
        if c["rank"] in ids:
            build_clip(a, c, work)


if __name__ == "__main__":
    main()
