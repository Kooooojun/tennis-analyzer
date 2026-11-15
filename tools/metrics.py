"""Per-stroke body metrics. Two entry points share one definition:
measure_full() on a whole-video pose.npy (33 landmarks), measure_clip() on the 150-frame web clip (KEEP landmarks)."""
import numpy as np
import warnings; warnings.filterwarnings("ignore")
from common import PORTRAIT, FPS
from kind import classify


def _scale(size):
    """Normalized landmarks -> units of 540 px, so thresholds mean the same in portrait (540x960) and landscape (960x540)."""
    return np.array(size or PORTRAIT, float) / 540

SWMAX = 0.5527  # shoulder width / (nose-to-hip) when chest is square to the camera; 100% open


def _angle(xy, f, a, b, c):
    v1 = xy[f, a] - xy[f, b]; v2 = xy[f, c] - xy[f, b]; n = np.linalg.norm(v1) * np.linalg.norm(v2)
    return np.degrees(np.arccos(np.clip(np.dot(v1, v2) / n, -1, 1))) if n > 0 else np.nan


def _med(a):
    a = np.array(a, float); return float(np.nanmedian(a)) if np.isfinite(a).any() else None


KNEE_GAP_MAX = 20.0  # deg; |knee3d - knee| above this = "angle unreliable for this stroke" (checked against multi-view ground truth: docs/research/multiview-angles.md)
KNEE_VIEW_MIN = 30.0  # deg; camera within this of straight in front / behind = knee angle not shown or scored (CalTennis: 2D median error 19.6 deg front, 34.4 back vs ~2 side; testset/results/eval-caltennis.md)


def cam_az(world, J, frames):
    """Camera azimuth around the player, deg 0-180 (0 = in front of the chest, 90 = side, 180 = behind; same as the CalTennis ct_eval.az).
    MediaPipe world is camera-aligned (x right, y down, z away), so the camera is at -z. Body right = shoulder + hip lines, median over `frames`.
    None when the window has no data or the body line is nearly vertical. A left/right label swap turns az into 180 - az; the gate covers both ends."""
    W = np.asarray(world[[i for i in frames if 0 <= i < len(world)]], float)  # slice first: `world` can be a whole video, do not convert all of it
    if not len(W): return None
    r = np.nanmedian(W[:, J['rs']] - W[:, J['ls']] + W[:, J['rh']] - W[:, J['lh']], axis=0)
    fx, fz = -r[2], r[0]  # forward = up x right, up = -y
    n = np.hypot(fx, fz)
    if not np.isfinite(n) or n < 0.05: return None
    return float(np.degrees(np.arccos(np.clip(-fz / n, -1, 1))))


def _front_back(az):
    """True when the camera is within KNEE_VIEW_MIN of straight in front / behind (az from cam_az, None = unknown -> False)."""
    return az is not None and min(az, 180 - az) < KNEE_VIEW_MIN


def _knee(xy, J, c):
    ks = [min(_angle(xy, i, J['rh'], J['rk'], J['ra']), _angle(xy, i, J['lh'], J['lk'], J['la'])) for i in range(c - 48, c - 5)]
    return float(np.nanpercentile(ks, 10))


PREP_WIN = FPS  # frames (1.0 s) searched before contact; a fixed 1.4 s window caught the previous rally stroke (testset/results/prep-contact.md)
PREV_GAP = 3  # frames after the previous hit that still belong to it (contact frames are +-2 frames)
PREP_MAX = 90  # frames (1.5 s, the web clip before contact): how far a backswing end on the window's first frame is followed back


def _swing_dir(xy, J, c):
    """+1 / -1: image-x direction of the forward swing (hitting wrist, 0.33 s before contact -> contact). Medians, not the
    last few frames: the wrist already wraps back in the follow-through when the contact frame is a few frames late."""
    if c < 20: return np.nan  # window would start before the video and wrap to its end
    d = np.nanmedian(xy[c - 2:c + 1, J['rw'], 0]) - np.nanmedian(xy[c - 20:c - 13, J['rw'], 0])
    return float(np.sign(d)) if np.isfinite(d) and d != 0 else np.nan


