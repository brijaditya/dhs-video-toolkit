"""Step 1: transcribe a video with word timestamps (faster-whisper).

Usage:
  python transcribe.py --client drsmith --video clients/drsmith/raw/podcast1.mp4
  python transcribe.py --audio-from clip.mp4 --out words.json      (used internally for captions)
"""
from __future__ import annotations

import argparse
from pathlib import Path

from common import ensure_client, fail, fmt_time, probe, run_main, save_json, slug, ROOT


def transcribe_file(media: Path, model_size: str = "small", language: str | None = None) -> dict:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        fail("faster-whisper is not installed in this Python.",
             "run setup.ps1 again, or use the toolkit's .venv Python to run this script.")
    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
    except Exception as e:  # most often: no internet on first run (model download)
        fail(f"Could not load the speech model '{model_size}' ({str(e)[:100]}).",
             "connect to the internet once so the model can download, then try again.")
    segments, info = model.transcribe(str(media), word_timestamps=True, vad_filter=True,
                                      language=language, condition_on_previous_text=False)
    words, segs = [], []
    for seg in segments:
        segs.append({"start": round(seg.start, 2), "end": round(seg.end, 2), "text": seg.text.strip()})
        for w in seg.words or []:
            text = w.word.strip()
            if text:
                words.append({"word": text, "start": round(w.start, 3), "end": round(w.end, 3)})
    return {"language": info.language, "duration": round(info.duration, 2), "words": words, "segments": segs}


def readable_text(data: dict) -> str:
    """A text version with a time stamp on every sentence, easy to read when choosing clips."""
    lines = [f"# Transcript ({data['language']}, {fmt_time(data['duration'])} long)", ""]
    for s in data["segments"]:
        lines.append(f"[{fmt_time(s['start'])} - {fmt_time(s['end'])}] {s['text']}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--client")
    ap.add_argument("--video", type=Path)
    ap.add_argument("--audio-from", type=Path, help="transcribe this file and write --out")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--model", default="small", help="tiny, base, small (default), medium, large-v3")
    ap.add_argument("--language", default=None, help="e.g. en. Default: detect")
    a = ap.parse_args()

    if a.audio_from:
        media, out = a.audio_from, a.out or a.audio_from.with_suffix(".words.json")
    else:
        if not (a.client and a.video):
            ap.error("give --client and --video")
        media = a.video if a.video.is_absolute() else (Path.cwd() / a.video)
        if not media.exists():
            media = ROOT / a.video
        d = ensure_client(a.client)
        out = a.out or d["transcripts"] / f"{slug(media.stem)}.json"
    if not media.exists():
        fail(f"The video {media} was not found.", "check the file name and that it is inside the client's raw folder.")
    if not probe(media)["audio"]:
        fail("This video has no sound track.", "use a video with speech in it.")
    data = transcribe_file(media, a.model, a.language)
    if not data["words"]:
        fail("No speech was found in this video.", "check the sound is on and the language is right (try --language en).")
    save_json(out, data)
    if not a.audio_from:
        out.with_suffix(".txt").write_text(readable_text(data), encoding="utf-8")
    print(f"Transcript saved: {out}  ({len(data['words'])} words, {fmt_time(data['duration'])} long)")


if __name__ == "__main__":
    run_main(main)
