# ct_sync.py <pose dir> — find the clock shift between the two cameras of a pair (filename start times + timestamps, no SHIFT).
# Score = median distance of 9 joints in the partner camera to the epipolar line of the same joint, every 4th frame;
# coarse search +-20 s in 1/3 s steps, then +-25 frames. ct_tri.SHIFT holds the result (fine-tuned by ct_eval's swing check).
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from ct_tri import proj, interp


def F(Pa, Pb):
    C = np.linalg.svd(Pa)[2][-1]; e = Pb @ C; ex = np.array([[0, -e[2], e[1]], [e[2], 0, -e[0]], [-e[1], e[0], 0]])
    return ex @ Pb @ np.linalg.pinv(Pa)


for a, b in ((1, 3), (2, 4)):
    A, B = np.load(f"{sys.argv[1]}/c{a}.npz"), np.load(f"{sys.argv[1]}/c{b}.npz"); Fm = F(proj(a)[0], proj(b)[0])
    fr = np.arange(1200, len(A["t"]) - 1200, 4); J = [0, 11, 12, 15, 16, 23, 24, 27, 28]

    def score(d):
        ua = A["lm"][fr][:, J, :2].reshape(-1, 2); ub = interp(A["t"][fr] + d / 60, B["t"], B["lm"])[:, J, :2].reshape(-1, 2)
        l = np.c_[ua, np.ones(len(ua))] @ Fm.T
        return float(np.nanmedian(np.abs(np.sum(l * np.c_[ub, np.ones(len(ub))], 1)) / np.hypot(l[:, 0], l[:, 1])))
    d0 = min(range(-1200, 1201, 20), key=score); best = min(range(d0 - 25, d0 + 26), key=score)
    print(f"{a}-{b}: shift 0 -> {score(0):.2f} px; best +{best} frames -> {score(best):.2f} px")
