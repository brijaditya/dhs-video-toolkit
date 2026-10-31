"""Step 5: reframe to vertical / square / landscape and keep the speaker's face centred.

Face tracking uses OpenCV (YuNet face detector, Haar fallback). The camera path is smoothed so the
picture glides instead of jumping. If no face is found the crop stays in the centre.

Usage:
  python reframe.py input.mp4 output.mp4 [--format vertical|square|landscape] [--track track.json]
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np

from common import FORMATS, FPS, YUNET_MODEL, fail, ffmpeg, probe, run_main, save_json

DETECT_WIDTH = 640          # detection runs on a small copy of the frame (fast)
DETECT_FPS = 6              # face checks per second
MIN_FACE_COVERAGE = 0.15    # below this share of frames with a face -> centre crop


def _cv2():
    try:
        import cv2
        return cv2
    except ImportError:
        fail("OpenCV is not installed in this Python.", "run setup.ps1 again, or use the toolkit's .venv Python.")


class FaceFinder:
    def __init__(self, cv2, size):
        self.cv2, self.yunet, self.haar = cv2, None, None
        w, h = size
        if YUNET_MODEL.exists() and hasattr(cv2, "FaceDetectorYN"):
            try:
                self.yunet = cv2.FaceDetectorYN.create(str(YUNET_MODEL), "", (w, h), 0.6, 0.3, 50)
            except Exception:
                self.yunet = None
        if self.yunet is None:
            self.haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def faces(self, frame):
        """List of (x, y, w, h, score) in the frame's own pixels."""
        cv2 = self.cv2
        if self.yunet is not None:
            self.yunet.setInputSize((frame.shape[1], frame.shape[0]))
            _, det = self.yunet.detect(frame)
            return [] if det is None else [(r[0], r[1], r[2], r[3], r[14]) for r in det]
        gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        found = self.haar.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
        return [(x, y, w, h, 1.0) for (x, y, w, h) in found]


def detect_track(cv2, path: Path, src_w: int, src_h: int, n_frames: int, fps: float):
    """Return a list of (frame_index, cx, cy, w, h) for the main face, in source pixels."""
    scale = min(1.0, DETECT_WIDTH / src_w)
    dw, dh = int(src_w * scale), int(src_h * scale)
    finder = FaceFinder(cv2, (dw, dh))
    cap = cv2.VideoCapture(str(path))
    step = max(1, round(fps / DETECT_FPS))
    track, prev = [], None
    i = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % step == 0:
            ok, frame = cap.retrieve()
            if ok:
                small = cv2.resize(frame, (dw, dh)) if scale < 1 else frame
                cands = finder.faces(small)
                if cands:
                    def score(c):
                        x, y, w, h, s = c
                        base = w * h * s
                        if prev is not None:   # stick with the face we were already following
                            d = np.hypot(x + w / 2 - prev[0], y + h / 2 - prev[1]) / dw
                            base *= max(0.3, 1.2 - 2 * d)
                        return base
                    x, y, w, h, _ = max(cands, key=score)
                    prev = (x + w / 2, y + h / 2)
                    track.append((i, (x + w / 2) / scale, (y + h / 2) / scale, w / scale, h / scale))
        i += 1
    cap.release()
    return track, i