def _swing_vec(W, J, c):
    """Unit (x, 0, z) world direction of the forward swing (wrist relative to the hip centre, same windows as _swing_dir), for a camera
    straight in front / behind where the swing runs along depth and image x has no stable sign. None without data."""
    if c < 20: return None
    rel = W[:, J['rw']] - (W[:, J['lh']] + W[:, J['rh']]) / 2
    v = np.nanmedian(rel[c - 2:c + 1], axis=0) - np.nanmedian(rel[c - 20:c - 13], axis=0); v[1] = 0
    n = np.linalg.norm(v); return v / n if np.isfinite(n) and n > 0 else None


def _rmed(a, h):
    """Rolling median over +-h samples (edges shrink); NaN where the whole window is NaN."""
    return np.array([np.nanmedian(a[max(0, i - h):i + h + 1]) if np.isfinite(a[max(0, i - h):i + h + 1]).any() else np.nan for i in range(len(a))])


def _prep(P, J, c, u, prev=None):
    """(seconds from backswing end to contact, truncated) or None. Backswing end = the frame where the hitting wrist is furthest back
    relative to the hip centre along the swing direction u (+1/-1 on image x, or a _swing_vec on world coordinates; 5-frame median against jitter).
    prev: frame of the same player's previous hit in this array, if any; nothing at or before prev + PREV_GAP is searched.
    truncated = the wrist is still furthest back at the search limit (c - PREP_MAX or the clip start), so the time is a lower bound."""
    if c < 6: return None  # no frames before c-3
    o = max(0, c - PREP_MAX - 2)  # smooth only the frames used (+2 margin for the median): P can be a whole video, and _rmed is a per-frame python loop
    rel = P[o:c, J['rw']] - (P[o:c, J['lh']] + P[o:c, J['rh']]) / 2
    back = np.full(len(P), np.nan); back[o:c] = _rmed(rel[:, 0] * u if np.isscalar(u) else rel @ u, 2)
    lim = max(0, c - PREP_MAX); lo = lim if prev is None else max(lim, prev + PREV_GAP)
    a = max(lo, c - PREP_WIN); sm = back[a:c - 3]
    if not len(sm) or not np.isfinite(sm).any(): return None
    i = a + int(np.nanargmin(sm))
    # minimum on the window's first frame: the wrist was back earlier. Follow it back while the wrist stays within tol (5% of the range; 2% stopped on pose noise) of the
    # furthest-back point so far (not of the current frame: slow drift must not chain); the best of the next 3 earlier frames counts, so one
    # noise spike does not end the walk. A previous stroke first swings forward, which stops it; prev stops it at the previous hit
    tol = 0.05 * (np.nanmax(sm) - np.nanmin(sm))
    if back[a] <= back[i] + 0.4 * tol:  # the window starts on the backswing plateau (noise can put the minimum a few frames later); 2% of the range: 5% moved 1 in 10 normal strokes
        m = back[i]; e = a
        while a > lo and np.nanmin(np.r_[back[max(lo, a - 3):a], np.inf]) <= m + tol: a -= 1; m = np.fmin(m, back[a])
        k = np.flatnonzero(back[a:e + 1] <= m + tol)
        if len(k): i = a + int(k[0])  # first frame at the furthest-back level
    return round((c - i) / FPS, 3), bool(i == a and lo == lim and (a == lim or not np.isfinite(back[a - 1])))


# --- view-robust body kinematics (docs/scoring.md §11). Idea from Logan-Huang/Tennis-AI-Coach (no licence: rewritten, nothing copied).
TURN_REV = 0.15     # shoulder-width reversal (fraction of full width) needed to count a change of turning direction
FULL_SW_MIN = 0.55  # full shoulder width is at least this many torso lengths
LIMB_FULL = 0.8     # 2D knee only where thigh and shin both show >= 80% of their longest length in the clip


def _smooth(a, k=2):
    """Centred 5-frame nan-median along axis 0, against single-frame pose glitches."""
    return np.array([np.nanmedian(a[max(0, i - k):i + k + 1], axis=0) for i in range(len(a))])


def _zigzag(w, thr):
    """Turning points of w that reverse by more than thr, plus the first value and the last extreme."""
    piv = [w[0]]; hi = lo = w[0]; d = 0
    for v in w[1:]:
        if d >= 0 and v > hi: hi = v
        if d <= 0 and v < lo: lo = v
        if d >= 0 and hi - v > thr and hi > piv[-1]: piv.append(hi); d = -1; lo = v
        elif d <= 0 and v - lo > thr and lo < piv[-1]: piv.append(lo); d = 1; hi = v
    piv.append(hi if d > 0 else lo if d < 0 else (hi if hi - w[0] > w[0] - lo else lo))
    return piv


