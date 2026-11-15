"""THETIS 評估：對 work/thetis/<mode>/<clip>/pose*.npy 跑 kind.classify / hand_gate / arm_checks，結果存 work/thetis/res_<mode>.json。
用法：[HAND=R|L] [EYE=1] [APEX=1] .venv/bin/python tools/eval_thetis.py <mode> [first|all]
環境變數：HAND＝全部受試者強制用該手；EYE＝用 work/thetis/eye_hands.json 的眼睛確認手（其餘 HAND 或 R）；APEX＝發球／高壓改用持拍腕最高點當擊球點。
結果檔名 res_<mode><HAND><E><A>_<which>.json（最佳設定 = interp60 + HAND=R EYE=1 APEX=1 -> res_interp60REA_first.json）。
本機輸入（都不進 git，也沒有腳本產生，要自己備）：work/thetis/p18/<clip>/pose*.npy（原 fps 姿態，pose_full.py N=1）、p60/<clip>/（fps=60 重複影格後的姿態）、
list_first.txt／list_rest.txt（影片檔名清單，每行一支）、eye_hands.json（可無）。
mode: native18（18 fps 姿態直接當 60 fps 餵）、dup60（ffmpeg fps=60 重複影格後再跑姿態）、interp60（18 fps 姿態線性內插到 60 fps）。
THETIS 只在本機測試，結果與影格都不進 git（資料集：Gourgari et al. 2013）。"""
import glob, json, os, re, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from metrics import hand_gate, arm_checks, _scale
from kind import classify

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = f"{R}/work/thetis"; SIZE = (640, 480)
CLIP_IDX = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
# 檔名裡的動作縮寫 -> 類別（資料夾名與檔名不同，見資料集 README）
GROUP = dict(foreflat="FH", foreopen="FH", fslice="FH", backhand="BH", backhand2h="BH", bslice="BH",
             serflat="SV", serkick="SV", serslice="SV", smash="OH", fvolley="FHV", bvolley="BHV")


def interp(A, fps_in=18, fps_out=60):
    """線性內插 (frames, ...) 到 fps_out；NaN 的相鄰格不內插（結果 NaN）。"""
    n = len(A); t = np.arange(int((n - 1) * fps_out / fps_in) + 1) * fps_in / fps_out
    i0 = np.minimum(t.astype(int), n - 2); a = (t - i0).reshape(-1, *[1] * (A.ndim - 1))
    return (A[i0] * (1 - a) + A[i0 + 1] * a).astype(np.float32)


def load(mode, name):
    d = f"{W}/{'p60' if mode == 'dup60' else 'p18'}/{name}"
    P = np.load(f"{d}/pose.npy"); Wd = np.load(f"{d}/pose_world.npy")
    if mode == "interp60": P, Wd = interp(P), interp(Wd)
    return P.astype(float), Wd.astype(float)


