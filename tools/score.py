# score.py <session> — web/sessions/<s>/strokes.json (+ notes.json) -> web/sessions/<s>/scores.json
# One 1–10 score per (player, kind) for FH/BH: form (session median of each metric) and consistency (robust spread).
# Reference values, sources and gates: docs/scoring.md. Changing an anchor changes every session's score, so note it there.
import math
import numpy as np

# field, 10-point end, 1-point end (or band lo, hi, lo_bad, hi_bad), consistency 10/1 ends
METRICS = {
    "knee": dict(lin=(125, 160), cons=(5, 20)),
    "contact_h": dict(band=(0.3, 0.8, -0.2, 1.3), cons=(0.08, 0.30)),
    "open_min": dict(lin=(15, 60), cons=(5, 20)),
}
KINDS = ("FH", "BH")
MIN_N, MIN_N_CONS = 3, 5


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


def _value(s, m):
    """The stroke's value for metric m, or None when a quality gate drops it (docs/scoring.md §3)."""
    if m == "knee":
        if s.get("knee_warn"): return None
        return s["knee3d"] if _num(s.get("knee3d")) else s.get("knee")
    if m == "contact_h" and (not _num(s.get("vis")) or s["vis"] < 0.5): return None  # missing or NaN vis fails the gate
    return s.get(m)


def _mean(xs):
    xs = [x for x in xs if x is not None]; return float(np.mean(xs)) if xs else None


def _r(x, d=1): return None if x is None else round(x, d)


def score_group(strokes, show_open):
    out = {}
    for m, cfg in METRICS.items():
        if m == "open_min" and not show_open: continue
        vals = [v for v in (_value(s, m) for s in strokes) if _num(v)]
        med = float(np.median(vals)) if len(vals) >= MIN_N else None
        sp = spread(vals) if len(vals) >= MIN_N_CONS else None
        sc = lin(med, *cfg["lin"]) if "lin" in cfg else band(med, *cfg["band"])
        out[m] = dict(median=_r(med, 2), spread=_r(sp, 2), n=len(vals), score=_r(sc), cons=_r(lin(sp, *cfg["cons"])))
    form = _mean([x["score"] for x in out.values()]); cons = _mean([x["cons"] for x in out.values()])
    total = None if form is None else form if cons is None else 0.75 * form + 0.25 * cons
    k3 = sum(_num(s.get("knee3d")) for s in strokes)
    return dict(n=len(strokes), total=_r(total), form=_r(form), consistency=_r(cons), metrics=out,
                knee_src="knee3d" if k3 > len(strokes) / 2 else "knee")


def score_session(strokes, show_open):
    who = lambda s: s.get("player") or "me"  # "player": null counts as "me" too
    keys = sorted({(who(s), s["kind"]) for s in strokes if s["kind"] in KINDS})
    return [dict(player=p, kind=k, **score_group([s for s in strokes if who(s) == p and s["kind"] == k], show_open))
            for p, k in keys]


if __name__ == "__main__":
    from common import session, web, load, save
    s = session(); D = web(s); notes = load(D / "notes.json", {})
    G = score_session(load(D / "strokes.json"), notes.get("showOpen") is True)
    save(D / "scores.json", dict(session=s, date=notes.get("date", s), camera=notes.get("camera") or "", show_open=notes.get("showOpen") is True, groups=G))
    for g in G:
        ms = "  ".join(f"{m} {x['score']}（中位 {x['median']}，{x['n']} 拍，一致 {x['cons']}）" for m, x in g["metrics"].items())
        print(f"{g['player']} {g['kind']} {g['n']} 拍  總分 {g['total']}  技術 {g['form']}  一致性 {g['consistency']}  | {ms}")
    print("->", D / "scores.json")