def kinematics(xy, J, c, hand="R", start=None):
    """Leg load/drive, wrist speed, trunk share, shoulder turn and the 2D-knee foreshortening gate for the stroke at frame c.
    xy: (frames, n, 2) in 540-px units, y down. hand: racket hand "R"/"L" (J is remapped by _hand; pass "R" for an already remapped J). start: backswing-end frame for the turn (default c-30)."""
    a, b = max(0, c - 90), min(len(xy), c + 61)  # the 150-frame web clip
    J = _hand(J, hand); s, w = J['rs'], J['rw']
    X = _smooth(xy[a:b]); c0 = c - a
    hip = (X[:, J['lh']] + X[:, J['rh']]) / 2
    L = np.nanmedian(np.linalg.norm((X[:, J['ls']] + X[:, J['rs']]) / 2 - hip, axis=1))
    out = dict(leg_load=None, leg_drive=None, wrist_speed=None, trunk_share=None, turn=None, knee2d_ok=None)
    if not np.isfinite(L) or L <= 0 or c0 < 48: return out  # c0 < 48: stroke in the first 0.8 s, the windows would wrap to the clip end
    # legs: hip height above the lower (grounded) ankle, as a share of the standing height in the clip
    with np.errstate(all="ignore"):
        h = np.nanmax(X[:, [J['la'], J['ra']], 1], axis=1) - hip[:, 1]
    if np.isfinite(h[c0 - 48:c0 + 1]).any() and np.isfinite(h[c0 - 2:c0 + 3]).any():
        stand = np.nanmax(h); low = np.nanmin(h[c0 - 48:c0 + 1])
        # no "equivalent knee angle": on wall-1 the drop did not follow knee3d (wide stances lower the hip too), docs/research/body-kinematics.md
        out.update(leg_load=round(float((stand - low) / stand), 3), leg_drive=round(float((np.nanmedian(h[c0 - 2:c0 + 3]) - low) / stand), 3))
    # speeds of the racket wrist and shoulder relative to the hip centre, torso lengths / s, peak in the forward swing (0.25 s before contact
    # to contact). Raw frames, then a median on the speed (a one-frame glitch makes two spikes, both dropped); the 0.4 s window first
    # tried caught 3-4 frame wrist glitches in the backswing on wall-1 (62-98 torso/s)
    R = xy[a:b]; rhip = (R[:, J['lh']] + R[:, J['rh']]) / 2; p0 = max(0, c0 - 25)
    sp = lambda j: _smooth(np.linalg.norm(np.diff(R[p0:c0 + 8, j] - rhip[p0:c0 + 8], axis=0), axis=1))[c0 - 15 - p0:c0 + 3 - p0] * FPS / L
    vw, vs = sp(w), sp(s)
    if np.isfinite(vw).any():
        pw = float(np.nanmax(vw)); out["wrist_speed"] = round(pw, 2)
        if pw >= 1 and np.isfinite(vs).any(): out["trunk_share"] = round(float(np.nanmax(vs)) / pw, 3)
    # shoulder turn: angle of the shoulder line to the image plane = arccos(width / full width), path from backswing end to +0.3 s
    sw = np.linalg.norm(X[:, J['rs']] - X[:, J['ls']], axis=1) / L
    if np.isfinite(sw).any():
        full = max(float(np.nanmax(sw)), FULL_SW_MIN)
        st = (c - 30 if start is None else start) - a
        seg = sw[max(0, st):c0 + 19]; seg = seg[np.isfinite(seg)] / full
        if len(seg) >= 5:
            pv = np.clip(_zigzag(seg, TURN_REV), 0, 1); th = np.degrees(np.arccos(pv))
            big = np.abs(np.diff(pv)) > TURN_REV  # a leg smaller than the reversal threshold is jitter, even at the ends (arccos amplifies it near square)
            out["turn"] = round(float(np.abs(np.diff(th))[big].sum()), 1)
    # 2D knee gate: on the leg that gives the smaller angle, thigh and shin both near full length (leg side-on to the camera)
    seglen = lambda p, q: np.linalg.norm(X[:, p] - X[:, q], axis=1)
    legs = [(J['rh'], J['rk'], J['ra']), (J['lh'], J['lk'], J['la'])]
    thigh, shin = [seglen(g[0], g[1]) for g in legs], [seglen(g[1], g[2]) for g in legs]
    full = [(np.nanmax(t) if np.isfinite(t).any() else np.nan, np.nanmax(u) if np.isfinite(u).any() else np.nan) for t, u in zip(thigh, shin)]
    ok = []
    for i in range(max(0, c0 - 48), c0 - 5):  # max(): a negative start would wrap to the end of the clip
        ang = [_angle(X, i, *g) for g in legs]
        if not np.isfinite(ang).any(): continue
        k = int(np.nanargmin(ang))
        ok.append(thigh[k][i] >= LIMB_FULL * full[k][0] and shin[k][i] >= LIMB_FULL * full[k][1])
    if ok: out["knee2d_ok"] = bool(np.mean(ok) >= 0.5)
    return out