def smooth_path(frames: np.ndarray, values: np.ndarray, n: int, fps: float, dead: float) -> np.ndarray:
    """Per-frame smooth camera position from sparse face positions."""
    # remove one-off detection jumps
    if len(values) >= 5:
        k = 5
        pad = np.pad(values, (k // 2, k // 2), mode="edge")
        values = np.array([np.median(pad[j:j + k]) for j in range(len(values))])
    raw = np.interp(np.arange(n), frames, values)
    # hold still unless the face moves out of a small dead zone, then glide
    cam = np.empty(n)
    cur = raw[0]
    max_step = dead * 0.25
    for i in range(n):
        d = raw[i] - cur
        if abs(d) > dead:
            cur += np.clip(d - np.sign(d) * dead, -max_step, max_step)
        cam[i] = cur
    sigma = 0.35 * fps
    r = int(sigma * 3)
    kern = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    kern /= kern.sum()
    return np.convolve(np.pad(cam, (r, r), mode="edge"), kern, mode="valid")


def reframe(src: Path, dst: Path, fmt: str = "vertical", track_out: Path | None = None, tracking: bool = True) -> dict:
    cv2 = _cv2()
    W, H = FORMATS[fmt]
    info = probe(src)
    v = info["video"]
    if not v:
        fail("The file has no picture.", "use a real video file.")
    sw, sh = v["width"], v["height"]
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or FPS
    cap.release()
    n_est = max(1, int(round(info["duration"] * fps)))

    target = W / H
    if sw / sh >= target:
        crop_h, crop_w = float(sh), sh * target      # crop the sides
    else:
        crop_w, crop_h = float(sw), sw / target      # crop top/bottom
    crop_w, crop_h = min(crop_w, sw), min(crop_h, sh)

    track, n_frames = ([], n_est)
    if tracking:
        track, n_frames = detect_track(cv2, src, sw, sh, n_est, fps)
    n = max(n_frames, 1)
    coverage = len(track) / max(1, n_frames / max(1, round(fps / DETECT_FPS)))
    face_found = bool(track) and coverage >= MIN_FACE_COVERAGE

    cx_path = np.full(n, sw / 2.0)
    cy_path = np.full(n, sh / 2.0)
    if face_found:
        fr = np.array([t[0] for t in track], float)
        cx_path = smooth_path(fr, np.array([t[1] for t in track]), n, fps, dead=0.04 * crop_w)
        cy_face = smooth_path(fr, np.array([t[2] for t in track]), n, fps, dead=0.04 * crop_h)
        # face sits in the upper-middle of the picture (about 40% down) when we crop top/bottom
        cy_path = cy_face + 0.10 * crop_h
    x0 = np.clip(cx_path - crop_w / 2, 0, sw - crop_w)
    y0 = np.clip(cy_path - crop_h / 2, 0, sh - crop_h)

    scale = W / crop_w
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC

    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
           "-r", f"{fps:.5f}", "-i", "-", "-i", str(src), "-map", "0:v", "-map", "1:a:0?",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(dst)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    cap = cv2.VideoCapture(str(src))
    i = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            j = min(i, n - 1)
            m = np.float32([[scale, 0, -x0[j] * scale], [0, scale, -y0[j] * scale]])
            out = cv2.warpAffine(frame, m, (W, H), flags=interp, borderMode=cv2.BORDER_REPLICATE)
            proc.stdin.write(out.tobytes())
            i += 1
        proc.stdin.close()
    except BrokenPipeError:
        pass
    cap.release()
    err = proc.stderr.read().decode("utf-8", "replace").strip()
    if proc.wait() != 0 or i == 0:
        fail(f"Reframing stopped ({(err.splitlines() or ['no details'])[-1][:140]}).",
             "check the clip plays normally, then try again.")

    # face boxes in OUTPUT pixels (used to keep captions and the hook off the face)
    boxes = []
    if face_found:
        fr = np.array([t[0] for t in track], float)
        fcx = smooth_path(fr, np.array([t[1] for t in track]), n, fps, dead=0.0)
        fcy = smooth_path(fr, np.array([t[2] for t in track]), n, fps, dead=0.0)
        fw = float(np.median([t[3] for t in track]))
        fh = float(np.median([t[4] for t in track]))
        for j in range(0, n, max(1, round(fps / 5))):
            bx = (fcx[j] - fw / 2 - x0[j]) * scale
            by = (fcy[j] - fh / 2 - y0[j]) * scale
            boxes.append([round(j / fps, 2), round(bx), round(by), round(fw * scale), round(fh * scale)])
    result = {"format": fmt, "width": W, "height": H, "frames": i, "face_found": face_found,
              "face_coverage": round(min(coverage, 1.0), 2), "boxes": boxes}
    if track_out:
        save_json(track_out, result)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--format", choices=list(FORMATS), default="vertical")
    ap.add_argument("--track", type=Path, help="where to save the face positions (json)")
    ap.add_argument("--no-track", action="store_true", help="always centre crop")
    a = ap.parse_args()
    r = reframe(a.input, a.output, a.format, a.track, tracking=not a.no_track)
    how = "face tracked" if r["face_found"] else "no face found, centre crop used"
    print(f"Reframed to {r['format']} {r['width']}x{r['height']} ({how}). Saved: {a.output}")


if __name__ == "__main__":
    run_main(main)
