"""Shared helpers for the DHS repurpose scripts.

Works on Windows, Mac and Linux. Uses pathlib everywhere, no shell tricks.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
# Toolkit root = the folder that holds CLAUDE.md (C:\DHS on the Windows PC).
ROOT = Path(os.environ.get("DHS_ROOT") or SCRIPTS_DIR.parents[3]).resolve()
FONTS_DIR = ROOT / "assets" / "fonts"
YUNET_MODEL = ROOT / "assets" / "models" / "yunet.onnx"
DEFAULT_FONT = "Montserrat ExtraBold"

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm", ".mpg", ".mpeg", ".wmv"}

# name -> (width, height)
FORMATS = {
    "vertical": (1080, 1920),
    "square": (1080, 1080),
    "landscape": (1920, 1080),
}
# platform -> default format
PLATFORMS = {
    "tiktok": "vertical",
    "reels": "vertical",
    "shorts": "vertical",
    "facebook": "vertical",
    "linkedin": "vertical",
    "x": "vertical",
    "youtube": "landscape",
    "square": "square",
    "landscape": "landscape",
}
PLATFORM_ALIASES = {
    "instagram": "reels", "instagram reels": "reels", "ig": "reels", "reel": "reels",
    "youtube shorts": "shorts", "yt shorts": "shorts", "short": "shorts",
    "tik tok": "tiktok", "twitter": "x", "fb": "facebook", "li": "linkedin",
    "yt": "youtube",
}
FPS = 30


class ToolkitError(Exception):
    """An error with a plain-language cause and fix. Printed as a single line."""

    def __init__(self, cause: str, fix: str):
        super().__init__(f"{cause} Fix: {fix}")
        self.cause, self.fix = cause, fix


def fail(cause: str, fix: str):
    raise ToolkitError(cause, fix)


def run_main(main):
    """Run a script's main() and turn errors into one plain line."""
    try:
        code = main()
    except ToolkitError as e:
        print(f"PROBLEM: {e.cause}\nFIX: {e.fix}", file=sys.stderr)
        code = 1
    except KeyboardInterrupt:
        code = 130
    sys.exit(code or 0)


# ---------------------------------------------------------------- tools
def find_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        fail(f"{name} is not installed or not on the PATH.",
             "run setup.ps1 again (Windows) or install FFmpeg, then reopen the window.")
    return path


def ffmpeg() -> str:
    return find_tool("ffmpeg")


def ffprobe() -> str:
    return find_tool("ffprobe")


def run(cmd: list, cwd: Path | None = None, what: str = "FFmpeg", capture: bool = True):
    """Run a command; on failure raise a one-line error with the last useful log line."""
    cmd = [str(c) for c in cmd]
    try:
        proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=capture,
                              text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        fail(f"{cmd[0]} was not found.", "run setup.ps1 again, then reopen the window.")
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        last = tail[-1] if tail else "no details"
        fail(f"{what} stopped with an error ({last[:160]}).",
             "check the input file plays normally, then try again.")
    return proc