def _hand(J, hand):
    """Joint map with the racket arm under rs/re/rw. Left-hander: swap rs<->ls and use le/lw; _core only uses ls/rs as a pair elsewhere."""
    if hand not in ("R", "L"): raise ValueError(f"hand must be 'R' or 'L', got {hand!r}")
    return J if hand == "R" else {**J, "rs": J["ls"], "ls": J["rs"], "re": J["le"], "rw": J["lw"]}


def _core(xy, vis, c, J, world=None, hand="R", prev=None):
    """J maps names to landmark indices for this array layout. world: optional (frames, n, 3) metres, same layout, for knee3d.
    knee = 2D knee (unchanged definition); knee3d = same window/percentile on 3D angles, None without world data.
    hand: racket hand, "R" or "L" (per-player setting, work/profiles.json); everything with the hitting arm follows it."""
    az = cam_az(world, J, range(c - 48, c - 5)) if world is not None and c >= 48 else None  # knee window; before _hand, which swaps ls/rs
    J = _hand(J, hand)
    L = np.linalg.norm((xy[:, J['ls']] + xy[:, J['rs']]) / 2 - (xy[:, J['lh']] + xy[:, J['rh']]) / 2, axis=1)
    bh = np.linalg.norm(xy[:, J['nose']] - (xy[:, J['lh']] + xy[:, J['rh']]) / 2, axis=1)
    openp = np.clip(np.linalg.norm(xy[:, J['rs']] - xy[:, J['ls']], axis=1) / bh / SWMAX * 100, 0, 120)
    # Incomplete windows give None, never a silently shortened or wrapped number (same rule as kinematics' c0 < 48)
    pre = c >= 48; ct = 2 <= c <= len(xy) - 3; w = slice(c - 2, c + 3)
    r = lambda x, n: None if x is None or not np.isfinite(x) else round(float(x), n)
    k3 = _knee(world, J, c) if world is not None and pre else np.nan
    k2 = _knee(xy, J, c) if pre else np.nan
    ok3 = bool(np.isfinite(k3)); ok2 = bool(np.isfinite(k2))
    d = _swing_dir(xy, J, c) if ct else np.nan
    view = _front_back(az)  # front / behind: the swing runs along depth, image x has no stable sign
    if ct:
        hip = (xy[w, J['lh'], 1] + xy[w, J['rh'], 1]) / 2; hx = (xy[w, J['lh'], 0] + xy[w, J['rh'], 0]) / 2
        fwd = None if view else _med(d * (xy[w, J['rw'], 0] - hx) / L[w])
        ch = _med((hip - xy[w, J['rw'], 1]) / L[w]); oc = _med(openp[w]); el = _med([_angle(xy, i, J['rs'], J['re'], J['rw']) for i in range(c - 2, c + 3)])
        vis_c = float(np.nanmean(vis[w, J['rw']])) if np.isfinite(vis[w, J['rw']]).any() else None
    else: fwd = ch = oc = el = vis_c = None
    u = _swing_vec(world, J, c) if view and ct else None
    pr = _prep(world, J, c, u, prev) if u is not None else None if view else _prep(xy, J, c, d, prev) if np.isfinite(d) else None
    prep, trunc = pr or (None, None)
    op = openp[c - 48:c - 5] if pre else np.array([np.nan])
    a = max(0, c - 90); xk = xy[a:c + 61].copy(); xk[vis[a:c + 61] < FORM_VIS_MIN] = np.nan  # same visibility cut as form_checks; only kinematics' 150-frame window, not the whole video
    gap = ok3 and ok2 and abs(k3 - k2) > KNEE_GAP_MAX
    return dict(knee=r(k2, 1) if ok2 else None, knee3d=round(k3, 1) if ok3 else None,
                knee_warn=True if view else bool(gap) if ok3 and ok2 else None,
                knee_warn_why="view" if view else "gap" if gap else None, cam_az=r(az, 1),
                open_min=r(np.nanpercentile(op, 10), 1) if np.isfinite(op).any() else None,
                open_contact=r(oc, 1),
                contact_h=r(ch, 2),
                contact_fwd=r(fwd, 2), prep=prep, prep_trunc=trunc,
                elbow=r(el, 1),
                vis=r(vis_c, 2),
                **kinematics(xk, J, c - a, "R", None if prep is None else c - a - round(prep * FPS)))  # J is already remapped for the racket hand


