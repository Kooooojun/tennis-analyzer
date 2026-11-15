# ct_report.py <res.csv> <fig dir> — numbers and plots for testset/results/eval-caltennis.md
import sys, csv, numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

R = list(csv.DictReader(open(sys.argv[1]))); fd = sys.argv[2]
col = lambda k, rows: np.array([float(r[k]) for r in rows])
REF_ERR = 10.0  # px: reference joints of the window must reproject within this (median)


def rk(x):
    return np.argsort(np.argsort(x))


def sp(x, y):
    m = np.isfinite(x) & np.isfinite(y); return float(np.corrcoef(rk(x[m]), rk(y[m]))[0, 1]) if m.sum() > 5 else np.nan


def q(a):
    a = a[np.isfinite(a)]
    return f"n={len(a)} 中位數 {np.median(a):.1f}° p75 {np.percentile(a, 75):.1f}° p90 {np.percentile(a, 90):.1f}°" if len(a) else "n=0"


for part, ref, e2k, e3k, azk, errk in (("膝", "knee_ref", "knee2d", "knee3d", "az_knee", "err_leg"), ("肘", "elbow_ref", "elbow2d", "elbow3d", "az_contact", "err_arm")):
    rows = [r for r in R if float(r[errk]) <= REF_ERR and all(np.isfinite(float(r[k])) for k in (ref, e2k, e3k, azk))]
    kr, k2, k3, az, cam = col(ref, rows), col(e2k, rows), col(e3k, rows), np.abs(col(azk, rows)), col("cam", rows)
    d2, d3, gap = k2 - kr, k3 - kr, np.abs(k3 - k2)
    print(f"\n## {part}（參考重投影誤差中位數 ≤ {REF_ERR:.0f} px：{len(rows)}/{len(R)} 拍·機）")
    print(f"- 2D |誤差|：{q(np.abs(d2))}；偏差（2D−參考）中位數 {np.median(d2):+.1f}°")
    print(f"- 3D |誤差|：{q(np.abs(d3))}；偏差（3D−參考）中位數 {np.median(d3):+.1f}°")
    print(f"- 3D 比 2D 接近參考的比例：{np.mean(np.abs(d3) < np.abs(d2)):.0%}")
    print(f"- 參考值範圍：p10 {np.percentile(kr, 10):.0f}° 中位數 {np.median(kr):.0f}° p90 {np.percentile(kr, 90):.0f}°")
    print("\n| 攝影機 | 拍數 | 2D 中位數 | 2D p90 | 3D 中位數 | 3D p90 |\n|---|---|---|---|---|---|")
    for c in (1, 2, 3, 4):
        m = cam == c
        print(f"| {c} | {m.sum()} | {np.median(abs(d2[m])):.1f} | {np.percentile(abs(d2[m]), 90):.1f} | {np.median(abs(d3[m])):.1f} | {np.percentile(abs(d3[m]), 90):.1f} |")
    print("\n| 方位角 |az|（0=正前、90=側面、180=正後） | 拍數 | 2D 中位數 | 2D p90 | 3D 中位數 | 3D p90 |\n|---|---|---|---|---|---|")
    for lo in range(0, 180, 30):
        m = (az >= lo) & (az < lo + 30)
        if m.sum() < 3: print(f"| {lo}–{lo + 30}° | {m.sum()} | – | – | – | – |"); continue
        print(f"| {lo}–{lo + 30}° | {m.sum()} | {np.median(abs(d2[m])):.1f} | {np.percentile(abs(d2[m]), 90):.1f} | {np.median(abs(d3[m])):.1f} | {np.percentile(abs(d3[m]), 90):.1f} |")
    big = np.fmax(abs(d2), abs(d3))
    print(f"\n- Spearman(|3D−2D|, 2D 誤差) = {sp(gap, abs(d2)):.2f}；(|3D−2D|, 3D 誤差) = {sp(gap, abs(d3)):.2f}；(|3D−2D|, 兩者較大誤差) = {sp(gap, big):.2f}")
    print(f"- |3D−2D| 分布：中位數 {np.median(gap):.1f}° p75 {np.percentile(gap, 75):.1f}° p90 {np.percentile(gap, 90):.1f}°")
    print("\n| 門檻 | 旗標比例 | 未旗標：2D 中位數／p90 | 未旗標：3D 中位數／p90 | 旗標：2D 中位數 | 旗標：3D 中位數 | 大誤差（2D 或 3D >20°）被抓到 |\n|---|---|---|---|---|---|---|")
    for T in (10, 15, 20, 25, 30, 35, 45):
        f = gap > T; k = ~f; bad = big > 20
        fm = lambda a, m: f"{np.median(a[m]):.1f}" if m.any() else "–"
        print(f"| {T}° | {f.mean():.0%} | {fm(abs(d2), k)}／{np.percentile(abs(d2[k]), 90):.1f} | {fm(abs(d3), k)}／{np.percentile(abs(d3[k]), 90):.1f} | {fm(abs(d2), f)} | {fm(abs(d3), f)} | {(f & bad).sum()}/{bad.sum()} |")
    fig, ax = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for a, d, nm in ((ax[0], d2, "2D"), (ax[1], d3, "MediaPipe world 3D")):
        for c, mk in zip((1, 2, 3, 4), "os^D"):
            m = cam == c; a.scatter(az[m], d[m], s=12, marker=mk, alpha=0.6, label=f"cam {c}")
        a.axhline(0, c="k", lw=0.6); a.set_xlabel("|azimuth| deg (0 front, 90 side, 180 back)"); a.set_title(f"{'knee' if part == '膝' else 'elbow'}: {nm} - reference"); a.set_xlim(0, 180)
    ax[0].set_ylabel("error (deg)"); ax[0].legend(fontsize=8); fig.tight_layout(); fig.savefig(f"{fd}/{'knee' if part == '膝' else 'elbow'}_vs_azimuth.png", dpi=110)
    fig, a = plt.subplots(figsize=(5.5, 4))
    a.scatter(gap, abs(d2), s=10, alpha=0.6, label="2D |error|"); a.scatter(gap, abs(d3), s=10, alpha=0.6, label="3D |error|")
    a.set_xlabel("|3D - 2D| (deg)"); a.set_ylabel("|error| vs reference (deg)"); a.set_title(part == "膝" and "knee" or "elbow"); a.legend(); fig.tight_layout()
    fig.savefig(f"{fd}/{'knee' if part == '膝' else 'elbow'}_gap_vs_error.png", dpi=110)
