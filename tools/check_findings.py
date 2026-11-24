# check_findings.py <session> — every finding in web/sessions/<s>/notes.json must cite numbers that match strokes.json / scores.json.
# Cite formats and rules: docs/scoring.md §8; the per-player `overall` entries: docs/advice.md. Exit 1 and list the failing findings when any check fails.
import math
import sys
import re
import numpy as np
from platform_util import utf8_stdout
from trend import NAMES, _entry, compare
from score import METRICS, MIN_N, _value

utf8_stdout()

STATS = dict(median=np.median, mean=np.mean, min=np.min, max=np.max, n=len)
SCORE_STATS = ("median", "spread", "n", "score", "cons")
GROUP_KEYS = ("total", "form", "consistency", "power", "uncapped")
PRACTICE_REPS = r"\d+(?:\.\d+)?\s*(?:次|下|組|遍)"


def _num(v): return isinstance(v, (int, float)) and not isinstance(v, bool) and not math.isnan(v)


def _match(actual, cited, txt=None):
    """Cited value is the actual one rounded to the cite's own decimals (155 accepts 154.5–155.5).
    txt: the number as written in a finding's text, so "0.30" keeps its 2 decimals."""
    if not _num(actual) or not _num(cited): return False
    txt = txt or str(cited)
    d = len(txt.split(".")[1]) if "." in txt else 0
    return abs(actual - cited) <= min(0.5 * 10 ** -d, 0.05 * max(abs(actual), 1)) + 1e-9  # rounding only; a small-scale field (0.4) cannot match "0"


def _usable(s, field, show_open=False):
    """The stroke's value for `field`, or None when a quality gate drops it: score._value's gates (docs/scoring.md §3) plus two for cites only.
    elbow is never citable: single-camera elbow error p90 is 37-48 deg (testset/results/eval-caltennis.md)."""
    if field == "elbow" or field == "open_min" and not show_open: return None
    v = _value(s, "knee", field) if field in ("knee", "knee3d") else _value(s, field)
    return v if _num(v) else None  # this _num rejects bool, score's does not


STR_KEYS = ("metric", "stat", "field", "kind", "player", "drill", "change", "drill_diff")


def _bad_keys(c):
    """Cite keys that must be strings (None allowed) but are not: a list or dict would raise TypeError in the lookups below."""
    return [k for k in STR_KEYS if c.get(k) is not None and not isinstance(c[k], str)]


DD_STATS = ("diff", "ci_lo", "ci_hi", "feed", "rally")  # drill_diff cite stats: feed / rally are the two medians (docs/scoring.md §7.2, §8)
UNSURE = r"不確定|暫定|不能確定|無法判定|不能當成確定|區間含 0"  # wording that lets a text mention a drill_diff whose interval contains 0


def _dd(c, groups):
    """(drill_diff entry, None) for a cite with `drill_diff`, or (None, reason). diff / ci_lo / ci_hi need both diff and ci (score.py leaves them None with a `reason` when a side has < 10 strokes)."""
    g = next((g for g in groups if g["kind"] == c.get("kind") and g["player"] == (c.get("player") or "me")), None)
    if g is None: return None, f"scores.json 沒有 {c.get('player') or 'me'} {c.get('kind')} 這組"
    dd = g.get("drill_diff")
    if not isinstance(dd, dict): return None, f"{c.get('kind')} 這組的 scores.json 沒有 drill_diff（舊檔，重跑 score.py）"
    if dd.get("metrics") is None: return None, f"{c.get('kind')} 沒有 drill_diff：{dd.get('reason')}"
    m, st = c["drill_diff"], c.get("stat")
    if not isinstance(m, str) or m not in dd["metrics"]: return None, f"drill_diff 沒有 metric {m}"
    if st not in DD_STATS: return None, f"drill_diff 不認得 stat {st}（要 {'／'.join(DD_STATS)}）"
    e = dd["metrics"][m]
    if st in ("feed", "rally"):
        return (e, None) if _num(e[st].get("median")) else (None, f"{c.get('kind')} {m} {st} 沒有中位數（{st} {e[st].get('n')} 拍）")
    if not _num(e.get("diff")) or not isinstance(e.get("ci"), list): return None, f"{c.get('kind')} {m} 的 diff／ci 是 null，不能引用：{e.get('reason')}"
    return e, None


