"""Step 7: hook text on screen for the first 3 seconds, in a clean style (ASS file).

One tidy rounded box with the hook line, near the top, moved so it never covers the face.

Usage:
  python hook.py --text "You are sleeping wrong" --format vertical --client drsmith --track track.json --out clip.hook.ass
"""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from captions import ass_escape, ass_header, ass_time, base_size, resolve_font, text_width
from common import FORMATS, hex_to_ass, load_brief, load_json, luminance, run_main

HOOK_SECONDS = 3.0
LINE_H = 1.22          # line height as a share of font size
BOTTOM_LIMIT = {"vertical": 0.62, "square": 0.68, "landscape": 0.72}   # keep clear of the captions


def _rounded_box(w: float, h: float, r: float) -> str:
    w, h, r = round(w), round(h), round(r)
    return (f"m {r} 0 l {w - r} 0 b {w} 0 {w} 0 {w} {r} l {w} {h - r} b {w} {h} {w} {h} {w - r} {h} "
            f"l {r} {h} b 0 {h} 0 {h} 0 {h - r} l 0 {r} b 0 0 0 0 {r} 0")


def build_hook(text: str, W: int, H: int, brief: dict | None = None, client: str | None = None,
               face_boxes: list | None = None, duration: float = HOOK_SECONDS, notes: list | None = None):
    notes = notes if notes is not None else []
    brief = brief or {}
    colors = brief.get("colors", {})
    fam, fonts_dir, bold, note, font_file = resolve_font(client, brief.get("hook_font") or brief.get("caption_font"))
    if note:
        notes.append(note)
    box_hex = colors.get("hook background") or colors.get("primary") or "#101820"
    txt_hex = "#FFFFFF" if luminance(box_hex) < 0.55 else "#111111"
    fmt = next((k for k, v in FORMATS.items() if v == (W, H)), "vertical")
    limit = BOTTOM_LIMIT[fmt] * H

    face = [b for b in (face_boxes or []) if b[0] <= duration]
    face_top = min((b[2] - 0.30 * b[4] for b in face), default=None)     # hair sits above the detected box
    face_bottom = max((b[2] + b[4] for b in face), default=None)

    def layout(scale: float):
        size = round(base_size(W, H) * 0.72 * scale)
        per_line = max(12, int(0.84 * W / (0.58 * size)))
        lines = textwrap.wrap(text.strip(), width=per_line)[:3] or [text.strip()]
        pad_x, pad_y = round(size * 0.55), round(size * 0.40)
        box_w = max(text_width(font_file, size, l) for l in lines) + 2 * pad_x
        box_h = len(lines) * size * LINE_H + 2 * pad_y
        return size, lines, pad_x, pad_y, min(box_w, W * 0.94), box_h

    placed = None
    for scale in (1.0, 0.8):
        size, lines, pad_x, pad_y, box_w, box_h = layout(scale)
        top = 0.085 * H
        if face_top is None or top + box_h + 0.02 * H <= face_top:
            placed = (top, scale)
            break
        below = face_bottom + 0.03 * H
        if below + box_h <= limit:
            placed = (below, scale)
            break
    if placed is None:
        placed = (0.085 * H, 1.0)
        notes.append("the hook text is close to the face; check the first 3 seconds by eye.")
    top, scale = placed
    size, lines, pad_x, pad_y, box_w, box_h = layout(scale)
    top = round(top)

    box_style = (f"Style: HookBox,{fam},{size},{hex_to_ass(box_hex, 20)},{hex_to_ass(box_hex)},{hex_to_ass(box_hex)},"
                 f"{hex_to_ass('#000000', 255)},0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1")
    txt_style = (f"Style: Hook,{fam},{size},{hex_to_ass(txt_hex)},{hex_to_ass(txt_hex)},{hex_to_ass('#000000', 255)},"
                 f"{hex_to_ass('#000000', 255)},{-1 if bold else 0},0,0,0,100,100,0,0,1,0,0,8,0,0,0,1")
    x0 = round((W - box_w) / 2)
    end = ass_time(min(duration, HOOK_SECONDS))
    fade = "\\fad(250,300)"
    box_ev = (f"Dialogue: 0,{ass_time(0)},{end},HookBox,,0,0,0,,"
              f"{{\\pos({x0},{top}){fade}\\p1}}{_rounded_box(box_w, box_h, size * 0.35)}{{\\p0}}")
    txt_ev = (f"Dialogue: 1,{ass_time(0)},{end},Hook,,0,0,0,,"
              f"{{\\pos({W // 2},{top + pad_y}){fade}}}" + "\\N".join(ass_escape(l) for l in lines))
    return ass_header(W, H, [box_style, txt_style]) + box_ev + "\n" + txt_ev + "\n", fonts_dir


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--text", required=True)
    ap.add_argument("--format", choices=list(FORMATS), default="vertical")
    ap.add_argument("--client")
    ap.add_argument("--track", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    W, H = FORMATS[a.format]
    boxes = load_json(a.track).get("boxes") if a.track and a.track.exists() else None
    notes: list = []
    ass, _ = build_hook(a.text, W, H, load_brief(a.client) if a.client else {}, a.client, boxes, notes=notes)
    a.out.write_text(ass, encoding="utf-8")
    print(f"Hook text saved: {a.out}")
    for n in notes:
        print("NOTE:", n)


if __name__ == "__main__":
    run_main(main)
