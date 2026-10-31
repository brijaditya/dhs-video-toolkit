"""Download a client's video from a link into clients/<name>/raw/.

Works with direct file links, Dropbox and Google Drive share links ("anyone with the link"), and
YouTube / Vimeo / Loom pages (through yt-dlp). Only use it for videos the client has given us.

Usage:
  python fetch.py --client drsmith --url "https://..." [--name sleep_podcast]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from common import VIDEO_EXTS, ToolkitError, ensure_client, fail, probe, run_main

STREAM_HOSTS = ("youtube.com", "youtu.be", "vimeo.com", "loom.com", "facebook.com", "fb.watch", "wistia.com", "tiktok.com")
UA = {"User-Agent": "Mozilla/5.0 (DHS toolkit)"}


def host_of(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower()


def normalize_url(url: str) -> str:
    """Turn share-page links into direct download links."""
    u = urllib.parse.urlparse(url)
    h = host_of(url)
    if h.endswith("dropbox.com"):
        q = dict(urllib.parse.parse_qsl(u.query))
        q.pop("raw", None)
        q["dl"] = "1"
        return urllib.parse.urlunparse(u._replace(query=urllib.parse.urlencode(q)))
    if h in ("drive.google.com", "docs.google.com"):
        m = re.search(r"/d/([\w-]+)", u.path) or re.search(r"[?&]id=([\w-]+)", url)
        if m:
            return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    return url


def allowed_hint(host: str) -> str:
    return (f"open the cloud environment settings (menu in the session title bar, then Edit), Network access, "
            f"add {host} under Allowed domains, save, and start a new session.")


def open_url(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers=UA)
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        host = host_of(url)
        if e.code in (403, 407):
            fail(f"The cloud network is blocking {host} (or the link is not shared with 'anyone with the link').",
                 allowed_hint(host) + " Also check the link is shared publicly.")
        if e.code == 404:
            fail("That link does not exist any more (error 404).", "check the link and send it again.")
        fail(f"The website answered with error {e.code}.", "check the link opens in a browser, then send it again.")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        host = host_of(url)
        fail(f"Could not reach {host} ({str(getattr(e, 'reason', e))[:80]}).",
             allowed_hint(host) + " If it still fails, check the link.")


def drive_confirm_url(html: str, original: str) -> str | None:
    """Google shows a 'cannot scan for viruses' page for big files; find the real download link."""
    fields = dict(re.findall(r'name="(id|export|confirm|uuid)" value="([^"]*)"', html))
    if fields.get("id") and fields.get("confirm"):
        return "https://drive.usercontent.google.com/download?" + urllib.parse.urlencode(fields)
    m = re.search(r"confirm=([\w-]+)", html)
    return f"{original}&confirm={m.group(1)}" if m else None


def download_direct(url: str, dest_dir: Path, name: str | None) -> Path:
    resp = open_url(url)
    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "text/html" in ctype and host_of(url).endswith("google.com"):
        html = resp.read().decode("utf-8", "replace")
        nxt = drive_confirm_url(html, url)
        if not nxt:
            fail("Google Drive did not give the video (the link is probably private).",
                 "share the file as 'anyone with the link can view' and send the link again.")
        resp = open_url(nxt)
        ctype = (resp.headers.get("Content-Type") or "").lower()
    if "text/html" in ctype:
        fail("That link is a web page, not a video file.",
             "send a direct download link, or a share link set to 'anyone with the link'.")
    cd = resp.headers.get("Content-Disposition") or ""
    fn = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
    base = urllib.parse.unquote(fn.group(1)) if fn else Path(urllib.parse.urlparse(url).path).name
    ext = Path(base).suffix.lower()
    ext = ext if ext in VIDEO_EXTS else ".mp4"
    stem = re.sub(r"[^a-z0-9_]+", "_", (name or Path(base).stem or "video").lower()).strip("_") or "video"
    dest = dest_dir / f"{stem}{ext}"
    n = 2
    while dest.exists():
        dest = dest_dir / f"{stem}_{n}{ext}"
        n += 1
    total = int(resp.headers.get("Content-Length") or 0)
    done, next_mark = 0, 10
    part = dest.with_suffix(dest.suffix + ".part")
    with open(part, "wb") as f:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total and done * 100 // total >= next_mark:
                print(f"  downloaded {done * 100 // total}%", flush=True)
                next_mark += 10
    part.rename(dest)
    return dest


def download_stream(url: str, dest_dir: Path, name: str | None) -> Path:
    stem = re.sub(r"[^a-z0-9_]+", "_", (name or "video").lower()).strip("_") or "video"
    before = set(dest_dir.glob("*"))
    cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist", "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
           "--merge-output-format", "mp4", "-o", str(dest_dir / f"{stem}.%(ext)s"), url]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "").strip().splitlines()
        host = host_of(url)
        fail(f"The video could not be downloaded from {host} ({(err[-1] if err else 'no details')[:120]}).",
             allowed_hint(host) + " If the video is private, ask the client for a file or an 'anyone with the link' share.")
    new = [f for f in dest_dir.glob("*") if f not in before and f.suffix.lower() in VIDEO_EXTS]
    if not new:
        fail("The download finished but no video file appeared.", "send the link again or send the file itself.")
    return max(new, key=lambda f: f.stat().st_mtime)


def fetch(url: str, client: str, name: str | None = None) -> Path:
    raw = ensure_client(client)["raw"]
    host = host_of(url)
    if not url.lower().startswith(("http://", "https://")):
        fail("That does not look like a web link.", "send a link that starts with https://")
    if any(host == h or host.endswith("." + h) for h in STREAM_HOSTS):
        path = download_stream(url, raw, name)
    else:
        path = download_direct(normalize_url(url), raw, name)
    info = probe(path)
    if not info["video"] or not info["audio"]:
        path.unlink(missing_ok=True)
        fail("The downloaded file is not a video with sound.", "check the link, or send the video file itself.")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--client", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--name", help="file name to save as (letters, numbers, underscores)")
    a = ap.parse_args()
    p = fetch(a.url, a.client, a.name)
    info = probe(p)
    mins = info["duration"] / 60
    print(f"Video saved: {p}  ({mins:.1f} minutes, {info['video']['width']}x{info['video']['height']})")


if __name__ == "__main__":
    run_main(main)
