# Who hit it: shared by candidates.py (attribution) and eval_attrib.py (measuring it on a hold-out), so there is one formula.
import numpy as np
from match import match, WRIST
from metrics import hand_gate
from common import FPS


def matched(P, E, wh, hand):
    """match() rows by hit time for the racket wrist; unknown hand: the wrist that swung more (bigger arc) at each hit,
    so a left-hander without a profile does not lose hits (default-R missed 6 of 45 on a left-handed test video)."""
    M = {}
    for h in ([hand] if hand else "RL"):
        for r in match(P, E, wh, h):
            if r[0] not in M or r[4] > M[r[0]][4]: M[r[0]] = r
    return M


def wrist_hands(Ps, prof, E, wh, sz):
    """{track: 'R'|'L'|None}: the profile hand, else guessed from the track's own matched hits (as assemble does), only to pick
    the wrist; None = both wrists."""
    Hd = dict(prof)
    for k in Ps:
        if Hd[k] is None:
            ts = [t for t, _, _, sp, arc in matched(Ps[k], E, wh, None).values() if sp >= 0.05 and arc >= 0.7]
            if ts: Hd[k] = hand_gate([Ps[k]], sz, [ts])[0]
    return Hd


def swing(P, f, wh, wi=16):
    """Wrist path from 0.33 s before a hit sound to 0.07 s after, in torso lengths. The hitter swings into contact;
    the other player's big moves (getting ready for the next ball, walking in) mostly come after it or without a visible wrist."""
    xy = P[:, wi, :2] * wh; xy[P[:, wi, 2] < 0.2] = np.nan
    L = np.linalg.norm((P[f - 30:f + 30, 11, :2] + P[f - 30:f + 30, 12, :2] - P[f - 30:f + 30, 23, :2] - P[f - 30:f + 30, 24, :2]) / 2 * wh, axis=1)
    return np.nansum(np.linalg.norm(np.diff(xy[f - 20:f + 5], axis=0), axis=1)) / np.nanmedian(L) if np.isfinite(L).any() else 0.0


def who_hit(Ps, Hd, t, wh):
    """Track key of Ps whose racket wrist (Hd; None = best of both) swung most into a hit at time t. One person = that one."""
    f = int(round(t * FPS))
    return max(Ps, key=lambda k: max(swing(Ps[k], f, wh, WRIST[h]) for h in ([Hd[k]] if Hd[k] else "RL"))) if len(Ps) > 1 else next(iter(Ps))
