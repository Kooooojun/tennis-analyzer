# hits.py <audio_hp.f32> <audio.f32> <sounds.npy> — hit-sound candidates, rows (t, pk, on, bb).
# t: onset start in s. pk: peak dB. on: dB above the last 0.5 s (median). bb: broadband SNR in dB, the mean over 5 bands
# (100 Hz-8 kHz) of the first 40 ms against the 0.25-0.05 s before; it comes from the unfiltered audio.
# The threshold is low (6 dB) on purpose: on 對牆影片 A a racket hit is only 8-25 dB above the echo, so the old
# 18 dB caught 4%. events.py decides which candidates are hits (hand speed + bb); a ball bouncing on the ground has
# almost no energy below 1 kHz (bb ~2 dB) while a racket hit has (bb ~11 dB), so bb must use the unfiltered audio.
import sys
import numpy as np

SR, HOP = 16000, 80          # 5 ms envelope frames
FR = SR / HOP
THR = 6.0                    # dB above background
BG = 100                     # background = median of the previous 0.5 s
NMS = 0.1                    # s; one candidate per sound
BANDS = [(100, 400), (400, 1000), (1000, 2000), (2000, 4000), (4000, 8000)]
WIN = 640                    # 40 ms


def envelope(a):
    n = len(a) // HOP
    return 20 * np.log10(np.sqrt((a[:n * HOP].reshape(n, HOP).astype(np.float64) ** 2).mean(1)) + 1e-6)


def background(db, step=10):
    """Median of the previous BG frames, computed every `step` frames (memory stays small on 40-minute videos)."""
    pad = np.r_[np.full(BG, np.median(db[:BG]) if len(db) else 0.0), db]
    idx = np.arange(0, len(db), step)
    med = np.array([np.median(pad[i:i + BG]) for i in idx])
    return np.repeat(med, step)[:len(db)]


def candidates(db):
    """[(t_onset_s, dB_above_bg, peak_frame)] — local maxima of db - background over +-NMS, at least THR."""
    on = db - background(db); r = int(NMS * FR); out = []
    for i in np.flatnonzero(on >= THR):
        if on[i] < on[max(0, i - r):i + r + 1].max(): continue
        if out and i - out[-1][2] <= r: continue          # flat top: keep the first frame
        s = i
        while s > 0 and on[s - 1] > THR / 2 and i - s < 10: s -= 1   # walk back to where the rise starts
        out.append((s / FR, float(on[i]), int(i)))
    return out


def band_snr(raw, t):
    n = int(t * SR)
    if n < SR // 4 or n + WIN > len(raw): return np.nan
    f = np.fft.rfftfreq(WIN, 1 / SR); w = np.hanning(WIN)
    x = np.abs(np.fft.rfft(raw[n:n + WIN] * w)) ** 2
    bg = raw[n - SR // 4:n - SR // 20]
    xb = np.mean([np.abs(np.fft.rfft(bg[j:j + WIN] * w)) ** 2 for j in range(0, len(bg) - WIN + 1, WIN // 2)], 0)
    return float(np.mean([10 * np.log10((x[(f >= a) & (f < b)].sum() + 1e-12) / (xb[(f >= a) & (f < b)].sum() + 1e-12)) for a, b in BANDS]))


if __name__ == "__main__":
    if len(sys.argv) != 4: sys.exit("usage: hits.py <audio_hp.f32> <audio.f32> <sounds.npy>")
    hp, raw = np.fromfile(sys.argv[1], np.float32), np.fromfile(sys.argv[2], np.float32)
    db = envelope(hp)
    rows = [(t, float(db[i:i + 6].max()), on, band_snr(raw, t)) for t, on, i in candidates(db)]
    np.save(sys.argv[3], np.array(rows, dtype=np.float64).reshape(-1, 4))
    print(len(rows), "sound candidates")
