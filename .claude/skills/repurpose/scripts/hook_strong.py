"""Strong hook: big 3-line box for the first 3 seconds, key words in yellow, quick pop-in.

Usage (toolkit Python, from the toolkit folder):
  .venv/bin/python .claude/skills/repurpose/scripts/hook_strong.py --out clip.hook.ass \
      --text "WESTBORO'S HEADLINE|NUMBERS ARE|[[LYING]] TO YOU" [--y 70] [--secs 3]
Lines are separated by |, words inside [[ ]] turn yellow (and bigger on short lines).
--y is the top of the box (1920 high picture). Keep it above/below the face (check a frame!).
Each line should stay under about 19 letters.
"""
import argparse
import re

YELLOW = r"{\c&H0028C9FF&"
WHITE = r"{\c&H00FFFFFF&"


def fmt(t):
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def line_markup(line):
    plain = re.sub(r"\[\[|\]\]", "", line)
    big = 104 if len(plain) <= 14 else 90
    def rep(m):
        return f"{YELLOW}\\fs{big}}}{m.group(1)}{WHITE}\\fs84}}"
    return re.sub(r"\[\[(.+?)\]\]", rep, line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--y", type=int, default=70)
    ap.add_argument("--secs", type=float, default=3.0)
    ap.add_argument("--res", default="1080x1920")
    ap.add_argument("--x", type=int, default=60, help="left edge of the box")
    ap.add_argument("--boxw", type=int, default=960)
    ap.add_argument("--size", type=int, default=84)
    a = ap.parse_args()
    lines = [l.strip().upper() for l in a.text.split("|")]
    body = r"\N".join(line_markup(l) for l in lines)
    h = 330
    PW, PH = [int(v) for v in a.res.lower().split('x')]
    bw = a.boxw
    end = fmt(a.secs)
    doc = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: {PW}
PlayResY: {PH}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Box,Montserrat ExtraBold,60,&H102E2014,&H102E2014,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Bar,Montserrat ExtraBold,60,&H0028C9FF,&H0028C9FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Txt,Montserrat ExtraBold,{a.size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,{end},Box,,0,0,0,,{{\\pos({a.x},{a.y})\\fad(120,250)\\p1}}m 28 0 l {bw-28} 0 b {bw} 0 {bw} 0 {bw} 28 l {bw} {h-28} b {bw} {h} {bw} {h} {bw-28} {h} l 28 {h} b 0 {h} 0 {h} 0 {h-28} l 0 28 b 0 0 0 0 28 0
Dialogue: 1,0:00:00.00,{end},Bar,,0,0,0,,{{\\pos({a.x},{a.y})\\fad(120,250)\\p1}}m 0 0 l 18 0 l 18 {h} l 0 {h}
Dialogue: 2,0:00:00.00,{end},Txt,,0,0,0,,{{\\an5\\pos({a.x + bw // 2},{a.y + h // 2})\\fscx55\\fscy55\\t(0,180,\\fscx112\\fscy112)\\t(180,320,\\fscx100\\fscy100)\\fad(0,250)}}{body}
"""
    open(a.out, "w", encoding="utf-8").write(doc)
    print(f"Strong hook saved: {a.out}")


if __name__ == "__main__":
    main()