FULL = dict(nose=0, ls=11, rs=12, le=13, re=14, lw=15, rw=16, lh=23, rh=24, lk=25, rk=26, la=27, ra=28)
CLIP = dict(nose=0, ls=1, rs=2, le=3, re=4, lw=5, rw=6, lh=7, rh=8, lk=9, rk=10, la=11, ra=12)


def measure_full(P, t, size, Wd=None, hand="R", prev_t=None):
    """P: pose.npy (frames,33,3). t: contact time in seconds. size: proxy (w, h). Adds an automatic stroke kind (tools/kind.py): auto_kind FH/BH/SV/OH or '?', with kind_conf 0-1.
    hand "L": kind.classify mirrors its racket-side test. prev_t: the same player's previous hit in this video (s), bounds the prep search."""
    xy = P[:, :, :2] * _scale(size); f = int(round(t * 60)); k = classify(P, f, hand, Wd, size)
    return dict(f=f, auto_kind=k["kind"], kind_conf=k["conf"], **_core(xy, P[:, :, 2], f, FULL, Wd, hand, None if prev_t is None else int(round(prev_t * 60))))


def measure_clip(frames, c, size=None, world=None, hand="R", prev=None):
    nan = [[np.nan] * 3] * 17
    P = np.array([nan if fr is None else fr for fr in frames], float)
    Wd = np.array([nan if w is None else w for w in world], float) if world else None
    return _core(P[:, :, :2] * _scale(size), P[:, :, 2], c, CLIP, Wd, hand, prev)


GUESS_MIN = 30  # sharp wrist-speed samples (0.5 s at 60 fps) needed per wrist before guessing a hand
GUESS_WIN = (24, 12)  # frames before / after a hit that count as "swinging"
GUESS_VIS = 0.9  # a hidden wrist jumps 3x faster than a real swing; only sharp frames count (0.5 picked the wrong hand on the mirrored wall-1 video)


def _swing_mask(n, hit_times):
    """n-frame bool mask of the frames within GUESS_WIN of a hit time (seconds); None = every frame."""
    sel = np.ones(n, bool)
    if hit_times is not None:
        sel[:] = False
        for tt in hit_times: sel[max(0, int(round(tt * FPS)) - GUESS_WIN[0]):int(round(tt * FPS)) + GUESS_WIN[1]] = True
    return sel


