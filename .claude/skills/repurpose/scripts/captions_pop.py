"""Alternative caption style: "pop-in" captions (ALL CAPS, each word pops in as it is spoken,
key words turn yellow and grow). Makes an ASS file you pass to export.py with --ass.

Usage (toolkit Python, from the toolkit folder):
  .venv/bin/python .claude/skills/repurpose/scripts/captions_pop.py --words clip/words.json \
      --out clip/captions_pop.ass [--keys "westboro,headline numbers,real story,sold"] [--y 1600]
"""
import argparse
import json
import re

YELLOW = "&H0028C9FF"  # #FFC928 (ASS colours are BGR)
WHITE = "&H00FFFFFF"
MAX_WORDS = 3
MAX_CHUNK_SECS = 1.6
MAX_CHARS = 15  # keeps every line inside the picture, even with the pop-in growth


def fmt(t):
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def load_words(path):
    d = json.load(open(path))
    w = d["words"] if isinstance(d, dict) else d
    out = []
    for x in w:
        t = (x.get("word") or x.get("text") or "").strip()
        if not t:
            continue
        # glue spoken numbers back together: "2" + ".6" -> "2.6", "$700" + ",000" -> "$700,000"
        if out and re.match(r"^[.,]\d", t) and out[-1]["t"][-1:].isdigit():
            out[-1]["t"] += t
            out[-1]["e"] = float(x["end"])
            continue
        out.append({"t": t, "s": float(x["start"]), "e": float(x["end"])})
    return out


def chunks(words):
    cur = []
    for i, w in enumerate(words):
        chars = sum(len(x["t"]) for x in cur) + len(cur) + len(w["t"])
        if cur and (len(cur) >= MAX_WORDS or chars > MAX_CHARS or w["s"] - cur[0]["s"] > MAX_CHUNK_SECS
                    or w["s"] - cur[-1]["e"] > 0.5):
            yield cur
            cur = []
        cur.append(w)
        if re.search(r"[.,!?;:]$", w["t"]):
            yield cur
            cur = []
    if cur:
        yield cur


def key_flags(words, keys):
    flags = [False] * len(words)
    norm = [re.sub(r"[^a-z0-9$']", "", w["t"].lower()) for w in words]
    for k in keys:
        parts = [re.sub(r"[^a-z0-9$']", "", p) for p in k.lower().split()]
        for i in range(len(words) - len(parts) + 1):
            if norm[i:i + len(parts)] == parts:
                for j in range(len(parts)):
                    flags[i + j] = True
    return flags


def main():
    global MAX_CHARS, MAX_WORDS
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--keys", default="", help="comma list of key words/phrases to show in yellow")
    ap.add_argument("--y", type=int, default=1600, help="baseline of the captions (1920 high picture)")
    ap.add_argument("--size", type=int, default=96)
    ap.add_argument("--res", default="1080x1920", help="picture size, e.g. 1920x1080 for landscape")
    ap.add_argument("--max-chars", type=int, default=MAX_CHARS)
    ap.add_argument("--max-words", type=int, default=MAX_WORDS)
    a = ap.parse_args()

    MAX_CHARS, MAX_WORDS = a.max_chars, a.max_words
    PW, PH = [int(v) for v in a.res.lower().split('x')]
    words = load_words(a.words)
    keys = [k.strip() for k in a.keys.split(",") if k.strip()]
    flags = key_flags(words, keys)
    idx = {id(w): i for i, w in enumerate(words)}

    head = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: {PW}
PlayResY: {PH}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,Montserrat ExtraBold,{a.size},{WHITE},{WHITE},&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,8,4,2,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    all_chunks = list(chunks(words))
    for ci, ch in enumerate(all_chunks):
        next_start = all_chunks[ci + 1][0]["s"] if ci + 1 < len(all_chunks) else None
        for k, w in enumerate(ch):
            start = w["s"]
            if k + 1 < len(ch):
                end = ch[k + 1]["s"]
            else:
                end = ch[-1]["e"] + 0.25
                if next_start is not None:
                    end = min(end, next_start)
            if end <= start:
                end = start + 0.2
            parts = []
            for j, v in enumerate(ch):
                txt = v["t"].upper()
                key = flags[idx[id(v)]]
                col = YELLOW if key else WHITE
                if j > k:
                    parts.append(f"{{\\alpha&HFF&}}{txt}")
                elif j == k:
                    big = 122 if key else 112
                    parts.append(
                        f"{{\\alpha&H00&\\c{col}\\fscx70\\fscy70\\t(0,90,\\fscx{big}\\fscy{big})"
                        f"\\t(90,190,\\fscx100\\fscy100)}}{txt}"
                    )
                else:
                    parts.append(f"{{\\alpha&H00&\\c{col}\\fscx100\\fscy100}}{txt}")
            text = " ".join(parts)
            lines.append(f"Dialogue: 2,{fmt(start)},{fmt(end)},Pop,,0,0,0,,{{\\an2\\pos({PW // 2},{a.y})}}{text}")
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(lines) + "\n")
    print(f"Pop-in captions saved: {a.out} ({len(lines)} steps)")


if __name__ == "__main__":
    main()