def probe(path: Path) -> dict:
    """Return basic facts about a media file using ffprobe."""
    p = run([ffprobe(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
            what="Reading the video")
    data = json.loads(p.stdout or "{}")
    info = {"duration": float(data.get("format", {}).get("duration") or 0.0), "video": None, "audio": None}
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and not info["video"]:
            num, _, den = (s.get("avg_frame_rate") or "0/1").partition("/")
            fps = float(num) / float(den or 1) if float(den or 1) else 0.0
            info["video"] = {"codec": s.get("codec_name"), "width": int(s.get("width", 0)),
                             "height": int(s.get("height", 0)), "fps": fps,
                             "pix_fmt": s.get("pix_fmt"),
                             "rotation": _rotation(s)}
        elif s.get("codec_type") == "audio" and not info["audio"]:
            info["audio"] = {"codec": s.get("codec_name"), "rate": int(s.get("sample_rate") or 0),
                             "channels": int(s.get("channels") or 0)}
    return info


def _rotation(stream: dict) -> int:
    for sd in stream.get("side_data_list", []) or []:
        if "rotation" in sd:
            return int(sd["rotation"]) % 360
    return int((stream.get("tags") or {}).get("rotate", 0)) % 360


def has_audio(path: Path) -> bool:
    return probe(path)["audio"] is not None


# ---------------------------------------------------------------- names / paths
def slug(text: str) -> str:
    """lowercase letters and numbers only (used in file names)."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def normalize_platform(name: str) -> str:
    n = name.strip().lower()
    n = PLATFORM_ALIASES.get(n, n)
    if n not in PLATFORMS:
        fail(f"'{name}' is not a platform I know.",
             "use one of: " + ", ".join(sorted(PLATFORMS)) + ".")
    return n


def client_dirs(client: str) -> dict:
    client = slug(client)
    base = ROOT / "clients" / client
    return {"base": base, "raw": base / "raw", "transcripts": base / "transcripts",
            "clips": base / "clips", "final": base / "final", "brief": base / "brief.md",
            "fonts": base / "fonts"}


def ensure_client(client: str) -> dict:
    d = client_dirs(client)
    for k in ("raw", "transcripts", "clips", "final"):
        d[k].mkdir(parents=True, exist_ok=True)
    return d


def final_name(client: str, topic: str, clip_no: int, platform: str) -> str:
    return f"{slug(client)}_{slug(topic)}_clip{clip_no:02d}_{platform}.mp4"


def fmt_time(sec: float) -> str:
    sec = max(0.0, float(sec))
    m, s = divmod(sec, 60)
    return f"{int(m):02d}:{s:04.1f}"


def parse_time(v) -> float:
    """Accept 83.5, '83.5', '01:23.5' or '1:02:03'."""
    if isinstance(v, (int, float)):
        return float(v)
    parts = str(v).strip().split(":")
    total = 0.0
    for p in parts:
        total = total * 60 + float(p)
    return total


# ---------------------------------------------------------------- brief
def _norm_key(k: str) -> str:
    k = re.sub(r"\(.*?\)", "", k)
    return re.sub(r"[^a-z ]+", "", k.lower()).strip()


def load_brief(client: str) -> dict:
    """Read clients/<name>/brief.md. Returns {} when there is none.

    Understands lines like `- Primary: #1A2B3C` (bullets, bold and indents are fine).
    """
    path = client_dirs(client)["brief"]
    brief = {"_path": str(path)}
    if not path.exists():
        return {}
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8", errors="replace"), flags=re.S)
    fields = {}
    for line in text.splitlines():
        m = re.match(r"^\s*(?:[-*+]\s*)?\**\s*((?:[^:*#()]|\([^)]*\))+?)\s*\**\s*:\s*\**\s*(.*?)\s*$", line)
        if m:
            key, val = _norm_key(m.group(1)), m.group(2).strip().strip("*").strip()
            if key and val and not val.startswith(("<!--", "(")):
                fields.setdefault(key, val)
    brief["fields"] = fields

    def hexes(s):
        return re.findall(r"#[0-9a-fA-F]{6}\b", s or "")

    colors = {}
    for label in ("primary", "secondary", "accent", "caption text", "hook background"):
        h = hexes(fields.get(label, ""))
        if h:
            colors[label] = h[0].upper()
    if not colors:  # fall back to any hex found in the "brand colors" line
        for i, h in enumerate(hexes(fields.get("brand colors", ""))):
            colors[["primary", "secondary", "accent"][min(i, 2)]] = h.upper()
    brief["colors"] = colors
    brief["caption_font"] = fields.get("caption font") or fields.get("fonts") or ""
    brief["hook_font"] = fields.get("hook font") or ""
    brief["platforms"] = [p.strip() for p in re.split(r"[,/;]", fields.get("platforms", "")) if p.strip()]
    brief["caption_notes"] = fields.get("caption", "")
    brief["logo"] = fields.get("logo", "")
    return brief


def find_brand_fonts(client: str) -> Path | None:
    """Folder with the client's own font files (clients/<name>/fonts), if any."""
    d = client_dirs(client)["fonts"]
    return d if d.exists() and any(p.suffix.lower() in (".ttf", ".otf") for p in d.iterdir()) else None


def font_family_name(font_file: Path) -> str | None:
    try:
        from fontTools.ttLib import TTFont
        return TTFont(str(font_file), lazy=True)["name"].getDebugName(1)
    except Exception:
        return None


def hex_to_ass(hex_color: str, alpha: int = 0) -> str:
    """#RRGGBB -> ASS &HAABBGGRR (alpha 0 = solid, 255 = invisible)."""
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# ---------------------------------------------------------------- clips.json
def topic_dir(client: str, topic: str) -> Path:
    return client_dirs(client)["clips"] / slug(topic)


def load_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"{path} does not exist.", "check the name, or run the earlier step first.")
    except json.JSONDecodeError as e:
        fail(f"{path} is not valid JSON ({e.msg} on line {e.lineno}).", "fix the file or create it again.")


def save_json(path: Path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def words_in_range(words: list, start: float, end: float) -> list:
    return [w for w in words if w["end"] > start and w["start"] < end]