def guess_hand(poses, size=None, times=None):
    """Racket hand from the video: the wrist whose image speed (per torso length) has the higher 98th percentile (idea from
    Logan-Huang/Tennis-AI-Coach). poses: pose arrays (frames,33,3) of ONE player; times: per array the hit times in seconds, so only
    swings count (testset/results/player-profile.md: over a whole wall-1 video the percentile picked the wrong hand for a right-hander,
    because a hand-held phone moved close to the legs and the skeleton jumped); None = whole video.
    Returns (hand, ratio), ratio = faster / slower percentile (close to 1 = unsure), or (None, None) with too few visible frames.
    Still a guess: a two-hander's helper hand or a mirrored phone video can fool it."""
    sp = {15: [], 16: []}; sizes = size if isinstance(size, list) else [size] * len(poses)  # one proxy size per pose array
    for i, P in enumerate(poses):
        P = np.asarray(P, float); xy = P[:, :, :2] * _scale(sizes[i]); vis = P[:, :, 2]
        L = np.linalg.norm((xy[:, 11] + xy[:, 12]) / 2 - (xy[:, 23] + xy[:, 24]) / 2, axis=1)[1:]
        sel = _swing_mask(len(P) - 1, times[i] if times is not None else None)
        for w in sp:
            fin = np.isfinite(xy[:, w, 0]); q = np.pad(np.where(fin[:, None], xy[:, w], 0), ((2, 2), (0, 0)), mode="edge")
            m = np.median(np.lib.stride_tricks.sliding_window_view(q, 5, axis=0), axis=2)  # 5-frame median: pose jitter is not a swing
            good = np.convolve(fin & (vis[:, w] >= GUESS_VIS), np.ones(5), "same") == 5  # whole window finite and sharp
            v = np.linalg.norm(np.diff(m, axis=0), axis=1) / np.maximum(L, 1e-3)
            sp[w].append(v[sel & good[1:] & good[:-1] & np.isfinite(v)])  # a NaN torso length would turn the percentile into NaN and silently pick R
    q = {w: np.concatenate(a) for w, a in sp.items()}
    if min(len(a) for a in q.values()) < GUESS_MIN: return None, None
    l, r = (float(np.percentile(q[w], 98)) for w in (15, 16))
    return ("L" if l > r else "R"), round(max(l, r) / max(min(l, r), 1e-9), 2)


GUESS_RATIO = 1.15  # speed ratio below this = cannot tell
GUESS_HI = 0.05     # torso lengths; 95th-percentile wrist height difference below this = cannot tell


def hand_gate(poses, size=None, times=None):
    """guess_hand plus a second cue: the racket wrist goes higher above the shoulder line while swinging (follow-through,
    serve). Speed alone picked the wrong hand with ratios up to 2.28 (one-hand backhand video, THETIS p7/p10), so both cues
    must agree. Returns (hand, ratio, None) or (None, ratio, why) when unsure."""
    g, ratio = guess_hand(poses, size, times)
    if g is None: return None, None, "too little sharp video"
    if ratio < GUESS_RATIO: return None, ratio, f"wrist speed ratio {ratio} < {GUESS_RATIO}"
    sizes = size if isinstance(size, list) else [size] * len(poses); hi = {15: [], 16: []}
    for i, P in enumerate(poses):
        P = np.asarray(P, float); xy = P[:, :, :2] * _scale(sizes[i])
        sh = (xy[:, 11] + xy[:, 12]) / 2; L = np.linalg.norm(sh - (xy[:, 23] + xy[:, 24]) / 2, axis=1)
        sel = _swing_mask(len(P), times[i] if times is not None else None)
        for w in hi:
            h = (sh[:, 1] - xy[:, w, 1]) / np.maximum(L, 1e-3)
            hi[w].append(h[sel & (P[:, w, 2] >= 0.5) & np.isfinite(h)])
    q = {w: np.concatenate(a) for w, a in hi.items()}
    if min(len(a) for a in q.values()) < GUESS_MIN: return None, ratio, "too little visible wrist for the height check"
    d = float(np.percentile(q[16], 95) - np.percentile(q[15], 95))  # > 0: right wrist higher
    if abs(d) < GUESS_HI or ("R" if d > 0 else "L") != g: return None, ratio, f"wrist height says {'R' if d > 0 else 'L'} ({d:+.2f}), speed says {g}"
    return g, ratio, None


# --- arm shape checks (docs/scoring.md §7): pass/fail with a confidence gate, never a degree score ---
ARM_STRAIGHT = 135.0  # deg, mean of 2D and 3D elbow angle (180 = straight): >= this passes. Meta-analysis impact flexion 30 +/- 16 deg; 3D reads ~20 deg more bent than 2D on straight arms, so 135 is loose on purpose
ARM_BENT = 120.0      # deg: mean below this fails; the band between is "cannot tell"
ARM_GAP_MAX = 35.0    # deg; |elbow 3D - elbow 2D| above this = view or tracking is off, say "cannot tell" (straight arms show a 14-31 deg gap, see testset/results/elbow-shape.md; multi-view check: docs/research/multiview-angles.md)
ARM_DEPTH_MAX = 0.75  # |depth| / length of upper arm and forearm; 0.75 = segment 49 deg out of the image plane
ARM_VIS_MIN = 0.5
FRONT_MIN = 0.1       # m; one-hand BH contact: wrist ahead of the leading shoulder along the shoulder line
_ARM = dict(R=(2, 4, 6), L=(1, 3, 5))  # CLIP indices (shoulder, elbow, wrist) per racket hand


