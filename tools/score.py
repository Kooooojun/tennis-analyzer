# score.py <session> — web/sessions/<s>/strokes.json (+ notes.json) -> web/sessions/<s>/scores.json
# One 1–10 score per (player, kind) for FH/BH: form (session median of each metric) and consistency (robust spread).
# Reference values, sources and gates: docs/scoring.md. Changing an anchor changes every session's score, so note it there.
import math
import numpy as np

# field, 10-point end, 1-point end (or band lo, hi, lo_bad, hi_bad), consistency 10/1 ends; no lin/band = consistency only
METRICS = {
    # abs_kinds: kinds that get the absolute score; other kinds get consistency only (the 125 anchor is a forehand front-knee value, docs/scoring.md §2)
    "knee": dict(lin=(125, 160), cons=(5, 20), abs_kinds=("FH",)),
    "contact_h": dict(cons=(0.08, 0.30)),  # 2D wrist height has no validated absolute target
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
BOOTSTRAP_N, BOOTSTRAP_SEED = 1000, 20261116
MIN_N_DRILL = 10  # per drill, usable strokes (after the quality gates) for drill_diff; docs/scoring.md §7.2
DRILL_DIFF = dict(contact_fwd="肩髖長", knee="度", contact_h="肩髖長", prep="秒")  # metric -> unit; only adds a field to scores.json, no anchor / gate / formula change, so SCORE_VERSION stays
VIEW_WARN = 0.3  # 暫定: no source. Share of a group's strokes the view gate drops, from which the next-shoot advice says "film from the side". Margin under 1 - MIN_COVER: at 50% knee is already 資料不足
FPS_MIN = 50  # same as web/index.html fpsLow: below it the page already warns that speed numbers are unverified
SCORE_VERSION = 10  # 10: contact_h consistency only; no absolute wrist-height target. 9: lean None for a camera within 30 deg of front/back (a whole front/back session can turn lean into 資料不足), tilt drops frames whose 3D shoulders overlap along the camera axis; old sessions need refine.py re-run for the new values (serve-form-view-gates). 8: prep followed back past 1.0 s when the window start is the minimum; prep_trunc (lower bound) strokes left out of prep; prep along the 3D swing axis for a front / back camera (prep-window-direction). 7: BH knee / open_min consistency only, turn out of the power cap, consistency spread centred per (video, drill) (score-groups-consistency). 6: knee view gate (camera within 30 deg of front/back -> knee_warn) + kinematics get visibility-masked xy (knee-view-gate). 5: power cap (wrist_speed, turn, leg_load) + 2D-knee foreshortening gate (body-kinematics). 4: + finish, reach, tilt, lean, stance and the SV group (serve-finish). 3: + prep, contact_fwd (prep-contact). bump when an anchor, gate or formula changes; trend.py only compares equal versions


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


def _knee_src(strokes):
    # one knee source per group: 2D shifts 9-19 deg with view angle, so a 2D/3D mix is not comparable
    ok = [s for s in strokes if not s.get("knee_warn")]
    return "knee3d" if sum(_num(s.get("knee3d")) for s in ok) > len(ok) / 2 else "knee"


def score_group(strokes, show_open, kind="FH"):
    knee_src = _knee_src(strokes)
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
    form_metrics = [m for m, x in out.items() if not METRICS[m].get("power") and x["score"] is not None]
    form = _mean([x["score"] for x in tech]); cons = _mean([x["cons"] for x in tech])
    power = _mean([x["score"] for m, x in out.items() if METRICS[m].get("power")])
    raw = None if form is None else form if cons is None else 0.75 * form + 0.25 * cons
    total = raw if raw is None or power is None else min(raw, power + POWER_MARGIN)  # no power data -> no cap (old sessions keep their scale)
    power_n = sum(any(_num(_value(s, m)) for m, x in out.items() if METRICS[m].get("power") and x["status"] == "ok") for s in strokes)  # cap is per group (docs/scoring.md §11); the web can show how many strokes fed it
    return dict(n=len(strokes), total=_r(total), form=_r(form), consistency=_r(cons), power=_r(power), power_n=power_n if kind in BASE_KINDS else None, uncapped=_r(raw),
                capped=raw is not None and total < raw, metrics=out, knee_src=knee_src, score_version=SCORE_VERSION,
                form_metrics=form_metrics, form_n=len(form_metrics))


def bootstrap_group(strokes, show_open, kind="FH"):
    """Within-video resampling through the official scorer, including its quality gates."""
    group = score_group(strokes, show_open, kind)
    clips = {}
    for s in strokes: clips.setdefault(str(s.get("video")), []).append(s)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    samples = [score_group([clip[i] for clip in clips.values() for i in rng.integers(0, len(clip), len(clip))], show_open, kind)
               for _ in range(BOOTSTRAP_N)]

    def interval(value, values):
        if value is None: return None
        valid = [v for v in values if v is not None and math.isfinite(v)]
        # A failed gate is not zero; incomplete draws cannot establish an unconditional interval.
        complete = len(valid) == BOOTSTRAP_N
        return dict(ci=[float(x) for x in np.percentile(valid, [2.5, 97.5])] if complete else None,
                    sem=float(np.std(valid, ddof=1)) if complete else None, valid=len(valid), samples=BOOTSTRAP_N)

    group["uncertainty"] = {k: interval(group[k], [s[k] for s in samples]) for k in ("total", "form", "consistency", "power", "uncapped")}
    for m, metric in group["metrics"].items():
        metric["uncertainty"] = {k: interval(metric[k], [s["metrics"][m][k] for s in samples]) for k in ("score", "cons", "median", "spread")}
    return group


def drill_diff(strokes, kind="FH"):
    """Same player, same kind: median of 自拋 (drill feed) minus median of 對打 (drill rally), per metric, with a within-video bootstrap 95% interval.
    Values pass the same quality gates as the score (_value); each drill needs >= MIN_N_DRILL usable strokes, else diff / ci are None and `reason` says why (docs/scoring.md §7.2)."""
    out = dict(direction="自拋 − 對打（feed − rally）", min_n=MIN_N_DRILL, reason=None, metrics=None)
    if kind not in BASE_KINDS: return dict(out, reason="發球沒有自拋／對打之分")
    knee_src = _knee_src(strokes)
    sides = [[s for s in strokes if s.get("drill") == d] for d in ("feed", "rally")]
    vals = {m: [np.array([v if _num(v := _value(s, m, knee_src)) else np.nan for s in side]) for side in sides] for m in DRILL_DIFF}
    clips = []  # per side: index arrays per video, in order of first appearance, so one input always draws the same way
    for side in sides:
        by = {}
        for i, s in enumerate(side): by.setdefault(str(s.get("video")), []).append(i)
        clips.append([np.array(ix) for ix in by.values()])
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = [[np.concatenate([c[rng.integers(0, len(c), len(c))] for c in side]) if side else np.array([], int) for side in clips] for _ in range(BOOTSTRAP_N)]
    out["metrics"] = {}
    for m, unit in DRILL_DIFF.items():
        sv = [v[~np.isnan(v)] for v in vals[m]]
        e = dict(unit=unit, feed=dict(median=_r(float(np.median(sv[0])), 3) if len(sv[0]) else None, n=len(sv[0])),
                 rally=dict(median=_r(float(np.median(sv[1])), 3) if len(sv[1]) else None, n=len(sv[1])), diff=None, ci=None, sem=None, valid=0, samples=BOOTSTRAP_N, reason=None)
        short = [f"{name}可用 {len(v)} 拍" for name, v in zip(("自拋", "對打"), sv) if len(v) < MIN_N_DRILL]
        if short: e["reason"] = "；".join(short) + f"，要各 ≥ {MIN_N_DRILL} 拍"
        else:
            e["diff"] = _r(float(np.median(sv[0]) - np.median(sv[1])), 3)
            ds = []
            for d in draws:
                a, b = (v[ix] for v, ix in zip(vals[m], d)); a, b = a[~np.isnan(a)], b[~np.isnan(b)]
                ds.append(float(np.median(a) - np.median(b)) if len(a) and len(b) else np.nan)  # a failed gate is not zero
            ds = [x for x in ds if math.isfinite(x)]; e["valid"] = len(ds)
            if len(ds) == BOOTSTRAP_N: e.update(ci=[_r(float(x), 3) for x in np.percentile(ds, [2.5, 97.5])], sem=_r(float(np.std(ds, ddof=1)), 3))
            else: e["reason"] = f"重抽 {BOOTSTRAP_N} 次裡有 {BOOTSTRAP_N - len(ds)} 次某一邊沒有可用的拍，不給區間"
        out["metrics"][m] = e
    return out


def score_session(strokes, show_open, with_uncertainty=False):
    who = lambda s: s.get("player") or "me"  # "player": null counts as "me" too
    keys = sorted({(who(s), s["kind"]) for s in strokes if s["kind"] in KINDS})
    scorer = bootstrap_group if with_uncertainty else score_group
    groups = []
    for p, k in keys:
        rows = [s for s in strokes if who(s) == p and s["kind"] == k]
        groups.append(dict(player=p, kind=k, **scorer(rows, show_open, k), **({"drill_diff": drill_diff(rows, k)} if with_uncertainty else {})))  # drill_diff is a bootstrap too: the plain call stays resample-free
    return groups


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
        applicable = [s for s in strokes if s.get("kind") == kind and (_num(s.get(conf)) or
                      (s.get("contact_untrusted") is True and (kind == "SV" or s.get("backhand") == "one")))]
        for p in sorted({who(s) for s in applicable}):
            g = [s for s in applicable if who(s) == p]
            decided = [s for s in g if s.get("contact_untrusted") is not True]
            ps, fl = sum(s.get(field) is True for s in decided), sum(s.get(field) is False for s in decided); n = len(g)
            ok = ps + fl >= MIN_DECIDED and (ps + fl) / n >= MIN_COVER
            out.append(dict(player=p, kind=kind, field=field, name=name, n=n, passed=ps, failed=fl, unclear=n - ps - fl, coverage=_r((ps + fl) / n, 2),
                            status="ok" if ok else "資料不足", formula=rule,
                            verified=field in VERIFIED and ok and ps > 0 and fl == 0))  # needs status ok and >= 1 pass; False verdicts were never checked against truth. The web does not read this yet (greys every row)
    return out


def shoot_basis(strokes, groups, fps, show_open):
    """Inputs of the 「下次拍攝建議」 (SKILL.md) and which of them fire: (lines to print, triggers [(type, advice, "player kind")]).
    view: share of a group's strokes whose cam_az is within KNEE_VIEW_MIN of front / behind (metrics._front_back, the gate itself), >= VIEW_WARN.
    Not knee_warn_why == "view": refine.py rewrites a stroke it distrusts to "contact" and clears its cam_az, so that stroke's view is unknown, left out of the denominator and printed.
    cover / count: a 資料不足 metric is either gated (usable / group strokes < MIN_COVER: more strokes of the same kind do not fix the gate) or just short (>= MIN_COVER but usable < MIN_N).
    fps: source fps < FPS_MIN. showOpen has no trigger of its own (camera height is not measured); an open_min 資料不足 shows up as cover / count."""
    from metrics import _front_back
    lines, trig = [], []
    for g in groups:
        who = f"{g['player']} {g['kind']}"
        gs = [x for x in strokes if (x.get("player") or "me") == g["player"] and x["kind"] == g["kind"]]
        known = [x for x in gs if x.get("cam_az") is not None]
        view = sum(_front_back(x["cam_az"]) for x in known)
        why = {w: sum(x.get("knee_warn_why") == w for x in gs) for w in ("view", "gap", "contact")}
        lines.append(f"拍攝依據 {who}：視角擋掉 {view}/{len(known)} 拍（{view / max(len(known), 1):.0%}，門檻 {VIEW_WARN:.0%} 暫定；方位未知 {len(gs) - len(known)} 拍不算）；knee_warn_why：視角 {why['view']}、gap {why['gap']}、contact {why['contact']}")
        if known and view / len(known) >= VIEW_WARN: trig.append(("view", "側面約 90°、固定、全身入鏡", who))
        short = {"cover": [], "count": []}
        for m, x in g["metrics"].items():
            if x["status"] != "資料不足": continue
            n, tot = x["n"], x["inputs"]["n_total"]
            short["cover" if n / tot < MIN_COVER else "count"].append(m)
            lines.append(f"拍攝依據 {who}：{m} 資料不足，可用 {n}/{tot} 拍（覆蓋率 {n / tot:.0%}，要 ≥ {MIN_COVER:.0%} 且 ≥ {MIN_N} 拍）→ {'被閘門擋掉，多錄不一定有用' if n / tot < MIN_COVER else '拍數不足，多錄有用'}")
        if short["count"]: trig.append(("count", f"多錄 {g['kind']}（{'、'.join(short['count'])} 可用拍數不到 {MIN_N}）", who))
        if short["cover"]: trig.append(("cover", f"{'、'.join(short['cover'])} 被閘門擋掉過半，多錄同樣條件不一定有用；先看是視角、遮擋還是接觸點不可信（原因為推論）", who))
    lines.append(f"拍攝依據：來源 fps {fps if fps else '未知'}（低於 {FPS_MIN} 才建議 60 fps）；showOpen {show_open}")
    if fps and fps < FPS_MIN: trig.append(("fps", "用 60 fps 拍", "來源"))
    lines.append("拍攝建議觸發：" + ("；".join(f"{who}：{a}" for _, a, who in trig) if trig else "無（這場機位可以，照舊）"))
    return lines, trig


if __name__ == "__main__":
    from common import session, web, load, save, src_fps
    s = session(); D = web(s); notes = load(D / "notes.json", {})
    G = score_session(load(D / "strokes.json"), notes.get("showOpen") is True, with_uncertainty=True)
    save(D / "scores.json", dict(score_version=SCORE_VERSION, session=s, date=notes.get("date", s), camera=notes.get("camera") or "", show_open=notes.get("showOpen") is True, groups=G, checks=check_session(load(D / "strokes.json"))))
    for g in G:
        ms = "  ".join(f"{m} {x['score']}（中位 {x['median']}，{x['n']} 拍，一致 {x['cons']}）" for m, x in g["metrics"].items())
        print(f"{g['player']} {g['kind']} {g['n']} 拍  總分 {g['total']}  技術 {g['form']}  一致性 {g['consistency']}  | {ms}")
    strokes = load(D / "strokes.json")
    print("\n".join(shoot_basis(strokes, G, src_fps(s), notes.get("showOpen") is True)[0]))
    print("->", D / "scores.json")