def _dd_value(e, st): return e[st]["median"] if st in ("feed", "rally") else e["diff"] if st == "diff" else e["ci"][st == "ci_hi"]


def _dd_unsure(c, groups):
    """True when the cite's interval contains 0, so a text citing it must not state the difference as certain."""
    e = _dd(c, groups)[0]
    return e is not None and c.get("stat") in ("diff", "ci_lo", "ci_hi") and e["ci"][0] <= 0 <= e["ci"][1]


def _cite(c, strokes, groups, show_open=False):
    """None if the cite checks out, else the reason."""
    who = lambda s: s.get("player") or "me"
    if not isinstance(c, dict): return "cite 的每一項要是物件"
    if _bad_keys(c): return f"cite 的 {'、'.join(_bad_keys(c))} 要是字串"
    if "change" in c and (c["change"] not in ("up", "down") or "stroke" in c or not isinstance(c.get("metric"), str) or c.get("stat", "score") not in ("score", "cons")):
        return "change 只能是 up／down，且須引用分數或分項一致性"
    if "stroke" in c:
        n = c["stroke"]
        if not isinstance(n, int) or not 1 <= n <= len(strokes): return f"拍 #{n} 不存在"
        s = strokes[n - 1]; f = c.get("field")
        if not isinstance(f, str) or f not in s or isinstance(s[f], (list, dict, str)): return f"#{n} 沒有數值欄位 {f}"
        v = _usable(s, f, show_open)
        if v is None: return f"#{n} 的 {f} 被品質閘門排除或是空值，不能引用"
        return None if _match(v, c.get("value")) else f"#{n} {f} 實際 {v}，引用 {c.get('value')}"
    if "drill_diff" in c:  # self-feed minus rally, from scores.json
        e, why = _dd(c, groups)
        if why: return why
        v = _dd_value(e, c["stat"])
        return None if _match(v, c.get("value")) else f"{c['kind']} drill_diff {c['drill_diff']} {c['stat']} 實際 {v}，引用 {c.get('value')}"
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


EVIDENCE_FIELDS = (*METRICS, "knee3d")  # knee3d is the knee metric's other source (score.py picks one per group); id, vis, elbow ... are not measurements to score


def _evidenced(cites, strokes, groups, show_open):
    """True when a problem finding rests on more than one stroke (docs/scoring.md §8):
    - a metric cite (stat other than n, or a group score such as total), or stat n whose group metric has n >= score.MIN_N;
    - a stat cite of median / mean (min, max and n say nothing about the spread of strokes) over a scoring field with usable n >= score.MIN_N;
    - cites of 2+ different strokes.
    A cite with `stroke` is one stroke whatever else it carries; a cite with `metric` is never read as a stat cite, so a stray `field` on it is ignored."""
    if len({c["stroke"] for c in cites if "stroke" in c}) >= 2: return True
    for c in cites:
        if "stroke" in c: continue
        if "drill_diff" in c:
            if c.get("stat") in ("diff", "ci_lo", "ci_hi"): return True  # diff needs >= 10 strokes per drill (score.MIN_N_DRILL); _cite already checked it exists
        elif "metric" in c:
            g = next((g for g in groups if g["kind"] == c.get("kind") and g["player"] == (c.get("player") or "me")), None)
            if c["metric"] in GROUP_KEYS or c.get("stat", "score") != "n": return True
            if g is not None and (g["metrics"].get(c["metric"]) or {}).get("n", 0) >= MIN_N: return True  # the value _cite just matched, from scores.json
        elif c.get("stat") in ("median", "mean") and c.get("field") in EVIDENCE_FIELDS and _group_n(c, strokes, show_open) >= MIN_N: return True
    return False


def _group_n(c, strokes, show_open):
    """Usable strokes behind a group stat cite: same kind, player and drill (none = all), past the quality gates."""
    return sum(_usable(s, c["field"], show_open) is not None for s in strokes if s["kind"] == c.get("kind")
               and (s.get("player") or "me") == (c.get("player") or "me") and c.get("drill", s.get("drill")) == s.get("drill"))


MAIN_MIN_N = 10  # docs/advice.md: an overall main point compares two groups of >= 10 usable strokes each (暫定, same order as the framework's gate)


