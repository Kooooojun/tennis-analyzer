# check_findings.py <session> — every finding in web/sessions/<s>/notes.json must cite numbers that match strokes.json / scores.json.
# Cite formats and rules: docs/scoring.md §8. Exit 1 and list the failing findings when any check fails.
import math
import re
import numpy as np

STATS = dict(median=np.median, mean=np.mean, min=np.min, max=np.max, n=len)
SCORE_STATS = ("median", "spread", "n", "score", "cons")
GROUP_KEYS = ("total", "form", "consistency")


def _num(v): return isinstance(v, (int, float)) and not isinstance(v, bool) and not math.isnan(v)


def _match(actual, cited):
    """Cited value is the actual one rounded to the cite's own decimals (155 accepts 154.5–155.5)."""
    if not _num(actual) or not _num(cited): return False
    d = len(str(cited).split(".")[1]) if "." in str(cited) else 0
    return abs(actual - cited) <= min(0.5 * 10 ** -d, 0.05 * max(abs(actual), 1)) + 1e-9  # rounding only; a small-scale field (0.4) cannot match "0"


def _usable(s, field):
    """The stroke's value for `field`, or None when a quality gate drops it (same gates as score.py, docs/scoring.md §3)."""
    if field in ("knee", "knee3d") and s.get("knee_warn"): return None
    if field == "contact_h" and not (_num(s.get("vis")) and s["vis"] >= 0.5): return None
    v = s.get(field)
    return v if _num(v) else None


def _cite(c, strokes, groups):
    """None if the cite checks out, else the reason."""
    who = lambda s: s.get("player") or "me"
    if not isinstance(c, dict): return "cite 的每一項要是物件"
    if "stroke" in c:
        n = c["stroke"]
        if not isinstance(n, int) or not 1 <= n <= len(strokes): return f"拍 #{n} 不存在"
        s = strokes[n - 1]; f = c.get("field")
        if not isinstance(f, str) or f not in s or isinstance(s[f], (list, dict, str)): return f"#{n} 沒有數值欄位 {f}"
        v = _usable(s, f)
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
        vals = [v for v in (_usable(s, f) for s in sel) if v is not None]
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
        errs += [r for r in (_cite(c, strokes, scores.get("groups", [])) for c in cites) if r]
        vals = [c["value"] for c in cites if isinstance(c, dict) and _num(c.get("value"))]
        text = f.get("text", "")
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*°", text):
            if not any(abs(float(m.group(1)) - v) <= 0.5 + 1e-9 for v in vals): errs.append(f"文字裡的 {m.group(0)} 沒有對應的引用")
        refs = {int(x) for x in re.findall(r"#(\d+)", text)} | {j[0] for j in f.get("jump", []) if isinstance(j, (list, tuple)) and j and isinstance(j[0], int)}
        errs += [f"拍 #{n} 不存在" for n in sorted(refs) if not 1 <= n <= len(strokes)]
        errs = list(dict.fromkeys(errs))
        if errs: out.append(f"#{i} {f.get('title', '')}: " + "；".join(errs))
    return out


if __name__ == "__main__":
    import sys
    from common import session, web, load
    D = web(session())
    errs = check(load(D / "notes.json"), load(D / "strokes.json"), load(D / "scores.json"))
    print("\n".join(errs) if errs else f"ok：{len(load(D / 'notes.json').get('findings', []))} 條 findings 的引用都對得上")
    sys.exit(1 if errs else 0)