def arm_checks(frames, c, size=None, world=None, kind=None, hand="R", one_hand=False):
    """Racket-arm shape at contact on the CLIP layout (frames/world as in measure_clip), window c-2..c+2.
    serve_arm_straight (kind SV) and bh_elbow_ok / bh_front_ok (kind BH with one_hand) are True / False / None (None = cannot tell).
    *_conf = min(wrist-chain visibility, 1 - arm depth fraction, 1 - 2D/3D gap / 70), 0-1. FH, OH and two-handed BH get None."""
    out = dict(serve_arm_straight=None, serve_arm_conf=None, bh_elbow_ok=None, bh_elbow_conf=None, bh_front_ok=None)
    want_elbow = kind == "SV" or (kind == "BH" and one_hand)
    if not want_elbow: return out
    miss = {"serve_arm_conf": 0.0} if kind == "SV" else {"bh_elbow_conf": 0.0}; out_miss = {**out, **miss}  # applies but cannot measure = "cannot tell"
    if world is None: return out_miss
    s, e, w = _ARM.get(hand, _ARM["R"]); sc = _scale(size); e2, e3, vis, dep = [], [], [], []
    for i in range(c - 2, c + 3):
        if i < 0 or i >= len(frames) or frames[i] is None or world[i] is None: continue
        P = np.array(frames[i], float); W = np.array(world[i], float)
        xy = P[:, :2] * sc
        e2.append(_angle(xy[None], 0, s, e, w)); e3.append(_angle(W[None], 0, s, e, w)); vis.append(P[[s, e, w], 2].min())
        dep.append(max(abs(W[b, 2] - W[a, 2]) / (np.linalg.norm(W[b] - W[a]) or np.nan) for a, b in ((s, e), (e, w))))
    if len(e2) < 3 or not (np.isfinite(e2).any() and np.isfinite(e3).any()): return out_miss
    a2, a3, v, d = _med(e2), _med(e3), _med(vis), _med(dep)
    if None in (a2, a3, v, d): return out_miss
    gap = abs(a3 - a2); conf = round(float(max(0, min(v, 1 - d, 1 - gap / 70))), 2)
    ok = v >= ARM_VIS_MIN and d <= ARM_DEPTH_MAX and gap <= ARM_GAP_MAX
    m = (a2 + a3) / 2; verdict = None if not ok else True if m >= ARM_STRAIGHT else False if m < ARM_BENT else None
    if kind == "SV": out.update(serve_arm_straight=verdict, serve_arm_conf=conf)
    else:
        out.update(bh_elbow_ok=verdict, bh_elbow_conf=conf)
        out["bh_front_ok"] = _front(frames, world, c, s, w, hand, ok)
    return out


def _front(frames, world, c, s, w, hand, ok):
    """One-hand BH: is the wrist ahead of the racket-side shoulder along the shoulder line (3D, metres)? None if the shoulders are not both visible/wide enough."""
    if not ok: return None
    ds = []
    for i in range(c - 2, c + 3):
        if i < 0 or i >= len(world) or world[i] is None or frames[i] is None: continue
        W = np.array(world[i], float); P = np.array(frames[i], float)
        u = W[2, [0, 2]] - W[1, [0, 2]]
        if hand == "L": u = -u
        n = np.linalg.norm(u)
        if n < 0.2 or P[[1, 2], 2].min() < ARM_VIS_MIN: continue
        ds.append(float(np.dot(W[w, [0, 2]] - W[s, [0, 2]], u / n)))
    m = _med(ds)
    return None if m is None else bool(m >= FRONT_MIN)


# --- form checks (docs/scoring.md §10): finish / reach / shoulder tilt / torso lean / stance, from the CLIP layout like arm_checks ---
FINISH_WIN = FPS // 2  # frames after contact searched for the follow-through peak (0.5 s)
FORM_VIS_MIN = 0.5
LEAN_MAX = 90.0
TILT_X_MIN = 0.35      # 3D shoulder line: |x| / shoulder width below this = the two shoulders overlap along the camera axis (left/right swap flips the sign); frame dropped
STANCE_MAX = 3.0       # ankle gap / hip gap above this = hip width collapsed by the view (or a bad pose), drop it
_WR = dict(R=6, L=5)   # CLIP index of the racket wrist per hand


