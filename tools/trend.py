# trend.py — every web/sessions/*/scores.json -> history per (player, kind) with flags -> web/sessions/trend.json
# Latest session vs the mean of up to 3 earlier sessions with the same camera and knee source (docs/scoring.md §6).
import re
import math
import numpy as np

WEAK, STRONG, BASE_N = 6, 8, 3
MIN_N = 10  # fewer strokes than this: same-day retest moved the total 1.6, too noisy to compare (docs/scoring.md §6)
NAMES = {"total": "總分", "consistency": "一致性", "knee": "膝蓋", "contact_h": "擊球時手腕高度（2D）", "contact_fwd": "擊球前後", "prep": "準備時間", "open_min": "轉肩", "finish": "收拍", "reach": "擊球伸展", "tilt": "肩膀傾斜", "lean": "軀幹前傾", "stance": "站姿寬度", "wrist_speed": "手速", "turn": "轉肩幅度", "leg_load": "重心降低"}


def _scored(items): return {k for k, v in items.items() if v is not None}  # None = not scored, so it is not part of the set


def compare(history):
    """history: [{"session", "camera", "n", "items": {name: score or None}}], oldest first. Returns flags for the latest session."""
    if not history or history[-1]["n"] < MIN_N or history[-1].get("score_version") is None: return []
    history = [h for h in history if h["n"] >= MIN_N]
    if len(history) < 2: return []
    last = history[-1]; prev = [h for h in history[:-1] if last["camera"] and h["camera"] == last["camera"] and h.get("knee_src") == last.get("knee_src") and h.get("score_version") == last.get("score_version")]
    out = []
    for item, v in last["items"].items():
        # total / consistency average over whichever metrics were scored, so only compare sessions that scored the same set
        # consistency-only metrics (score always None) still feed them, so the set of metrics with a cons must match too (Codex PR #3)
        same = [h for h in prev if item not in ("total", "consistency") or (_scored(h["items"]) == _scored(last["items"]) and set(h.get("cons_set") or []) == set(last.get("cons_set") or []))]
        # Additional composite claims from check_findings carry their own relevant component sets.
        same = [h for h in same if item not in last.get("component_sets", {}) or h.get("component_sets", {}).get(item) == last["component_sets"][item]]
        same = [h for h in same if h["items"].get(item) is not None][-BASE_N:]
        sem = lambda h: ((h.get("uncertainty") or {}).get(item) or {}).get("sem")
        if v is None or not same or any(sem(h) is None or not math.isfinite(sem(h)) or sem(h) < 0 for h in [last, *same]): continue
        base = float(np.mean([h["items"][item] for h in same])); d = v - base
        threshold = 1.96 * math.sqrt(sem(last)**2 + sum(sem(h)**2 for h in same) / len(same)**2)
        flag = "在誤差內" if abs(d) <= threshold or math.isclose(abs(d), threshold, rel_tol=0, abs_tol=1e-12) else "缺點改善" if base < WEAK and d > 0 else "優點退步" if base >= STRONG and d < 0 else "進步" if d > 0 else "退步"
        out.append(dict(item=item, flag=flag, base=round(base, 2), now=v, diff=round(d, 2), threshold=threshold))
    return out


def _items(g):
    return {"total": g["total"], "consistency": g["consistency"], **{m: x["score"] for m, x in g["metrics"].items()}}


def _score_set(g):
    """Same sets as compare(); old scores without form metadata remain unknown to the web."""
    if "form_metrics" not in g: return None
    return [sorted(_scored(_items(g))), sorted(m for m, x in g["metrics"].items() if x["cons"] is not None)]


def _entry(r, g):
    """One history row. Every session is kept; comparable / series_key let the web split or mark lines (same n / camera rules as compare(); the date filter there lives in dated())."""
    cam = r.get("camera") or ""
    return dict(session=r["session"], date=r.get("date"), camera=cam, n=g["n"], knee_src=g.get("knee_src"), score_version=g.get("score_version"), items=_items(g),
                uncertainty={"total": (g.get("uncertainty") or {}).get("total"), "consistency": (g.get("uncertainty") or {}).get("consistency"),
                             **{m: (x.get("uncertainty") or {}).get("score") for m, x in g["metrics"].items()}},
                cons_set=sorted(m for m, x in g["metrics"].items() if x["cons"] is not None),
                form_metrics=g.get("form_metrics"), form_n=g.get("form_n"), score_set=_score_set(g),
                comparable=g["n"] >= MIN_N and bool(cam) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(r.get("date")))), series_key=[cam, g.get("knee_src"), g.get("score_version")])


if __name__ == "__main__":
    from common import ROOT, load, save
    from score import SCORE_VERSION
    S = ROOT / "web" / "sessions"
    runs = sorted((load(p) for p in S.glob("*/scores.json")), key=lambda r: (str(r.get("date", r["session"])), r["session"]))
    H = {}
    for r in runs:
        for g in r["groups"]:
            H.setdefault((g["player"], g["kind"]), []).append(_entry(r, g))
    # only YYYY-MM-DD dates sort correctly as text; undated sessions are listed but never compared
    dated = lambda h: [x for x in h if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(x["date"]))]
    old = sorted({r["session"] for r in runs if r.get("score_version") != SCORE_VERSION})
    if old: print("注意：這些場次的 scores.json 版本不是", SCORE_VERSION, "，只會跟同版本的場次比，請重跑 tools/score.py：", ", ".join(old))
    out = [dict(player=p, kind=k, history=h, flags=compare(dated(h))) for (p, k), h in sorted(H.items())]
    save(S / "trend.json", out)
    for t in out:
        print(f"== {t['player']} {t['kind']}")
        for h in t["history"]: print(f"  {h['session']:<14} {h['camera'][:16]:<16} 總分 {h['items']['total']}  一致性 {h['items']['consistency']}  ({h['n']} 拍)")
        for f in t["flags"]: print(f"  ** {f['flag']}：{NAMES.get(f['item'], f['item'])} {f['base']} -> {f['now']}")
    print("->", S / "trend.json")
