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
import re
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
HDR_H, PANEL_H = 420, 750
ANTON = ROOT / "assets" / "fonts" / "Anton-Regular.ttf"


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


def banner_pngs(work, brand, role, handle, team=""):
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
    if team:
        center(team.upper(), 894, 32, (201, 176, 110, 255))
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


def fit_lines(text, max_w, max_h, max_size, min_size):
    """Biggest Anton size at which the text fits the box; returns (size, lines)."""
    words = text.upper().split()
    lines = []
    for size in range(max_size, min_size - 1, -2):
        font = ImageFont.truetype(str(ANTON), size)
        lines, cur = [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if font.getlength(t) <= max_w:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if len(lines) * size * 1.22 <= max_h and all(font.getlength(l) <= max_w for l in lines):
            return size, lines
    return min_size, lines


def header_ass(path, D, hook, title, brand, role):
    hs, hl = fit_lines(hook, 980, 290, 120, 56)
    ts, tl = fit_lines(title, 980, 290, 130, 56)
    hook_l, title_l = r"\N".join(hl), r"\N".join(tl)
    asc, desc = ImageFont.truetype(str(ANTON), 100).getmetrics()
    k = (asc + desc) / 100.0   # the subtitle renderer sizes by line height, so scale up to get the size we measured
    hs, ts = int(hs * k), int(ts * k)
    tag = f"{brand.upper()}  |  {role.upper()}"
    cy = HDR_H // 2 + 28
    doc = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Tag,Montserrat ExtraBold,40,&H0028C9FF,&H0028C9FF,&H00000000,&H00000000,0,0,0,0,100,100,3,0,1,0,0,5,0,0,0,1
Style: Hook,Anton,{hs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,0,0,5,0,0,0,1
Style: Title,Anton,{ts},&H0028C9FF,&H0028C9FF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{fmt(0)},{fmt(D)},Tag,,0,0,0,,{{\\pos(540,56)\\fad(300,200)}}{tag}
Dialogue: 1,{fmt(0)},{fmt(3.0)},Hook,,0,0,0,,{{\\pos(540,{cy})\\fscx55\\fscy55\\t(0,180,\\fscx110\\fscy110)\\t(180,320,\\fscx100\\fscy100)\\fad(0,250)}}{hook_l}
Dialogue: 1,{fmt(3.1)},{fmt(D)},Title,,0,0,0,,{{\\pos(540,{cy})\\fad(350,200)}}{title_l}
"""
    Path(path).write_text(doc, encoding="utf-8")


def header_ass_old(path, D, hook, title, brand, role):
    hook_l = r"\N".join(textwrap.wrap(hook.upper(), 23))
    title_l = r"\N".join(textwrap.wrap(title.upper(), 21))
    tag = f"{brand.upper()}  |  {role.upper()}"
    doc = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Tag,Montserrat ExtraBold,34,&H0028C9FF,&H0028C9FF,&H00000000,&H00000000,0,0,0,0,100,100,3,0,1,0,0,5,0,0,0,1
Style: Hook,Montserrat ExtraBold,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,0,0,5,0,0,0,1
Style: Title,Montserrat ExtraBold,58,&H0028C9FF,&H0028C9FF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{fmt(0)},{fmt(D)},Tag,,0,0,0,,{{\\pos(540,46)\\fad(300,200)}}{tag}
Dialogue: 1,{fmt(0)},{fmt(3.0)},Hook,,0,0,0,,{{\\pos(540,180)\\fscx55\\fscy55\\t(0,180,\\fscx110\\fscy110)\\t(180,320,\\fscx100\\fscy100)\\fad(0,250)}}{hook_l}
Dialogue: 1,{fmt(3.1)},{fmt(D)},Title,,0,0,0,,{{\\pos(540,180)\\fad(350,200)}}{title_l}
"""
    Path(path).write_text(doc, encoding="utf-8")


def detect_speakers(video, D):
    """Who is speaking, from mouth movement: list of ("top"|"bot", start, end). top = left speaker, bot = right speaker."""
    import cv2
    import numpy as np
    HOST, GUEST = (460, 330, 700, 480), (1400, 310, 1640, 460)  # face areas in the 1920x1080 picture
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    prev, eh, eg = None, [], []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        h = cv2.resize(g[HOST[1]:HOST[3], HOST[0]:HOST[2]], (48, 30)).astype(np.float32)
        u = cv2.resize(g[GUEST[1]:GUEST[3], GUEST[0]:GUEST[2]], (48, 30)).astype(np.float32)
        if prev is not None:
            eh.append(float(np.abs(h - prev[0]).mean()))
            eg.append(float(np.abs(u - prev[1]).mean()))
        prev = (h, u)
    cap.release()
    b = max(1, int(fps * 0.2))
    nb = len(eh) // b
    if nb < 10:
        return []
    H = np.array([np.mean(eh[i * b:(i + 1) * b]) for i in range(nb)])
    G = np.array([np.mean(eg[i * b:(i + 1) * b]) for i in range(nb)])
    r = np.log((H / (np.percentile(H, 70) + 1e-6) + 1e-3) / (G / (np.percentile(G, 70) + 1e-6) + 1e-3))
    sign = np.where(r > 0.15, 1.0, np.where(r < -0.15, -1.0, 0.0))
    k = 7
    sm = np.convolve(np.pad(sign, (k // 2, k // 2), mode="edge"), np.ones(k), mode="valid")
    lab = np.where(sm > 0.5, 1, np.where(sm < -0.5, -1, 0))
    last = next((int(x) for x in lab if x != 0), 1)
    out = []
    for x in lab:
        if x != 0:
            last = int(x)
        out.append(last)
    segs, st = [], 0
    for i in range(1, len(out) + 1):
        if i == len(out) or out[i] != out[st]:
            segs.append([out[st], st * 0.2, i * 0.2])
            st = i
    merged = []
    for sg in segs:  # keep segments of at least 1 second, so the picture never flickers
        if merged and (sg[2] - sg[1] < 1.0 or merged[-1][0] == sg[0]):
            merged[-1][2] = sg[2]
        else:
            merged.append(sg)
    merged[0][1] = 0.0
    merged[-1][2] = D
    return [("top" if w > 0 else "bot", a0, b0) for w, a0, b0 in merged]


def s_expr(segs, who, fade=0.3):
    """ffmpeg expression: 1 while `who` is speaking (eased in and out), else 0."""
    terms = []
    for i, (w, a0, b0) in enumerate(segs):
        if w != who:
            continue
        a1 = -fade if i == 0 else a0
        terms.append(f"min(max((t-{a1:.2f})/{fade},0),1)*(1-min(max((t-{b0:.2f})/{fade},0),1))")
    return "min(1," + "+".join(terms) + ")" if terms else "0"


def build_clip(a, c, work):
    n = c["rank"]
    cw = work / f"c{n:02d}"
    cw.mkdir(parents=True, exist_ok=True)
    cut, tight = cw / "cut.mp4", cw / "tight.mp4"
    start, end = float(c["start"]), float(c["end"])
    print(f"Clip {n}: cutting {start:.1f}-{end:.1f}s ...", flush=True)
    if a.fresh or not cut.exists():
      run(["ffmpeg", "-y", "-loglevel", "error", "-ss", start, "-i", a.source, "-t", f"{end - start:.3f}", "-vf", "fps=30",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", cut])
    print(f"Clip {n}: removing silences ...", flush=True)
    if a.fresh or not tight.exists():
        run([PY, S / "silence.py", cut, tight, "--level", "normal"])
    D = duration(tight)
    T = D + BANNER_SECS
    print(f"Clip {n}: {D:.1f}s of talking, timing the captions ...", flush=True)
    words = cw / "words.json"
    if a.fresh or not words.exists():
        run([PY, S / "transcribe.py", "--audio-from", tight, "--out", words])
    music = cw / "music.wav"
    if a.fresh or not music.exists():
        run([PY, S / "make_music.py", "--secs", f"{T:.2f}", "--out", music, "--seed", n, "--bpm", 90 + (n % 4) * 3])
    banner_pngs(cw, a.brand, a.role, a.handle, a.team)
    segs = detect_speakers(tight, D) if a.focus > 0 else []
    print(f"Clip {n}: speaker changes found: {len(segs)}", flush=True)
    St, Sb = (s_expr(segs, "top"), s_expr(segs, "bot")) if segs else ("1", "1")
    def panel(src_label, x, out, logo, SX):
        z = f"(1+0.05*t/{D:.3f})*(1+{a.focus}*{SX})"
        return (f"[{src_label}]crop=800:600:{x}:156,{logo},"
                f"scale=w='trunc(1080*{z}/2)*2':h='trunc(810*{z}/2)*2':eval=frame,"
                f"crop=1080:{PANEL_H}:(iw-1080)*0.5:(ih-{PANEL_H})*0.38,"
                f"eq=brightness='-0.11*(1-{SX})':saturation='1-0.35*(1-{SX})':eval=frame,setsar=1[{out}]")
    fc = ";".join([
        "[0:v]split=2[va][vb]",
        panel("va", a.left, "top", "drawbox=x=620:y=140:w=180:h=115:color=0x0A0B0D:t=fill", St),
        panel("vb", a.right, "bot", "drawbox=x=0:y=140:w=34:h=115:color=0x0A0B0D:t=fill", Sb),
        f"[5:v][top][bot]vstack=inputs=3[stk]",
        f"[stk]drawbox=x=0:y={HDR_H}:w=1080:h={PANEL_H}:color=0xFFC928@0.95:t=8:enable='gt({St},0.5)',"
        f"drawbox=x=0:y={HDR_H + PANEL_H}:w=1080:h={PANEL_H}:color=0xFFC928@0.95:t=8:enable='gt({Sb},0.5)',"
        f"drawbox=x=0:y={HDR_H - 3}:w=1080:h=6:color=0xFFC928:t=fill,drawbox=x=0:y={HDR_H + PANEL_H - 3}:w=1080:h=6:color=0xFFC928:t=fill,"
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
        f"[1:a]volume={a.music}[mus]",
        "[mus][sc]sidechaincompress=threshold=0.012:ratio=12:attack=10:release=500:makeup=1[duck]",
        "[2:a]volume=0.25,asplit=2[w1][w2]",
        f"[w2]adelay={int(D * 1000)}|{int(D * 1000)}[w2d]",
        f"[3:a]volume=0.25,adelay={int((D + 1.7) * 1000)}|{int((D + 1.7) * 1000)}[dd]",
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
    # captions without filler words (um, uh, hmm)
    d_ = json.load(open(words))
    w_ = d_["words"] if isinstance(d_, dict) else d_
    fill = re.compile(r"^(u+m+|u+h+|e+r+m*|hm+|mm+)[,.!?]*$", re.I)
    w_ = [x for x in w_ if not fill.match((x.get("word") or x.get("text") or "").strip())]
    words_clean = cw / "words_clean.json"
    json.dump({"words": w_}, open(words_clean, "w"))
    run([PY, S / "captions_pop.py", "--words", words_clean, "--out", caps, "--res", "1080x1920", "--y", "1800", "--size", str(a.cap_size),
         "--max-chars", str(a.cap_chars), "--max-words", "3", "--keys", a.keys])
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
    ap.add_argument("--team", default="", help="optional extra line on the end banner, e.g. \"Feely Group | eXp Realty\"")
    ap.add_argument("--left", type=int, default=140, help="x of the left speaker's crop (800x600) in the 1920x1080 source")
    ap.add_argument("--right", type=int, default=1120, help="x of the right speaker's crop")
    ap.add_argument("--music", type=float, default=0.0, help="music loudness (0 = no music)")
    ap.add_argument("--focus", type=float, default=0.30, help="zoom on the person speaking (0 = off)")
    ap.add_argument("--fresh", action="store_true", help="ignore saved cuts, captions and music; start the clip over")
    ap.add_argument("--cap-size", type=int, default=88)
    ap.add_argument("--cap-chars", type=int, default=14)
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