def _form_dir(xy, c, wr):
    """+1 / -1 image-x direction of the FH/BH stroke (lean sign), same definition as contact_fwd. The serve has no usable direction (see form_checks)."""
    return _swing_dir(xy, dict(rw=wr), c)


def form_checks(frames, c, size=None, world=None, kind=None, hand="R"):
    """Fields finish (FH/BH), reach and tilt (SV), lean and stance (any kind); None = cannot tell / gate failed. kind None computes all.
    L = shoulder-centre -> hip-centre length at contact; heights are in L, + = above the shoulder centre. Landmarks under FORM_VIS_MIN are ignored."""
    out = dict(finish=None, reach=None, tilt=None, lean=None, stance=None)
    n = len(frames)
    if c < 8 or c >= n: return out
    nan = [[np.nan] * 3] * 17
    P = np.array([nan if fr is None else fr for fr in frames], float)
    xy = P[:, :, :2] * _scale(size); xy[P[:, :, 2] < FORM_VIS_MIN] = np.nan
    W = np.array([nan if w is None else w for w in world], float) if world is not None else None
    az = cam_az(W, dict(ls=1, rs=2, lh=7, rh=8), range(c - 48, c - 5)) if W is not None and c >= 48 else None  # same window and unmasked input as _core's knee gate
    if W is not None: W[P[:, :, 2] < FORM_VIS_MIN] = np.nan
    view = _front_back(az)
    sc = (xy[:, 1] + xy[:, 2]) / 2; hc = (xy[:, 7] + xy[:, 8]) / 2
    L = _med(np.linalg.norm(sc[c - 2:c + 3] - hc[c - 2:c + 3], axis=1))
    wr = _WR.get(hand, 6); hi = np.nanmin(xy[:, 5:7, 1], axis=1)  # higher of the two wrists, per frame
    up = (sc[:, 1] - hi) / L if L else np.full(n, np.nan)
    if kind in (None, "FH", "BH") and c + FINISH_WIN < n:
        seg = up[c:c + FINISH_WIN + 1]
        if np.isfinite(seg).sum() >= FINISH_WIN // 3:
            sm = _rmed(seg, 1)
            out["finish"] = round(float(np.nanmax(sm)), 2)
    if kind in (None, "SV"):
        r = None if view else _med(up[c - 2:c + 3]); out["reach"] = None if r is None else round(r, 2)  # straight behind, the raised arm leans along depth and 2D y reads low
        rs, os_ = (2, 1) if hand != "L" else (1, 2)
        if W is not None and c >= 30:  # 3D only: 2D shoulder tilt swings 45-70 deg on one player's serves (docs/scoring.md §10)
            seg = slice(c - 30, c - 4); dy = W[seg, rs, 1] - W[seg, os_, 1]; ln = np.linalg.norm(W[seg, rs] - W[seg, os_], axis=1)
            ang = np.degrees(np.arcsin(np.clip(dy / ln, -1, 1)))
            ang[np.abs(W[seg, rs, 0] - W[seg, os_, 0]) / ln < TILT_X_MIN] = np.nan
            sm = _rmed(ang, 2); sm[~np.isfinite(ang)] = np.nan  # dropped frames stay out of the peak; peak of the 5-frame median = the moment the racket shoulder is lowest (trophy), not the contact-time lift
            out["tilt"] = round(float(np.nanmax(sm)), 1) if np.isfinite(ang).sum() * 2 >= len(ang) else None
    v = (sc - hc)[c - 2:c + 3]
    if kind == "SV": ln = _med(np.degrees(np.arctan2(np.abs(v[:, 0]), -v[:, 1])))  # serve direction cannot be read from the wrist x (from behind it flips), so size only
    else:
        d = _form_dir(xy, c, wr); ln = _med(np.degrees(np.arctan2(v[:, 0] * d, -v[:, 1]))) if np.isfinite(d) else None
    out["lean"] = None if view or ln is None or abs(ln) > LEAN_MAX else round(ln, 1)  # > 90 deg = head below hips: a mis-tracked frame, not a lean
    A = W if W is not None else xy
    st = _med(np.linalg.norm(A[c - 2:c + 3, 11] - A[c - 2:c + 3, 12], axis=1) / np.linalg.norm(A[c - 2:c + 3, 7] - A[c - 2:c + 3, 8], axis=1))
    out["stance"] = None if st is None or st > STANCE_MAX else round(st, 2)
    return out
