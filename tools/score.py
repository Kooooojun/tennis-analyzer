# score.py <session> — web/sessions/<s>/strokes.json (+ notes.json) -> web/sessions/<s>/scores.json
# One 1–10 score per (player, kind) for FH/BH: form (session median of each metric) and consistency (robust spread).
# Reference values, sources and gates: docs/scoring.md. Changing an anchor changes every session's score, so note it there.
import math
import numpy as np

# field, 10-point end, 1-point end (or band lo, hi, lo_bad, hi_bad), consistency 10/1 ends; no lin/band = consistency only
METRICS = {
    # abs_kinds: kinds that get the absolute score; other kinds get consistency only (the 125 anchor is a forehand front-knee value, docs/scoring.md §2)
    "knee": dict(lin=(125, 160), cons=(5, 20), abs_kinds=("FH",)),
    "contact_h": dict(band=(0.3, 0.8, -0.2, 1.3), cons=(0.08, 0.30)),
    "contact_fwd": dict(cons=(0.10, 0.40)),  # no target: "in front" has no measured optimum and the x projection depends on the camera
    "prep": dict(lin=(0.7, 0.2), cons=(0.05, 0.20)),
    "open_min": dict(lin=(15, 60), cons=(5, 20), abs_kinds=("FH",)),
    # form_checks fields (docs/scoring.md §10): no measured optimum in the literature, so consistency only. Gate = the field is None when landmarks are under vis 0.5
    "finish": dict(cons=(0.15, 0.5), kinds=("FH", "BH")),
    "reach": dict(cons=(0.1, 0.4), kinds=("SV",)),
    "tilt": dict(cons=(3, 12), kinds=("SV",)),
    "lean": dict(cons=(3, 10), kinds=("FH", "BH", "SV")),
    "stance": dict(cons=(0.15, 0.6), kinds=("FH", "BH", "SV")),
    # power (FH/BH): not in form/consistency, only caps the total (docs/scoring.md §11); no cons anchors.
    # turn is not here: a front camera reads 0 deg for real rotation and capped totals by 3.3 (docs/research/body-kinematics.md); strokes.json keeps it for display
    "wrist_speed": dict(lin=(12, 4), power=True),
    "leg_load": dict(lin=(0.15, 0.02), power=True),
}
POWER_MARGIN = 1.2  # total <= power + 1.2: Tennis-AI-Coach's +12 on 0-100, same share of a 10-point scale
BASE_KINDS = ("FH", "BH")  # metrics without `kinds` apply here (knee etc. are not defined for the serve yet)
KINDS = ("FH", "BH", "SV")  # SV group exists only when the session has SV strokes
MIN_N, MIN_N_CONS = 3, 5
MIN_COVER = 0.5  # usable strokes / strokes in the group; below it the metric says 資料不足 (docs/scoring.md §1)
SCORE_VERSION = 9  # 9: lean None for a camera within 30 deg of front/back (a whole front/back session can turn lean into 資料不足), tilt drops frames whose 3D shoulders overlap along the camera axis; old sessions need refine.py re-run for the new values (serve-form-view-gates). 8: prep followed back past 1.0 s when the window start is the minimum; prep_trunc (lower bound) strokes left out of prep; prep along the 3D swing axis for a front / back camera (prep-window-direction). 7: BH knee / open_min consistency only, turn out of the power cap, consistency spread centred per (video, drill) (score-groups-consistency). 6: knee view gate (camera within 30 deg of front/back -> knee_warn) + kinematics get visibility-masked xy (knee-view-gate). 5: power cap (wrist_speed, turn, leg_load) + 2D-knee foreshortening gate (body-kinematics). 4: + finish, reach, tilt, lean, stance and the SV group (serve-finish). 3: + prep, contact_fwd (prep-contact). bump when an anchor, gate or formula changes; trend.py only compares equal versions


def _num(v):
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def lin(v, good, bad):
    """10 at `good`, 1 at `bad`, linear between, clipped. Works either direction."""
    if not _num(v): return None
    t = (v - good) / (bad - good)
    return float(10 - 9 * min(max(t, 0), 1))


def band(v, lo, hi, lo_bad, hi_bad):
    if not _num(v): return None
    return lin(v, lo, lo_bad) if v < lo else lin(v, hi, hi_bad) if v > hi else 10.0


def spread(vals):
    """Robust SD = IQR / 1.349, so one mis-tracked stroke does not blow it up."""
    q1, q3 = np.percentile(vals, [25, 75]); return float((q3 - q1) / 1.349)


