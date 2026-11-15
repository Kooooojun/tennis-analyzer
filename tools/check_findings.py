# check_findings.py <session> — every finding in web/sessions/<s>/notes.json must cite numbers that match strokes.json / scores.json.
# Cite formats and rules: docs/scoring.md §8. Exit 1 and list the failing findings when any check fails.
import math
import re
import numpy as np

STATS = dict(median=np.median, mean=np.mean, min=np.min, max=np.max, n=len)
SCORE_STATS = ("median", "spread", "n", "score", "cons")
GROUP_KEYS = ("total", "form", "consistency", "power", "uncapped")


def _num(v): return isinstance(v, (int, float)) and not isinstance(v, bool) and not math.isnan(v)


def _match(actual, cited, txt=None):
    """Cited value is the actual one rounded to the cite's own decimals (155 accepts 154.5–155.5).
    txt: the number as written in a finding's text, so "0.30" keeps its 2 decimals."""
    if not _num(actual) or not _num(cited): return False
    txt = txt or str(cited)
    d = len(txt.split(".")[1]) if "." in txt else 0
    return abs(actual - cited) <= min(0.5 * 10 ** -d, 0.05 * max(abs(actual), 1)) + 1e-9  # rounding only; a small-scale field (0.4) cannot match "0"


def _usable(s, field, show_open=False):
    """The stroke's value for `field`, or None when a quality gate drops it (same gates as score.py, docs/scoring.md §3).
    elbow is never citable: single-camera elbow error p90 is 37-48 deg (testset/results/eval-caltennis.md)."""
    if field == "elbow": return None
    if field in ("knee", "knee3d") and s.get("knee_warn"): return None
    if field == "knee" and s.get("knee2d_ok") is False: return None
    if field == "open_min" and not show_open: return None
    if field in ("contact_h", "contact_fwd") and not (_num(s.get("vis")) and s["vis"] >= 0.5): return None
    if field == "prep" and (s.get("prep_trunc") is True or s.get("prep_trunc") is None and _num(s.get("prep")) and s["prep"] >= 0.999): return None  # lower bound only, score.py leaves it out too
    v = s.get(field)
    return v if _num(v) else None


def _cite(c, strokes, groups, show_open=False):
    """None if the cite checks out, else the reason."""
    who = lambda s: s.get("player") or "me"
    if not isinstance(c, dict): return "cite 的每一項要是物件"
    if "stroke" in c:
        n = c["stroke"]
        if not isinstance(n, int) or not 1 <= n <= len(strokes): return f"拍 #{n} 不存在"
        s = strokes[n - 1]; f = c.get("field")
        if not isinstance(f, str) or f not in s or isinstance(s[f], (list, dict, str)): return f"#{n} 沒有數值欄位 {f}"
        v = _usable(s, f, show_open)
        if v is None: return f"#{n} 的 {f} 被品質閘門排除或是空值，不能引用"
        return None if _match(v, c.get("value")) else f"#{n} {f} 實際 {v}，引用 {c.get('value')}"
    if "metric" in c:  # a number from scores.json
        g = next((g for g in groups if g["kind"] == c.get("kind") and g["player"] == (c.get("player") or "me")), None)
        if g is None: return f"scores.json 沒有 {c.get('player') or 'me'} {c.get('kind')} 這組"
        m, st = c["metric"], c.get("stat", "score")
        if m in GROUP_KEYS: v = g.get(m)
        elif m in g["metrics"] and st in SCORE_STATS: v = g["metrics"][m].get(st)
        else: return f"scores.json 沒有 {m}／{st}"
        return None if _match(v, c.get("value")) else f"{c['kind']} {m} {st} 實際 {v}，引用 {c.get('value')}"
    if "stat" in c:  # recomputed from the strokes that pass the gates
        st, f = c["stat"], c.get("field")
        if st not in STATS: return f"不認得 stat {st}"
        sel = [s for s in strokes if s["kind"] == c.get("kind") and who(s) == (c.get("player") or "me") and c.get("drill", s.get("drill")) == s.get("drill")]
        vals = [v for v in (_usable(s, f, show_open) for s in sel) if v is not None]
        if not vals: return f"{c.get('kind')} {c.get('drill', '')} {f} 沒有可用的拍"
        v = float(STATS[st](vals)) if st != "n" else len(vals)
        return None if _match(v, c.get("value")) else f"{c['kind']} {c.get('drill', '')} {f} {st} 實際 {round(v, 2)}，引用 {c.get('value')}"
    return "cite 要有 stroke、metric 或 stat"


def check(notes, strokes, scores):
    """Return one error string per failing finding ('#<k> <title>: reason; reason')."""
    out = []
    for i, f in enumerate(notes.get("findings", []), 1):
        cites = f.get("cite") or []; errs = []
        if not isinstance(cites, list): cites = []
        if not cites: errs.append("沒有引用（cite）")
        errs += [r for r in (_cite(c, strokes, scores.get("groups", []), scores.get("show_open") is True) for c in cites) if r]
        vals = [c["value"] for c in cites if isinstance(c, dict) and _num(c.get("value"))]
        text = f.get("text", "")
        U = r"(?:°|%|％|秒)"
        # target ranges (0.3–0.8, 75%-85%) are not citations, but a degree range (120–130°) cites both ends
        rng = lambda m: f" {m.group(1)}° {m.group(3)}° " if "°" in (m.group(2) or "") + (m.group(4) or "") else " "
        bare = re.sub(rf"#\d+|(\d+(?:\.\d+)?)\s*({U})?\s*[–~～-]\s*(\d+(?:\.\d+)?)\s*({U})?", lambda m: " " if m.group(0).startswith("#") else rng(m), text)
        for m in re.finditer(rf"(?<![\d.:,°%％])([-−]?\d+(?:\.\d+)?)(\s*{U})?", bare):  # 1:04.8 and 1,234.5 are not decimals
            x, u = m.group(1).replace("−", "-"), (m.group(2) or "").strip()
            if not u and "." not in x: continue  # plain integers (62 拍, 3 次) are counts
            ok = (lambda v: abs(float(x) - v) <= 0.5 + 1e-9) if u == "°" else \
                 (lambda v: _match(v, float(x), x) or u in ("%", "％") and _match(v * 100, float(x), x))  # contact_h 0.53 is written as 53%
            if not any(ok(v) for v in vals): errs.append(f"文字裡的 {m.group(0).strip()} 沒有對應的引用")
        refs = {int(x) for x in re.findall(r"#(\d+)", text)} | {j[0] for j in (f.get("jump") or []) if isinstance(j, (list, tuple)) and j and isinstance(j[0], int)}
        errs += [f"拍 #{n} 不存在" for n in sorted(refs) if not 1 <= n <= len(strokes)]
        errs = list(dict.fromkeys(errs))
        if errs: out.append(f"#{i} {f.get('title', '')}: " + "；".join(errs))
    return out


if __name__ == "__main__":
    import sys
    from common import session, web, load
    D = web(session())
    if not (D / "scores.json").exists(): sys.exit(f"缺 scores.json：先跑 .venv/bin/python tools/score.py {D.name}")
    errs = check(load(D / "notes.json"), load(D / "strokes.json"), load(D / "scores.json"))
    print("\n".join(errs) if errs else f"ok：{len(load(D / 'notes.json').get('findings', []))} 條 findings 的引用都對得上")
    sys.exit(1 if errs else 0)