def _main_evidenced(cites, player, strokes, groups, show_open):
    """True when an overall main point rests on a metric cite of this player (stat other than n, or a group score),
    or on a comparison: median/mean cites of one field and kind in two different drills, each with >= MAIN_MIN_N usable strokes."""
    mine = [c for c in cites if isinstance(c, dict) and "stroke" not in c and (c.get("player") or "me") == player]
    if any("metric" in c and (c["metric"] in GROUP_KEYS or c.get("stat", "score") != "n") for c in mine): return True
    if any("drill_diff" in c and c.get("stat") in ("diff", "ci_lo", "ci_hi") for c in mine): return True  # a self-feed vs rally diff is itself the comparison
    drills = {}
    for c in mine:
        if "metric" in c or c.get("stat") not in ("median", "mean") or c.get("field") not in EVIDENCE_FIELDS or not isinstance(c.get("drill"), str): continue
        if _group_n(c, strokes, show_open) >= MAIN_MIN_N: drills.setdefault((c["field"], c.get("kind")), set()).add(c["drill"])
    return any(len(d) >= 2 for d in drills.values())


def _look_errs(look, strokes, player=None):
    """`look` = stroke numbers the analyst checked on the four-stage picture or strip: >= 3 distinct strokes that exist (and are the player's)."""
    if not isinstance(look, list): return ["look 要是拍號陣列"]
    ok = [n for n in look if type(n) is int and 1 <= n <= len(strokes)]  # type() so True is not stroke #1
    errs = [f"look 的拍 #{n} 不存在" for n in look if not (type(n) is int and 1 <= n <= len(strokes))]
    errs += [f"look 的拍 #{n} 不是 {player} 的" for n in ok if player is not None and (strokes[n - 1].get("player") or "me") != player]
    if len(set(ok)) < len(ok): errs.append("look 的拍號重複")
    if len(set(ok)) < 3: errs.append("look 至少要 3 個看過圖的拍號")
    return errs


