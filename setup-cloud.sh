#!/usr/bin/env bash
# DHS toolkit setup for a Linux cloud session (Claude Code on the web). Safe to run again. Ends with READY or a clear error.
# Windows PC: use setup.ps1 instead.
set -u
cd "$(dirname "$0")"
fail() { echo; echo "PROBLEM: $1"; echo "FIX: $2"; exit 1; }
step() { echo; echo "== $1"; }

step "1/5  FFmpeg and system parts"
command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null || {
  (apt-get update -qq && apt-get install -y -qq ffmpeg) >/dev/null 2>&1 || fail "FFmpeg is not installed and could not be added." "ask the owner to allow package downloads in the cloud environment's network settings."
}
# the effects skill (mediapipe) needs these graphics libraries; ignore if already present or not installable
if ! ldconfig -p 2>/dev/null | grep -q libEGL.so.1; then
  (apt-get update -qq && apt-get install -y -qq libegl1 libgles2 libgl1) >/dev/null 2>&1 || echo "  (note: could not add graphics libraries; effects may not run)"
fi
echo "  OK"

step "2/5  Toolkit Python environment"
PY=$(command -v python3.12 || command -v python3.13 || command -v python3) || fail "Python is missing." "use a cloud environment that includes Python 3."
[ -x .venv/bin/python ] || "$PY" -m venv .venv || fail "Could not create the Python environment." "run again; if it repeats, the disk may be full."
.venv/bin/python -m pip install -q --upgrade pip
# headless OpenCV: the normal one needs a screen library that cloud machines do not have
grep -v '^opencv-python$' requirements.txt > .requirements-cloud.txt
echo "opencv-python-headless" >> .requirements-cloud.txt
.venv/bin/python -m pip install -q -r .requirements-cloud.txt || fail "The Python packages did not install." "check the cloud environment allows package downloads (PyPI), then run again."
rm -f .requirements-cloud.txt
.venv/bin/auto-editor --version >/dev/null 2>&1 || fail "auto-editor could not get its engine." "the cloud environment must allow github.com downloads; ask the owner to allow it."
.venv/bin/python -c "import faster_whisper, cv2, numpy, PIL, fontTools" || fail "Some Python packages are broken." "delete the .venv folder and run again."
echo "  OK"

step "3/5  Speech model (about 500 MB, once)"
if .venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')" >/dev/null 2>&1; then
  echo "  OK"
else
  echo "  NOT READY: the speech model could not download (the cloud network blocks huggingface.co)."
  echo "  FIX: owner opens the cloud environment settings (menu in the session title bar > Edit) > Network access,"
  echo "       and adds these Allowed domains: huggingface.co, cdn-lfs.huggingface.co, cas-bridge.xet.hf.co, hf.co"
  NEED_NET=1
fi

step "4/5  Effects skill"
FX=.claude/skills/effects
[ -f $FX/scripts/fx.py ] || fail "The effects skill files are missing." "get the whole toolkit folder again."
[ -x $FX/.venv/bin/python ] || "$PY" -m venv $FX/.venv || fail "Could not create the effects environment." "run again."
$FX/.venv/bin/python -m pip install -q --upgrade pip
$FX/.venv/bin/python -m pip install -q -r $FX/requirements.txt faster-whisper || fail "The effects packages did not install." "check package downloads are allowed, then run again."
$FX/.venv/bin/python -c "import mediapipe, cv2, PIL, numpy" 2>/dev/null || fail "The effects packages are broken." "delete $FX/.venv and run again."
echo "  OK"

step "5/5  Self-test"
.venv/bin/python selftest.py 2>&1 | grep -v -E "WARN|net_impl" || true
.venv/bin/python selftest.py >/dev/null 2>&1 || fail "The self-test failed." "run: .venv/bin/python selftest.py and read the table."

echo
if [ "${NEED_NET:-0}" = "1" ]; then
  echo "READY for everything except listening to speech (see the speech model note above)."
else
  echo "READY - the DHS video toolkit is installed."
fi
