"""Quick self-test: builds a tiny fake video and runs the whole editing chain on it (no client files used).

Usage:  python selftest.py        (takes about 30 seconds; prints READY-style PASS/FAIL)
Does not need internet or the speech model.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / ".claude" / "skills" / "repurpose" / "scripts"))

from captions import build_captions            # noqa: E402
from common import ToolkitError, ffmpeg        # noqa: E402
from export import export_clip                 # noqa: E402
from hook import build_hook                    # noqa: E402
from reframe import reframe                    # noqa: E402
from silence import remove_silence             # noqa: E402


def main() -> int:
    work = ROOT / ".selftest"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    try:
        src = work / "source.mp4"
        subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=1280x720:rate=30:duration=9", "-f", "lavfi", "-i",
                        "aevalsrc='0.3*sin(2*PI*200*t)*lt(mod(t,4),2.5)':s=48000:d=9",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src)], check=True)
        print("1/5 test video made")
        tight = work / "tight.mp4"
        r = remove_silence(src, tight)
        print(f"2/5 silence removal ok ({r['before']:.0f}s -> {r['after']:.0f}s)")
        framed = work / "framed.mp4"
        reframe(tight, framed, "vertical", work / "face.json")
        print("3/5 reframe ok")
        words = [{"word": w, "start": 0.3 + i * 0.4, "end": 0.6 + i * 0.4}
                 for i, w in enumerate("this is a quick test of the caption system working fine".split())]
        cap, _ = build_captions(words, 1080, 1920)
        hook, _ = build_hook("Toolkit self test", 1080, 1920)
        (work / "c.ass").write_text(cap, encoding="utf-8")
        (work / "h.ass").write_text(hook, encoding="utf-8")
        print("4/5 captions and hook text ok")
        outs = export_clip(framed, "selftest", "demo", 1, ["reels"], "vertical", [work / "c.ass", work / "h.ass"],
                           out_dir=work)
        print("5/5 export ok")
    except (ToolkitError, subprocess.CalledProcessError, OSError) as e:
        print(f"SELF-TEST FAILED: {e}")
        return 1
    code = subprocess.run([sys.executable, str(ROOT / "check.py"), *map(str, outs)]).returncode
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(ROOT / "clients" / "selftest", ignore_errors=True)
    print("SELF-TEST PASSED" if code == 0 else "SELF-TEST FAILED (see table above)")
    return code


if __name__ == "__main__":
    sys.exit(main())