def _cons_spread(strokes, m, knee_src="knee"):
    """Robust SD after centring each (video, drill) on its own median, so a camera or drill change between clips is not read as inconsistency.
    Keys with < MIN_N_CONS values are centred on the whole-group median (3 values minus their own median always include a 0, which would shrink the spread).
    One key, or no stroke with a video (old strokes) = plain spread()."""
    pairs = [((str(s.get("video")), s.get("drill")), v) for s in strokes if _num(v := _value(s, m, knee_src))]  # str: 1 and "1" are one video; missing = None
    keys = {k for k, _ in pairs}
    if len(keys) < 2 or all(s.get("video") is None for s in strokes): return spread([v for _, v in pairs])
    whole = float(np.median([v for _, v in pairs]))
    mid = {k: float(np.median(vs)) if len(vs := [v for kk, v in pairs if kk == k]) >= MIN_N_CONS else whole for k in keys}
    return spread([v - mid[k] for k, v in pairs])


def _value(s, m, knee_src="knee"):
    """The stroke's value for metric m, or None when a quality gate drops it (docs/scoring.md §3)."""
    if m == "knee":
        return None if s.get("knee_warn") or (knee_src == "knee" and s.get("knee2d_ok") is False) else s.get(knee_src)
    if m == "prep" and (s.get("prep_trunc") or s.get("prep_trunc") is None and _num(s.get("prep")) and s["prep"] >= 0.999): return None  # old sessions (no prep_trunc): 1.0 s = the old window edge.  lower bound only: its score is 10 either way (>= 1.0 s), but the unknown true value would distort the spread
    if m in ("contact_h", "contact_fwd") and (not _num(s.get("vis")) or s["vis"] < 0.5): return None  # missing or NaN vis fails the gate
    return s.get(m)


def _mean(xs):
    xs = [x for x in xs if x is not None]; return float(np.mean(xs)) if xs else None


def _r(x, d=1): return None if x is None else round(x, d)


def _explain(cfg, n, total, med, sp, ok, kind="FH"):
    """Why the metric got (or did not get) a score: status, formula text and the inputs that fed it."""
    cover = n / total if total else 0
    if kind not in cfg.get("abs_kinds", (kind,)): cfg = {k: v for k, v in cfg.items() if k not in ("lin", "band")}; f = f"{kind} 只評一致性（參考值只有正拍來源）"
    elif "lin" in cfg: g, b = cfg["lin"]; f = f"10 − 9 × clip((中位數 − {g}) / ({b} − {g}), 0, 1)"
    elif "band" in cfg: lo, hi, lb, hb = cfg["band"]; f = f"中位數在 {lo}–{hi} 內 10 分；外側往 {lb} / {hb} 線性降到 1 分"
    else: f = "只評一致性，不評好壞"
    if "cons" in cfg: cg, cb = cfg["cons"]; f += f"；一致性 = 10 − 9 × clip((穩健SD − {cg}) / ({cb} − {cg}), 0, 1)"
    else: f += "；力量分項：不進技術分與一致性，只用來設總分上限"
    return dict(status="ok" if ok else "資料不足", coverage=_r(cover, 2), formula=f,
                inputs=dict(median=_r(med, 2), spread=_r(sp, 2), n=n, n_total=total, anchors=list(cfg.get("lin") or cfg.get("band") or []) or None, cons_anchors=list(cfg["cons"]) if "cons" in cfg else None))