def _change_errors(finding, scores, runs):
    """Check directional claims against the same score histories as trend.py."""
    text = finding.get("title", "") + "。" + finding.get("text", "")
    up, down = r"進步|改善|變好|(?:更|比較)(?:好|穩|一致)|比[^不沒無未非]*穩|一致了", r"退步|變差|(?:分數?|總分|一致性|技術)(?:也|又|都|再)?(?:下降|降低)|(?:更|比較)差|(?:變得?|更)不穩|比[^不沒無未非]*不穩"
    cross_session = r"前場|上場|上次|前次|之前|昨天|跨場|\d{1,2}/\d{1,2}"
    drills = {c.get("drill") for c in finding.get("cite", []) if isinstance(c, dict) and c.get("drill") is not None}
    clauses = [c.strip() for c in re.split(r"[。；，,：:！!?？\n]|但是|而且|所以|因此|但|而", text) if re.search(up + "|" + down, c)]
    split_clauses = []
    for clause in clauses:
        parts = re.split(r"(而且|並且|但是|同時|以及|且|但|而|與|及|、)", clause)
        pending = parts[0]
        for i in range(1, len(parts), 2):
            if re.search(up + "|" + down, pending) and re.search(up + "|" + down, "".join(parts[i + 1:])):
                split_clauses.append(pending)
                pending = parts[i + 1]
            else:
                pending += parts[i] + parts[i + 1]
        split_clauses.append(pending)
    clauses = [c for c in split_clauses
               if not re.search(r"(?:不能|無法|沒有|不足以|不代表|不算|不可).*?(?:" + up + "|" + down + ")", c)
               and not (not re.search(cross_session, c) and re.match(r"下次|下一次|未來|建議|試著|希望|目標|請|先改善", c))
               and not (not re.search(cross_session, text) and len(drills) >= 2 and re.search(r"自拋|對打|高拋", c))]
    declared = [c for c in finding.get("cite", []) if isinstance(c, dict) and c.get("change") in ("up", "down") and isinstance(c.get("metric"), str)]
    if not clauses and not declared: return []
    identities = {(c.get("player") or "me", c.get("kind")) for c in finding.get("cite", []) if isinstance(c, dict) and "kind" in c}
    if not identities: return ["進退步宣稱缺少球員與拍種的群組引用"]

    def entry(run, group):
        h = _entry(run, group)
        h["items"].update({k: group.get(k) for k in GROUP_KEYS})
        h["uncertainty"].update(group.get("uncertainty") or {})
        form = sorted(m for m, x in group["metrics"].items() if x["score"] is not None and not METRICS.get(m, {}).get("power"))
        power = sorted(m for m, x in group["metrics"].items() if x["score"] is not None and METRICS.get(m, {}).get("power"))
        h["component_sets"] = {"form": form, "power": power, "uncapped": [form, h["cons_set"]]}
        h["items"].update({m + ".cons": x["cons"] for m, x in group["metrics"].items()})
        h["uncertainty"].update({m + ".cons": (x.get("uncertainty") or {}).get("cons") for m, x in group["metrics"].items()})
        return h

    errors = []
    for player, kind in identities:
        group = next((g for g in scores.get("groups", []) if (g["player"], g["kind"]) == (player, kind)), None)
        if group is None:
            errors.append(f"{kind}沒有足夠的誤差估計，不能宣稱進步或退步")
            continue
        history = []
        for run in runs:
            if run.get("session") == scores.get("session") or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(run.get("date"))): continue
            if (str(run["date"]), run.get("session", "")) >= (str(scores.get("date", "")), scores.get("session", "")): continue
            old = next((g for g in run.get("groups", []) if (g["player"], g["kind"]) == (player, kind)), None)
            if old is not None: history.append(entry(run, old))
        history.sort(key=lambda h: (h["date"], h["session"]))
        flags = {f["item"]: f for f in compare([*history, entry({"session": "", **scores}, group)])} if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(scores.get("date"))) else {}
        names = {**NAMES, "form": "技術", "power": "力量", "uncapped": "未壓前總分"}
        cited_items = [c["metric"] + (".cons" if c.get("stat") == "cons" else "") for c in finding.get("cite", []) if isinstance(c, dict) and isinstance(c.get("metric"), str)
                       and (c.get("player") or "me", c.get("kind")) == (player, kind)]
        cited_cons = [m for m in cited_items if m.endswith(".cons")]
        claims = [(c["metric"] + (".cons" if c.get("stat") == "cons" else ""), c["change"]) for c in declared
                  if (c.get("player") or "me", c.get("kind")) == (player, kind)]
        for clause in clauses:
            mentioned = re.findall("|".join(re.escape(n) for n in sorted(names.values(), key=len, reverse=True)), clause)
            items = [item for item, name in names.items() if name in mentioned]
            if not items or items == ["consistency"] and cited_cons:
                items = cited_cons or cited_items
            if re.search(r"穩|一致", clause):
                if cited_cons: items = [m for m in items if m != "consistency"] + cited_cons
                metric_items = [m for m in items if m.removesuffix(".cons") in group["metrics"]]
                if re.search(r"進步|退步|改善|變好|變差|(?:更|比較)(?:好|差)", clause):
                    specific = [m for m in metric_items if m.endswith(".cons") or re.search(re.escape(names.get(m, m)) + r"(?:的|變得)?(?:一致性|更穩|比較穩)", clause)]
                    items = [m for m in items if m not in specific and not (m == "consistency" and specific)]
                else:
                    specific, items = metric_items, [m for m in items if m in GROUP_KEYS and names[m] in mentioned]
                items += [m if m.endswith(".cons") else m + ".cons" for m in specific]
                items = items or ["consistency"]
            claims += [(item, direction) for item in set(items or ["total"]) for direction, pattern in (("up", up), ("down", down)) if re.search(pattern, clause)]
        for item, direction in sorted(set(claims)):
            name = names.get(item.removesuffix(".cons"), item) + ("一致性" if item.endswith(".cons") else "")
            flag = flags.get(item)
            if flag is None: errors.append(f"{name}沒有足夠的誤差估計，不能宣稱進步或退步（需同版本、同機位可比資料）")
            elif flag["flag"] == "在誤差內": errors.append(f"{name}變化在誤差內（差 {flag['diff']}，門檻 {flag['threshold']:.2f}），不能宣稱進步或退步")
            elif direction == "up" and flag["diff"] < 0 or direction == "down" and flag["diff"] > 0:
                errors.append(f"{name}進退步方向與實際差值 {flag['diff']} 相反")
    return errors


