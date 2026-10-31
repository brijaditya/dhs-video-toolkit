"""Step 6: burned-in captions as an ASS subtitle file, made from the word timestamps.

Bold, large, 2-4 words per line, white with a thick black outline, current word highlighted,
placed in the lower-middle of the picture and moved down if needed so it never covers the face.

Usage:
  python captions.py clip.mp4 --client drsmith --format vertical --track track.json --out clip.captions.ass
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import (DEFAULT_FONT, FORMATS, FONTS_DIR, find_brand_fonts, font_family_name, hex_to_ass,
                    load_brief, load_json, luminance, run_main, save_json)

DEFAULT_HIGHLIGHT = "#FFD60A"
WHITE = "#FFFFFF"
BLACK = "#000000"


# ------------------------------------------------------------------ shared ASS helpers
def ass_header(W: int, H: int, styles: list[str]) -> str:
    return ("[Script Info]\nScriptType: v4.00+\nWrapStyle: 2\nScaledBorderAndShadow: yes\n"
            f"PlayResX: {W}\nPlayResY: {H}\nYCbCr Matrix: None\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
            "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
            "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            + "\n".join(styles) + "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, "
            "MarginV, Effect, Text\n")


def ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def ass_escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def base_size(W: int, H: int) -> int:
    return round(min(W, H) * 0.081)       # 88 px on a 1080-wide picture


def resolve_font(client: str | None, wanted: str | None):
    """Return (family, extra fonts folder, needs_bold, note, font file). Falls back to bundled Montserrat."""
    default_file = FONTS_DIR / "Montserrat-ExtraBold.ttf"
    if wanted and "montserrat" in wanted.lower():       # already bundled with the toolkit
        return DEFAULT_FONT, None, False, None, default_file
    if client and wanted:
        folder = find_brand_fonts(client)
        if folder:
            for f in folder.iterdir():
                if f.suffix.lower() in (".ttf", ".otf"):
                    fam = font_family_name(f)
                    if fam and (wanted.lower() in fam.lower() or wanted.lower() in f.stem.lower()):
                        return fam, folder, True, None, f
        return DEFAULT_FONT, None, False, (f"brand font '{wanted}' was not found in clients/{client}/fonts, "
                                          f"so Montserrat was used. Drop the font file there to use it."), default_file
    return DEFAULT_FONT, None, False, None, default_file


def text_width(font_file: Path, size: int, text: str) -> float:
    """Width of a line of text in pixels (Pillow if available, else a close estimate)."""
    try:
        from PIL import ImageFont
        return float(ImageFont.truetype(str(font_file), size).getlength(text))
    except Exception:
        return 0.60 * size * len(text)


# ------------------------------------------------------------------ grouping
def group_words(words: list, max_words: int = 4, max_chars: int = 18) -> list[list]:
    groups, cur = [], []
    for w in words:
        text = w["word"].strip()
        if not text:
            continue
        chars = sum(len(x["word"]) for x in cur) + max(0, len(cur) - 1) + len(text) + (1 if cur else 0)
        gap = w["start"] - cur[-1]["end"] if cur else 0
        if cur and (len(cur) >= max_words or chars > max_chars or gap > 0.45):
            groups.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.!?]$", text) and len(cur) >= 2:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    # avoid one-word orphans: join with the neighbour when it fits
    merged = []
    for g in groups:
        if merged and len(g) == 1 and len(merged[-1]) < max_words and \
                sum(len(x["word"]) + 1 for x in merged[-1]) + len(g[0]["word"]) <= max_chars + 4 and \
                g[0]["start"] - merged[-1][-1]["end"] < 0.45:
            merged[-1].append(g[0])
        else:
            merged.append(g)
    return merged


# ------------------------------------------------------------------ build
def build_captions(words: list, W: int, H: int, brief: dict | None = None, client: str | None = None,
                   face_boxes: list | None = None, highlight: bool = True, uppercase: bool = False,
                   notes: list | None = None) -> tuple[str, Path | None]:
    notes = notes if notes is not None else []
    brief = brief or {}
    colors = brief.get("colors", {})
    fam, fonts_dir, bold, note, _ = resolve_font(client, brief.get("caption_font"))
    if note:
        notes.append(note)

    text_hex = colors.get("caption text", WHITE)
    hl_hex = colors.get("accent") or colors.get("primary") or DEFAULT_HIGHLIGHT
    if luminance(hl_hex) < 0.35:           # too dark to stand out on a dark outline
        hl_hex = DEFAULT_HIGHLIGHT
    outline_hex = BLACK if luminance(text_hex) >= 0.35 else WHITE
    size = base_size(W, H)
    max_chars = max(10, int(0.84 * W / (0.60 * size)))
    outline = round(size * 0.11)

    style = (f"Style: Cap,{fam},{size},{hex_to_ass(text_hex)},{hex_to_ass(hl_hex)},{hex_to_ass(outline_hex)},"
             f"{hex_to_ass(BLACK, 110)},{-1 if bold else 0},0,0,0,100,100,0,0,1,{outline},{round(size * 0.03)},5,40,40,0,1")

    # vertical position: lower-middle, pushed below the face if they would overlap
    cy = {"vertical": 0.70, "square": 0.78, "landscape": 0.80}.get(
        next((k for k, v in FORMATS.items() if v == (W, H)), "vertical"), 0.72) * H
    half = size * 0.75
    if face_boxes:
        face_bottom = max(b[2] + b[4] for b in face_boxes)
        need = face_bottom + 0.03 * H + half
        if need > cy:
            cy = need
        if cy > 0.86 * H:
            cy = 0.86 * H
            notes.append("the face is low in the picture, so captions may sit close to it.")
    cy = round(cy)

    events = []
    groups = group_words(words, 4, max_chars)
    for gi, g in enumerate(groups):
        g_start, g_end = g[0]["start"], g[-1]["end"]
        nxt = groups[gi + 1][0]["start"] if gi + 1 < len(groups) else None
        if nxt is not None and nxt - g_end < 0.3:
            g_end = nxt
        else:
            g_end += 0.08
        def render(active: int | None) -> str:
            parts = []
            for k, w in enumerate(g):
                t = ass_escape(w["word"].upper() if uppercase else w["word"])
                if highlight and active is not None:
                    col = hl_hex if k == active else text_hex
                    parts.append(f"{{\\c{hex_to_ass(col)}}}{t}")
                else:
                    parts.append(t)
            return " ".join(parts)
        pos = f"\\an5\\pos({W // 2},{cy})"
        if highlight and len(g) > 1:
            for k, w in enumerate(g):
                s = w["start"] if k else g_start
                e = g[k + 1]["start"] if k + 1 < len(g) else g_end
                if e - s < 0.04:
                    continue
                pop = "\\fscx92\\fscy92\\t(0,90,\\fscx100\\fscy100)" if k == 0 else ""
                events.append(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},Cap,,0,0,0,,{{{pos}{pop}}}{render(k)}")
        else:
            events.append(f"Dialogue: 0,{ass_time(g_start)},{ass_time(g_end)},Cap,,0,0,0,,"
                          f"{{{pos}\\fscx92\\fscy92\\t(0,90,\\fscx100\\fscy100)}}{render(0 if highlight else None)}")
    return ass_header(W, H, [style]) + "\n".join(events) + "\n", fonts_dir


def main():
    from transcribe import transcribe_file
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path, help="the reframed clip (used to get exact word times)")
    ap.add_argument("--client")
    ap.add_argument("--format", choices=list(FORMATS), default="vertical")
    ap.add_argument("--track", type=Path, help="face positions from reframe.py")
    ap.add_argument("--words", type=Path, help="reuse an existing words json (skips transcribing)")
    ap.add_argument("--model", default="small")
    ap.add_argument("--no-highlight", action="store_true")
    ap.add_argument("--uppercase", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    W, H = FORMATS[a.format]
    words_path = a.words or a.out.with_suffix(".words.json")
    if a.words or words_path.exists():
        words = load_json(words_path)["words"]
    else:
        data = transcribe_file(a.video, a.model)
        save_json(words_path, data)
        words = data["words"]
    boxes = load_json(a.track).get("boxes") if a.track and a.track.exists() else None
    brief = load_brief(a.client) if a.client else {}
    notes: list = []
    ass, _ = build_captions(words, W, H, brief, a.client, boxes, not a.no_highlight, a.uppercase, notes)
    a.out.write_text(ass, encoding="utf-8")
    print(f"Captions saved: {a.out}")
    for n in notes:
        print("NOTE:", n)


if __name__ == "__main__":
    run_main(main)