def score_group(strokes, show_open, kind="FH"):
    # one knee source per group: 2D shifts 9-19 deg with view angle, so a 2D/3D mix is not comparable
    ok = [s for s in strokes if not s.get("knee_warn")]
    knee_src = "knee3d" if sum(_num(s.get("knee3d")) for s in ok) > len(ok) / 2 else "knee"
    out = {}
    for m, cfg in METRICS.items():
        if kind not in cfg.get("kinds", BASE_KINDS): continue
        if m == "open_min" and not show_open: continue
        vals = [v for v in (_value(s, m, knee_src) for s in strokes) if _num(v)]
        enough = len(vals) >= MIN_N and len(vals) / len(strokes) >= MIN_COVER
        med = float(np.median(vals)) if enough else None
        sp = _cons_spread(strokes, m, knee_src) if enough and len(vals) >= MIN_N_CONS and "cons" in cfg else None
        sc = None if kind not in cfg.get("abs_kinds", (kind,)) else lin(med, *cfg["lin"]) if "lin" in cfg else band(med, *cfg["band"]) if "band" in cfg else None
        out[m] = dict(median=_r(med, 2), spread=_r(sp, 2), n=len(vals), score=_r(sc), cons=_r(lin(sp, *cfg["cons"])) if "cons" in cfg else None, **_explain(cfg, len(vals), len(strokes), med, sp, enough, kind))
    tech = [x for m, x in out.items() if not METRICS[m].get("power")]
    form = _mean([x["score"] for x in tech]); cons = _mean([x["cons"] for x in tech])
    power = _mean([x["score"] for m, x in out.items() if METRICS[m].get("power")])
    raw = None if form is None else form if cons is None else 0.75 * form + 0.25 * cons
    total = raw if raw is None or power is None else min(raw, power + POWER_MARGIN)  # no power data -> no cap (old sessions keep their scale)
    power_n = sum(any(_num(_value(s, m)) for m, x in out.items() if METRICS[m].get("power") and x["status"] == "ok") for s in strokes)  # cap is per group (docs/scoring.md §11); the web can show how many strokes fed it
    return dict(n=len(strokes), total=_r(total), form=_r(form), consistency=_r(cons), power=_r(power), power_n=power_n if kind in BASE_KINDS else None, uncapped=_r(raw),
                capped=raw is not None and total < raw, metrics=out, knee_src=knee_src, score_version=SCORE_VERSION)


def score_session(strokes, show_open):
    who = lambda s: s.get("player") or "me"  # "player": null counts as "me" too
    keys = sorted({(who(s), s["kind"]) for s in strokes if s["kind"] in KINDS})
    return [dict(player=p, kind=k, **score_group([s for s in strokes if who(s) == p and s["kind"] == k], show_open, k))
            for p, k in keys]


# arm shape checks: (kind, field, conf field that is not None when the check applied, 中文名, 規則文字). Pass/fail counts only; docs/scoring.md §9.
CHECKS = [("SV", "serve_arm_straight", "serve_arm_conf", "發球擊球時手臂接近伸直", "2D、3D 肘角平均 ≥ 135° 通過，< 120° 不通過，其餘與信心閘門不過者為看不出來"),
          ("BH", "bh_elbow_ok", "bh_elbow_conf", "單手反拍擊球時手肘不明顯彎曲", "同上"),
          ("BH", "bh_front_ok", "bh_elbow_conf", "單手反拍擊球點在身體前方", "手腕在持拍側肩膀之前 ≥ 0.1 m（3D，沿肩線）")]
MIN_DECIDED = 3
VERIFIED = {"serve_arm_straight"}  # only check with eye labels behind its passes (THETIS 12/12); no truth yet for bent serves, one-hand BH elbow (1/2) or BH contact-in-front


def check_session(strokes):
    """One row per (player, kind, check) that applied to at least one stroke. Not part of the 1-10 score, so no score_version change."""
    who = lambda s: s.get("player") or "me"; out = []
    for kind, field, conf, name, rule in CHECKS:
        for p in sorted({who(s) for s in strokes if s.get("kind") == kind and _num(s.get(conf))}):
            g = [s for s in strokes if who(s) == p and s.get("kind") == kind and _num(s.get(conf))]
            ps, fl = sum(s.get(field) is True for s in g), sum(s.get(field) is False for s in g); n = len(g)
            out.append(dict(player=p, kind=kind, field=field, name=name, n=n, passed=ps, failed=fl, unclear=n - ps - fl, coverage=_r((ps + fl) / n, 2),
                            status="ok" if ps + fl >= MIN_DECIDED and (ps + fl) / n >= MIN_COVER else "資料不足", formula=rule,
                            verified=field in VERIFIED and fl == 0))  # False verdicts were never checked against truth; the web greys unverified rows
    return out


if __name__ == "__main__":
    from common import session, web, load, save
    s = session(); D = web(s); notes = load(D / "notes.json", {})
    G = score_session(load(D / "strokes.json"), notes.get("showOpen") is True)
    save(D / "scores.json", dict(score_version=SCORE_VERSION, session=s, date=notes.get("date", s), camera=notes.get("camera") or "", show_open=notes.get("showOpen") is True, groups=G, checks=check_session(load(D / "strokes.json"))))
    for g in G:
        ms = "  ".join(f"{m} {x['score']}（中位 {x['median']}，{x['n']} 拍，一致 {x['cons']}）" for m, x in g["metrics"].items())
        print(f"{g['player']} {g['kind']} {g['n']} 拍  總分 {g['total']}  技術 {g['form']}  一致性 {g['consistency']}  | {ms}")
    print("->", D / "scores.json")