def check(notes, strokes, scores, runs=()):
    """Return one error string per failing finding ('#<k> <title>: reason; reason')."""
    out = []
    for i, f in enumerate(notes.get("findings", []), 1):
        errs = _finding_errs(f, strokes, scores, runs)
        if errs: out.append(f"#{i} {f.get('title', '')}: " + "；".join(errs))
    if "overall" in notes: out += _overall_errs(notes["overall"], strokes, scores, runs)
    return out


def _finding_errs(f, strokes, scores, runs=()):
    """Reasons one finding fails ([] = it checks out); overall items are checked through it as info findings."""
    cites = f.get("cite") or []; errs = []
    if not isinstance(cites, list): cites = []
    if not cites: errs.append("沒有引用（cite）")
    errs += [r for r in (_cite(c, strokes, scores.get("groups", []), scores.get("show_open") is True) for c in cites) if r]
    if not errs and not f.get("good") and not f.get("info") and not _evidenced(cites, strokes, scores.get("groups", []), scores.get("show_open") is True):
        errs.append(f"問題型 finding 至少要有：一個 metric 引用（stat 不是 n，或 n ≥ {MIN_N}）、一個 median／mean 的群組統計引用（量測欄位、可用拍數 ≥ {MIN_N}），或兩個以上不同拍號的單拍引用（單拍、計數、min／max 不能撐起一條問題）")
    if any(isinstance(c, dict) and "drill_diff" in c and not _bad_keys(c) and _dd_unsure(c, scores.get("groups", [])) for c in cites) and not re.search(UNSURE, f.get("title", "") + f.get("text", "")):
        errs.append("drill_diff 的區間含 0，文字不能寫成確定的差：要寫「不確定」或「暫定」（docs/advice.md）")
    if "look" in f: errs += _look_errs(f["look"], strokes)
    elif not f.get("good") and not f.get("info") and any(isinstance(c, dict) and "prep" in (c.get("field"), c.get("metric"), c.get("drill_diff")) for c in cites):
        errs.append("問題型 finding 引用 prep 要有 look（看過圖的拍號，≥ 3）：prep 量的是手腕最後方到擊球，不是轉身時機")
    errs += _change_errors({**f, "cite": [c for c in cites if isinstance(c, dict) and not _bad_keys(c)]}, scores, runs)  # a malformed cite is already reported
    vals = [c["value"] for c in cites if isinstance(c, dict) and _num(c.get("value"))]
    text = f.get("text", "")
    practice = re.search(r"(?:練習\s*[:：]|(?:^|[。；！？\n])\s*(?:下次|下一次))(.*)", text, re.S)
    if practice and re.search(PRACTICE_REPS, practice[1]):
        errs.append("練習建議不要指定次數或組數")
    U = r"(?:°|度|%|％|秒)"
    # target ranges (0.3–0.8, 75%-85%) are not citations, but a degree range (120–130°) cites both ends
    rng = lambda m: f" {m.group(1)}° {m.group(3)}° " if {m.group(2), m.group(4)} & {"°", "度"} else " "
    # an ASCII '-' joins a range only with no space around it: "0.5 -0.20" is a number and a negative one
    bare = re.sub(rf"#\d+|\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?|(\d+(?:\.\d+)?)(?:\s*({U}))?(?:\s*[–~～]\s*|-)(\d+(?:\.\d+)?)\s*({U})?",
                  lambda m: rng(m) if m.group(1) else " ", text)  # #NN and 1,234.5 (thousands) are not citations
    for m in re.finditer(rf"(?<![\d.:°%％])([-−]?\d+(?:\.\d+)?)(\s*{U})?", bare):  # 1:04.8 is a time, not a decimal
        x, u = m.group(1).replace("−", "-"), (m.group(2) or "").strip()
        if not u and "." not in x: continue  # plain integers (62 拍, 3 次) are counts
        ok = (lambda v: abs(float(x) - v) <= 0.5 + 1e-9) if u in ("°", "度") else \
             (lambda v: _match(v, float(x), x) or u in ("%", "％") and _match(v * 100, float(x), x))  # contact_h 0.53 is written as 53%
        if not any(ok(v) for v in vals): errs.append(f"文字裡的 {m.group(0).strip()} 沒有對應的引用")
    refs = {int(x) for x in re.findall(r"#(\d+)", text)} | {j[0] for j in (f.get("jump") or []) if isinstance(j, (list, tuple)) and j and isinstance(j[0], int)}
    errs += [f"拍 #{n} 不存在" for n in sorted(refs) if not 1 <= n <= len(strokes)]
    return list(dict.fromkeys(errs))