def peak(P, hand, fps):
    """擊球點定義：持拍腕相對髖中心的速度（軀幹長/秒，3 格中位數平滑）的最大值，只看片段 15%–95%。回傳格號或 None。"""
    xy = P[:, :, :2] * _scale(SIZE); wr = 16 if hand == "R" else 15
    hip = (xy[:, 23] + xy[:, 24]) / 2; L = np.nanmedian(np.linalg.norm((xy[:, 11] + xy[:, 12]) / 2 - hip, axis=1))
    if not np.isfinite(L) or L <= 0: return None
    r = (xy[:, wr] - hip) / L; v = np.linalg.norm(np.diff(r, axis=0), axis=1) * fps
    k = max(3, int(round(fps * 0.05)) | 1)
    v = np.array([np.nanmedian(v[max(0, i - k // 2):i + k // 2 + 1]) if np.isfinite(v[max(0, i - k // 2):i + k // 2 + 1]).any() else np.nan for i in range(len(v))])
    lo, hi = int(0.15 * len(v)), int(0.95 * len(v))
    if not np.isfinite(v[lo:hi]).any(): return None
    return int(lo + np.nanargmax(v[lo:hi])) + 1


def apex(P, hand, fps):
    """發球／高壓的擊球點定義：持拍腕最高點（影像 y 最小，5 格中位數平滑），只看片段 15%–95%。"""
    wr = 16 if hand == "R" else 15; y = P[:, wr, 1].copy(); n = len(y); k = max(3, int(round(fps * 0.08)) | 1)
    y = np.array([np.nanmedian(y[max(0, i - k // 2):i + k // 2 + 1]) if np.isfinite(y[max(0, i - k // 2):i + k // 2 + 1]).any() else np.nan for i in range(n)])
    lo, hi = int(0.15 * n), int(0.95 * n)
    return int(lo + np.nanargmin(y[lo:hi])) if np.isfinite(y[lo:hi]).any() else None


# 眼睛確認的慣用手（只列兩段動作都清楚的；其他受試者沒有真值）
EYE = {int(k): v for k, v in json.load(open(f"{W}/eye_hands.json")).items()} if os.path.exists(f"{W}/eye_hands.json") else {}


def clip_layout(P, Wd, f):
    fr = [[[float(x) for x in P[i, j]] for j in CLIP_IDX] if np.isfinite(P[i, 0, 0]) else None for i in range(len(P))]
    wl = [[[float(x) for x in Wd[i, j]] for j in CLIP_IDX] if np.isfinite(Wd[i, 0, 0]) else None for i in range(len(P))]
    return fr, wl


def main():
    mode = sys.argv[1]; which = sys.argv[2] if len(sys.argv) > 2 else "first"
    assert mode in ("native18", "dup60", "interp60") and which in ("first", "all"), __doc__
    fps = 18 if mode == "native18" else 60
    names = [os.path.basename(l.strip())[:-4] for l in open(f"{W}/list_first.txt")]
    if which == "all": names += [os.path.basename(l.strip())[:-4] for l in open(f"{W}/list_rest.txt")]
    names = [n for n in names if os.path.exists(f"{W}/{'p60' if mode == 'dup60' else 'p18'}/{n}/pose.npy")]
    meta = {n: re.match(r"p(\d+)_(.+)_s(\d+)", n).groups() for n in names}
    D = {n: load(mode, n) for n in names}
    hands = {}
    for p in sorted({int(m[0]) for m in meta.values()}):
        ns = [n for n in names if int(meta[n][0]) == p]
        h, ratio, _ = hand_gate([D[n][0] for n in ns], SIZE)  # None = unsure (falls back to R below)
        hands[p] = (h, ratio)
    out = []
    for n in names:
        p, act, s = meta[n]; P, Wd = D[n]; h = os.environ.get("HAND") or hands[int(p)][0] or "R"
        if os.environ.get("EYE"): h = EYE.get(int(p), os.environ.get("HAND") or "R")
        f = apex(P, h, fps) if os.environ.get("APEX") and GROUP[act] in ("SV", "OH") else peak(P, h, fps)
        row = dict(name=n, person=int(p), action=act, seq=int(s), group=GROUP[act], hand=h, n=len(P), f=f)
        if f is not None:
            k = classify(P, f, h, Wd, SIZE); row.update(kind=k["kind"], conf=k["conf"], side=k["side"])
            # 手臂檢查：用真實動作類別決定檢查哪一種（發球／單手反拍），與預測拍種無關
            kk = {"SV": "SV", "BH": "BH"}.get(GROUP[act]) if act in ("backhand", "serflat", "serkick", "serslice") else None
            if kk:
                fr, wl = clip_layout(P, Wd, f); row["arm"] = arm_checks(fr, f, SIZE, wl, kk, h, one_hand=(act == "backhand"))
        else: row.update(kind="?", conf=0.0, side=None)
        out.append(row)
    tag = os.environ.get("HAND", "") + ("E" if os.environ.get("EYE") else "") + ("A" if os.environ.get("APEX") else "")
    json.dump(dict(hands={str(k): v for k, v in hands.items()}, rows=out), open(f"{W}/res_{mode}{tag}_{which}.json", "w"), ensure_ascii=False)
    print(mode, len(out), "clips; hands:", {v[0] for v in hands.values()})


if __name__ == "__main__":
    main()
