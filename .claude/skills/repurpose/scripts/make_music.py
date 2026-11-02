"""Make original background music and sound effects (no copyrighted material, made from scratch).

Usage (toolkit Python):
  .venv/bin/python .claude/skills/repurpose/scripts/make_music.py --secs 45 --out music.wav [--bpm 92] [--seed 1]
  .venv/bin/python .claude/skills/repurpose/scripts/make_music.py --sfx-dir sfx      (whoosh.wav, ding.wav)
Soft, modern, corporate-friendly bed: warm pad, light pluck, gentle kick and hats.
"""
import argparse
import os
import wave

import numpy as np

SR = 48000
CHORDS = [  # Am - F - C - G, three tones each (Hz)
    (110.00, 130.81, 164.81),
    (87.31, 110.00, 130.81),
    (130.81, 164.81, 196.00),
    (98.00, 123.47, 146.83),
]


def write_wav(path, stereo):
    pk = np.max(np.abs(stereo)) or 1.0
    data = (stereo / pk * 0.89 * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def env_ar(n, a, r):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na > 0:
        e[:na] = np.linspace(0, 1, na)
    if nr > 0:
        e[-nr:] = np.minimum(e[-nr:], np.linspace(1, 0, nr))
    return e


def music(secs, bpm, seed):
    rng = np.random.default_rng(seed)
    n = int(secs * SR)
    beat = 60.0 / bpm
    bar = 4 * beat
    L = np.zeros(n)
    R = np.zeros(n)

    def add(sig, start, gain=1.0, pan=0.0):
        i = int(start * SR)
        if i >= n:
            return
        seg = sig[: n - i]
        L[i:i + len(seg)] += seg * gain * (1 - max(pan, 0))
        R[i:i + len(seg)] += seg * gain * (1 + min(pan, 0))

    nbars = int(secs / bar) + 2
    for b in range(nbars):
        ch = CHORDS[b % 4]
        t0 = b * bar
        # warm pad
        nn = int((bar + 0.6) * SR)
        t = np.arange(nn) / SR
        pad = np.zeros(nn)
        for f in ch:
            for det in (-0.4, 0.4):
                pad += np.sin(2 * np.pi * (f * 2 + det) * t) * 0.5 + np.sin(2 * np.pi * (f * 4 + det) * t) * 0.15
        pad *= env_ar(nn, 0.45, 0.6) * 0.045
        add(pad, t0, 1.0)
        # bass on beats 1 and 3
        for k in (0, 2):
            m = int(beat * 1.8 * SR)
            tt = np.arange(m) / SR
            bs = np.sin(2 * np.pi * ch[0] * tt) * np.exp(-tt * 2.2) * 0.22
            add(bs, t0 + k * beat, 1.0)
        # kick on beats 1 and 3
        for k in (0, 2):
            m = int(0.22 * SR)
            tt = np.arange(m) / SR
            f = 45 + 80 * np.exp(-tt * 28)
            ph = 2 * np.pi * np.cumsum(f) / SR
            kick = np.sin(ph) * np.exp(-tt * 14) * 0.30
            add(kick, t0 + k * beat, 1.0)
        # pluck arpeggio on eighths
        tones = [ch[0] * 4, ch[1] * 4, ch[2] * 4, ch[1] * 4, ch[2] * 4, ch[0] * 8, ch[2] * 4, ch[1] * 4]
        for j, f in enumerate(tones):
            m = int(0.5 * SR)
            tt = np.arange(m) / SR
            pl = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * 2 * f * tt)) * np.exp(-tt * 7.5) * 0.085
            add(pl, t0 + j * beat / 2, 1.0, pan=0.25 if j % 2 else -0.25)
        # soft hats on offbeat eighths
        for j in range(8):
            if j % 2 == 1:
                m = int(0.04 * SR)
                nz = rng.standard_normal(m)
                nz = np.diff(np.concatenate([[0], nz]))
                hat = nz * np.exp(-np.arange(m) / SR * 90) * 0.05
                add(hat, t0 + j * beat / 2, 1.0, pan=0.15)
    # gentle low-pass (moving average) and fades
    k = 3
    kern = np.ones(k) / k
    L = np.convolve(L, kern, mode="same")
    R = np.convolve(R, kern, mode="same")
    fade_in = np.minimum(1, np.arange(n) / (0.6 * SR))
    fade_out = np.minimum(1, (n - np.arange(n)) / (1.4 * SR))
    f = fade_in * fade_out
    return np.stack([L * f, R * f], axis=1)


def whoosh(dur=0.7, seed=3):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    nz = rng.standard_normal(n)
    # sweeping brightness: blend a smoothed and a raw noise
    sm = np.convolve(nz, np.ones(60) / 60, mode="same")
    mix = np.linspace(0, 1, n)
    sig = sm * (1 - mix) * 9 + (nz - sm) * mix * 0.6
    env = np.sin(np.pi * np.minimum(1, t / dur)) ** 2
    sig = sig * env * 0.5
    return np.stack([sig, sig[::-1]], axis=1)


def ding(dur=0.9):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * 1318.5 * t) * 0.6 + np.sin(2 * np.pi * 1975.5 * t) * 0.4) * np.exp(-t * 5.5)
    s += np.sin(2 * np.pi * 2637 * t) * 0.12 * np.exp(-t * 9)
    s *= 0.6
    return np.stack([s, s], axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float)
    ap.add_argument("--out")
    ap.add_argument("--bpm", type=float, default=92)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--sfx-dir")
    a = ap.parse_args()
    if a.sfx_dir:
        os.makedirs(a.sfx_dir, exist_ok=True)
        write_wav(os.path.join(a.sfx_dir, "whoosh.wav"), whoosh())
        write_wav(os.path.join(a.sfx_dir, "ding.wav"), ding())
        print("sound effects saved in", a.sfx_dir)
    if a.secs and a.out:
        write_wav(a.out, music(a.secs, a.bpm, a.seed))
        print("music saved:", a.out)


if __name__ == "__main__":
    main()