def _overall_errs(overall, strokes, scores, runs=()):
    """notes.json `overall` (docs/advice.md): per player at most one entry with one main point or `insufficient`, an optional second, and `look`.
    Malformed input gives error strings, never an exception: build_site.py checks every session."""
    if not isinstance(overall, list): return ["overall 要是陣列（每位球員一筆）"]
    players, seen, out = {s.get("player") or "me" for s in strokes}, set(), []
    for i, e in enumerate(overall, 1):
        if not isinstance(e, dict): out.append(f"overall 第 {i} 筆: 要是物件"); continue
        p, errs = e.get("player"), []
        if not isinstance(p, str) or p not in players: errs.append(f"球員 {p} 不在這場的拍裡"); p = None
        elif p in seen: errs.append(f"{p} 有兩筆 overall，每位球員最多一筆")
        seen.add(p)
        if ("main" in e) == ("insufficient" in e): errs.append("main 和 insufficient 要剛好有一個")
        if "insufficient" in e and not (isinstance(e.get("film_next"), str) and e["film_next"].strip()): errs.append("insufficient 一定要有 film_next（下次怎麼拍）")
        errs += _look_errs(e["look"], strokes, p) if "look" in e else ["沒有 look（看過圖的拍號，≥ 3）"]
        for key in ("main", "second", "insufficient"):
            if key in e: errs += [f"{key}: {r}" for r in _item_errs(key, e[key], p, strokes, scores, runs)]
        if errs: out.append(f"overall {p or f'第 {i} 筆'}: " + "；".join(dict.fromkeys(errs)))
    return out


def _item_errs(key, it, player, strokes, scores, runs=()):
    """One main / second / insufficient item: required text, cites that match (same rules as a finding's text), and for main the stronger evidence rule."""
    if not isinstance(it, dict): return ["要是一個物件（每位球員只有一件）"]
    errs = [f"缺 {k}" for k in ("title", "why") + (() if key == "insufficient" else ("practice",)) if not (isinstance(it.get(k), str) and it[k].strip())]
    jump = it.get("jump") if isinstance(it.get("jump"), list) else None
    if "jump" in it and jump is None: errs.append("jump 要是陣列")
    elif key == "main" and not jump: errs.append("缺 jump（要看的拍號）")
    if jump and not all(isinstance(j, (list, tuple)) and len(j) == 2 and type(j[0]) is int and isinstance(j[1], str) for j in jump): errs.append("jump 每項要是 [拍號, 標籤]")
    text = "。".join(it[k] for k in ("title", "why", "practice", "cue") if isinstance(it.get(k), str))
    if isinstance(it.get("practice"), str) and re.search(PRACTICE_REPS, it["practice"]):
        errs.append("練習建議不要指定次數或組數")
    errs += _finding_errs(dict(info=True, title="", text=text, cite=it.get("cite"), jump=jump), strokes, scores, runs)
    if key == "main" and not _main_evidenced(it.get("cite") if isinstance(it.get("cite"), list) else [], player, strokes, scores.get("groups", []), scores.get("show_open") is True):
        errs.append(f"主要的事要有這位球員的一個 metric 引用（stat 不是 n），或一個比較：同欄位、同拍種、兩種 drill 的 median／mean，各 ≥ {MAIN_MIN_N} 拍可用")
    return errs


if __name__ == "__main__":
    import sys
    from common import session, web, load
    D = web(session())
    if not (D / "scores.json").exists(): sys.exit(f"缺 scores.json：先跑 .venv/bin/python tools/score.py {D.name}")
    runs = [load(p) for p in D.parent.glob("*/scores.json")]
    notes = load(D / "notes.json")
    errs = check(notes, load(D / "strokes.json"), load(D / "scores.json"), runs=runs)
    print("\n".join(errs) if errs else f"ok：{len(notes.get('findings', []))} 條 findings、{len(notes.get('overall', []))} 位球員的整體建議都對得上")
    sys.exit(1 if errs else 0)
