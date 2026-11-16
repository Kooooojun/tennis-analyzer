# eval_hits.py <labels.csv> <events.npy> [player] — score detected hits against hand labels (one-to-one, nearest first).
# labels.csv: t_sec,player,kind with kind stroke | touch | unsure. Strokes are the targets. touch/unsure rows are ignore zones:
# a detection within IGNORE s of one is neither right nor wrong. events.npy (or sounds.npy): rows whose first column is the hit time in seconds.
# With [player], only that player's strokes are targets and the other players' rows become ignore zones.
# Optional '# span start end' comments specify inclusive annotated intervals; outside predictions can match within TOL but never count as FP.
import csv, sys
import numpy as np

TOL = 3 / 60 + 1e-6   # +-3 frames at 60 fps (epsilon: 0.05 s must count)
IGNORE = 0.25     # a touch/unsure label is a coarse moment, not a contact frame


def read_labels(path):
    """CSV rows plus optional inclusive '# span start end' annotation intervals."""
    lines, spans = [], []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for line in f:
            text = line.strip()
            if text.startswith("#"):
                fields = text.split()
                if text[1:].lstrip().lower().startswith(("span", "spam")) and fields[:2] != ["#", "span"]:
                    raise ValueError("範圍註解格式必須是 # span 開始 結束")
                if fields[:2] == ["#", "span"]:
                    if len(fields) != 4: raise ValueError("span 需要開始與結束秒數")
                    start, end = map(float, fields[2:])
                    if not np.isfinite([start, end]).all() or not 0 <= start <= end:
                        raise ValueError("span 必須是有限且遞增的非負秒數")
                    spans.append((start, end))
            else: lines.append(line)
    reader = csv.DictReader(lines); rows = list(reader)
    if not reader.fieldnames or "t_sec" not in reader.fieldnames: raise ValueError("標註缺少 t_sec 欄位")
    if not rows: raise ValueError("標註沒有資料列")
    for r in rows:
        if None in r or any(value is None for value in r.values()): raise ValueError("標註資料列欄數不符")
        if not np.isfinite(float(r["t_sec"])): raise ValueError("標註時間必須是有限秒數")
    if spans and any(not any(a <= float(r["t_sec"]) <= b for a, b in spans) for r in rows):
        raise ValueError("標註時間在 span 範圍外")
    return rows, spans or None


def score(targets, ignore, pred, tol=TOL, spans=None):
    """Greedy one-to-one matching within optional spans, closest first. Returns (tp [(label, pred)], fn, fp)."""
    if spans is not None:
        inside = lambda t: any(a <= t <= b for a, b in spans)
        targets, ignore = ([t for t in values if inside(t)] for values in (targets, ignore))
        pred = [p for p in pred if any(a - tol <= p <= b + tol for a, b in spans)]
    pairs = sorted((abs(p - t), i, j) for i, t in enumerate(targets) for j, p in enumerate(pred) if abs(p - t) <= tol)
    used_t, used_p, tp = set(), set(), []
    for _, i, j in pairs:
        if i in used_t or j in used_p: continue
        used_t.add(i); used_p.add(j); tp.append((targets[i], pred[j]))
    fn = [t for i, t in enumerate(targets) if i not in used_t]
    fp = [p for j, p in enumerate(pred) if j not in used_p and (spans is None or inside(p))
          and not any(abs(p - g) <= IGNORE for g in ignore)]
    return sorted(tp), fn, fp


def self_test():
    tp, fn, fp = score([1.0, 2.0], [5.0], [1.02, 1.03, 2.2, 5.1, 9.0])
    assert tp == [(1.0, 1.02)], tp           # closest wins, the second detection near 1.0 is a duplicate -> FP
    assert fn == [2.0], fn                   # 2.2 is outside +-3 frames
    assert fp == [1.03, 2.2, 9.0], fp        # 5.1 sits in the ignore zone
    assert score([], [], []) == ([], [], [])


if __name__ == "__main__":
    from platform_util import utf8_stdout
    utf8_stdout()
    if sys.argv[1:] == ["--self-test"]: self_test(); sys.exit(print("ok"))
    if len(sys.argv) not in (3, 4): sys.exit("usage: eval_hits.py <labels.csv> <events.npy> [player]")
    try: rows, spans = read_labels(sys.argv[1])
    except ValueError as exc: sys.exit(f"標註格式錯誤：{exc}")
    if rows and not {"t_sec", "player", "kind"} <= rows[0].keys(): sys.exit("標註缺少 t_sec、player 或 kind 欄位")
    if spans is None: print("提示：整支影片都當作已標註", file=sys.stderr)
    who = sys.argv[3] if len(sys.argv) == 4 else None
    is_target = lambda r: r["kind"] == "stroke" and (who is None or r["player"] == who)
    targets = [float(r["t_sec"]) for r in rows if is_target(r)]
    ignore = [float(r["t_sec"]) for r in rows if not is_target(r)]
    a = np.load(sys.argv[2]); pred = a.reshape(len(a), -1)[:, 0].tolist() if len(a) else []
    tp, fn, fp = score(targets, ignore, pred, spans=spans)
    err = np.array([p - t for t, p in tp]) * 60
    rec = len(tp) / max(len(targets), 1); prec = len(tp) / max(len(tp) + len(fp), 1)
    print(f"TP {len(tp)} FN {len(fn)} FP {len(fp)} | recall {rec:.2%} precision {prec:.2%}"
          + (f" | error frames median {np.median(err):+.1f} max |{np.abs(err).max():.1f}|" if len(err) else ""))
    if fn: print("  missed:", " ".join(f"{t:.2f}" for t in fn))
    if fp: print("  false: ", " ".join(f"{p:.2f}" for p in fp))
