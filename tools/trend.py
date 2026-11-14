# trend.py — every web/sessions/*/scores.json -> history per (player, kind) with flags -> web/sessions/trend.json
# Latest session vs the mean of up to 3 earlier sessions with the same camera and knee source (docs/scoring.md §6).
import re
import numpy as np

WEAK, STRONG, STEP, BASE_N = 6, 8, 1.0, 3
MIN_N = 10  # fewer strokes than this: same-day retest moved the total 1.6, too noisy to compare (docs/scoring.md §6)
NAMES = {"total": "總分", "consistency": "一致性", "knee": "膝蓋", "contact_h": "擊球高度", "contact_fwd": "擊球前後", "prep": "準備時間", "open_min": "轉肩"}


def compare(history):
    """history: [{"session", "camera", "n", "items": {name: score or None}}], oldest first. Returns flags for the latest session."""
    if not history or history[-1]["n"] < MIN_N: return []
    history = [h for h in history if h["n"] >= MIN_N]
    if len(history) < 2: return []
    last = history[-1]; prev = [h for h in history[:-1] if last["camera"] and h["camera"] == last["camera"] and h.get("knee_src") == last.get("knee_src") and h.get("score_version") == last.get("score_version")]
    out = []
    for item, v in last["items"].items():
        # total / consistency average over whichever metrics were scored, so only compare sessions that scored the same set
        same = [h for h in prev if item not in ("total", "consistency") or h["items"].keys() == last["items"].keys()]
        olds = [h["items"].get(item) for h in same][-BASE_N:]; olds = [x for x in olds if x is not None]
        if v is None or not olds: continue
        base = round(float(np.mean(olds)), 2); d = round(v - base, 2)
        if abs(d) < STEP: continue
        flag = "缺點改善" if base < WEAK and d > 0 else "優點退步" if base >= STRONG and d < 0 else "進步" if d > 0 else "退步"
        out.append(dict(item=item, flag=flag, base=base, now=v, diff=d))
    return out


def _items(g):
    return {"total": g["total"], "consistency": g["consistency"], **{m: x["score"] for m, x in g["metrics"].items()}}


if __name__ == "__main__":
    from common import ROOT, load, save
    from score import SCORE_VERSION
    S = ROOT / "web" / "sessions"
    runs = sorted((load(p) for p in S.glob("*/scores.json")), key=lambda r: (str(r.get("date", r["session"])), r["session"]))
    H = {}
    for r in runs:
        for g in r["groups"]:
            H.setdefault((g["player"], g["kind"]), []).append(dict(session=r["session"], date=r.get("date"), camera=r.get("camera") or "", n=g["n"], knee_src=g.get("knee_src"), score_version=g.get("score_version"), items=_items(g)))
    # only YYYY-MM-DD dates sort correctly as text; undated sessions are listed but never compared
    dated = lambda h: [x for x in h if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(x["date"]))]
    old = sorted({r["session"] for r in runs if r.get("score_version") != SCORE_VERSION})
    if old: print("注意：這些場次的 scores.json 版本不是", SCORE_VERSION, "，不會拿來比，請重跑 tools/score.py：", ", ".join(old))
    out = [dict(player=p, kind=k, history=h, flags=compare(dated(h))) for (p, k), h in sorted(H.items())]
    save(S / "trend.json", out)
    for t in out:
        print(f"== {t['player']} {t['kind']}")
        for h in t["history"]: print(f"  {h['session']:<14} {h['camera'][:16]:<16} 總分 {h['items']['total']}  一致性 {h['items']['consistency']}  ({h['n']} 拍)")
        for f in t["flags"]: print(f"  ** {f['flag']}：{NAMES.get(f['item'], f['item'])} {f['base']} -> {f['now']}")
    print("->", S / "trend.json")
