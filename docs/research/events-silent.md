# 無聲影片擊球候選：純姿態峰值的負結果

2026-11-16（台灣時間）。研究對應 [issue #63](https://github.com/Kooooojun/tennis-analyzer/issues/63)，基線為 `fd05159`。**本輪不部署純姿態候選**：固定 ±0.05 秒接觸配對下，四片逐片留出召回僅 15.49–28.00%、precision 僅 7.14–14.89%。維持 `events.py`、`hits.py` 與無音軌提示原狀，issue 仍開放；此結果只否定以下候選族，不能推論所有無聲偵測方法都不可行。

## 資料與事前預測

使用兩段沿用既有拍種標註的 60 fps 使用者的對牆影片 A（A1、A2），以及既有開發用 24 fps（D24）、30 fps 對牆（D30）各一片，共 145 個 stroke 標註。額外一段 A0 的舊標註缺 kind，僅用於有聲音不變性檢查，不計召回或 precision。四支 #53 留出片完全不讀取、不評分、不調參。

全程複製既有姿態、附軌、球軌、代理片、聲音與方法紀錄到本 worktree 的 `work/i63-silent-events/`；不重新估姿態或追球。兩支低 fps 開發片沿用方法 2，對牆 A 沿用缺方法／來源 fps 紀錄的既有峰值路徑；不補寫版本以改變基線。標註、span、ignore 均原樣複製，沒有由本次結果挑評分範圍。原聲音訊先確認有非零取樣，再產生同取樣數、全零 float32 PCM 對照。

量測前寫下預測及 10 類失敗方式，涵蓋靜音判定、接觸時間偏移、假揮拍峰、多人體聚合、低 fps 內插、標註範圍、來源改寫、有聲退步、樣本相關性、球軌假轉向。私有預測檔 SHA-256：`613d854ed43e097c45539af7513a6d8dd7887d9d79a862955aadbcd61bed42bc`；本機 `prediction.json` 留存建立紀錄。

| 項目 | 事前預測：召回／precision | 實際 |
|---|---|---|
| 60 fps 有聲音 | 88–100%／80–90% | A1 88.00%／88.00%；A2 100.00%／80.95% |
| 60 fps 靜音＋純姿態 | 40–70%／30–60% | A1 28.00%／14.89%；A2 23.53%／9.76% |
| 24／30 fps 有聲音 | 75–90%／55–75% | D24 78.12%／60.98%；D30 88.73%／69.23% |
| 24／30 fps 靜音＋純姿態 | 25–60%／20–50% | D24 15.62%／7.14%；D30 15.49%／9.24% |

有聲音預測落在範圍內；純姿態的召回與 precision 全部低於預測下限。事前研究決策線為**每片召回 ≥70%、precision ≥60%**，這是本輪自行固定的部署門檻，不是 issue 原先指定的數字。四折皆未通過，連 72 組各片樣本內評分也沒有任何一組同時過線。

## 凍結候選與逐片留出

純姿態重用 `events.hands` 的軀幹長度正規化手速、左右腕最短配對及 HIP 跳動遮罩；多軌逐格取最快可信手腕。NaN／非有限手速當 0，先用 1／5／9 格等權移動平均（片端零補），取前後 6 格內的局部最大值，速度門檻 3／6／9 torso/s；按速度降冪抑制 0.6／0.9 秒內的峰，平手較早者優先。最後時間偏移 −6／−3／0／+3 格，超出片段的候選丟棄。共 `3×3×2×4=72` 組，不使用聲音、球軌或標註決定當片峰值。

每折排除一整片，只用另外三片最大化逐片等權 F2（`5TP/(5TP+4FN+FP)`）；同分時取平均 precision 較高者，再按上述平滑寬度→門檻→冷卻→偏移列舉順序。留出 A1／A2／D30 都選到 `(1, 9, 0.6, -3)`；留出 D24 選到 `(1, 9, 0.6, +3)`。每折只用其他三片選參，報告該設定在留出片的分數，不把各片自己的最佳設定當 LOVO 結果。A1／A2 屬同場次，這不是逐場次留出，更不是新資料的獨立保留驗證。

實驗函式先確認**整段原始 PCM 至少有一個取樣、且每個取樣都等於 0**才產生純姿態候選；只要有一個非零取樣，即使聲音候選為空，仍不啟用。此分流僅在私有實驗存在，沒有寫進正式 CLI。5 項先寫的合成自檢涵蓋非零最小正 float32、空音訊、靜止／缺失骨架、去重與偏移、平頂峰／邊界、Wilson 空分母；先確認實驗模組不存在時失敗，再實作通過。

固定額外對照直接使用既有 `events.ball_turns`，沿用 gap、速度變化、局部最大值與近手腕門檻，不調參、不套聲音 lag。它同時需要姿態及球軌，**不是純姿態路徑**，也不是新設計的球轉向方法。

## 原聲、全靜音對照

評分一律使用 `tools/eval_hits.py`：stroke 為目標，touch／unsure 為 ignore，最近距離一對一配對、容許 ±3/60 秒，span 外不計 FP。下表 precision 指 `TP/(TP+FP)`，不是分類 accuracy；括號為 Wilson 95% 區間（百分比，z=1.96）。拍級二項近似未校正同片相關性，不能當成影片級泛化區間。

| 影片 | 候選來源 | TP／FN／FP | 召回（95% 區間） | precision（95% 區間） |
|---|---|---|---|---|
| A1 | 有聲音 | 22／3／3 | 88.00%（70.04–95.83） | 88.00%（70.04–95.83） |
| A1 | 全靜音＋純姿態 LOVO | 7／18／40 | 28.00%（14.28–47.58） | 14.89%（7.41–27.69） |
| A1 | 全靜音＋固定球轉向 | 8／17／28 | 32.00%（17.20–51.59） | 22.22%（11.72–38.09） |
| A2 | 有聲音 | 17／0／4 | 100.00%（81.57–100.00） | 80.95%（60.00–92.33） |
| A2 | 全靜音＋純姿態 LOVO | 4／13／37 | 23.53%（9.55–47.26） | 9.76%（3.86–22.55） |
| A2 | 全靜音＋固定球轉向 | 2／15／4 | 11.76%（3.29–34.34） | 33.33%（9.68–70.00） |
| D24 | 有聲音 | 25／7／16 | 78.12%（61.24–88.98） | 60.98%（45.73–74.34） |
| D24 | 全靜音＋純姿態 LOVO | 5／27／65 | 15.62%（6.86–31.75） | 7.14%（3.09–15.66） |
| D24 | 全靜音＋固定球轉向 | 4／28／58 | 12.50%（4.97–28.07） | 6.45%（2.54–15.45） |
| D30 | 有聲音 | 63／8／28 | 88.73%（79.31–94.18） | 69.23%（59.13–77.77） |
| D30 | 全靜音＋純姿態 LOVO | 11／60／108 | 15.49%（8.88–25.65） | 9.24%（5.24–15.80） |
| D30 | 全靜音＋固定球轉向 | 10／61／79 | 14.08%（7.83–24.02） | 11.24%（6.22–19.46） |

正式 CLI 在五片的全零音訊上都產生 `sounds.shape=(0,4)`、`events.shape=(0,3)`；四片評分召回都是 0%，precision 無定義，不能寫成 100%。上表的靜音＋純姿態及球轉向數字是額外研究候選的評分，並非宣稱正式程式已能處理無聲擊球。

### 接觸時間與假峰

以下為看完主結果後追加的診斷，沒有再選參或更動正式配對容許值。在每個標註前後 15 格內找原始手速最高點，其相對接觸標註的偏移第 10 百分位／中位／第 90 百分位如下：

| 影片 | 峰時間減標註時間（格） |
|---|---|
| A1 | −8.64／−1.80／+8.56 |
| A2 | −8.84／−3.80／+7.48 |
| D24 | −13.42／+0.33／+5.76 |
| D30 | −13.42／−3.42／+10.28 |

這是標註附近的最佳峰位置診斷，並非獨立偵測結果，也不能把寬窗最高點都認定為真揮拍。固定單一時間偏移無法消除這些前後分散；LOVO 靜音候選另有 40／37／65／108 個 FP。未逐一目視核對全部誤報，因此不能把 FP 都歸因於空揮，或宣稱已拆出各類原因。

## 有聲音不變性

從 `origin/main` 擷取 `hits.py`／`events.py`，與本分支正式 CLI 在同一份複製輸入上各重產 sounds、events，以 NPY 檔案位元組相等比較（比 `array_equal` 更嚴格，亦涵蓋 NaN 表示與檔頭）。三支對牆 A 全部相同；兩支開發片亦相同。下表為完整影片候選數，可能包含評分 span 外事件及 ignore，不能直接當作 TP+FP。

| 影片 | sounds 數 | events 數 | main／分支 sounds | main／分支 events |
|---|---:|---:|---|---|
| A0 | 173 | 37 | 逐位元相同 | 逐位元相同 |
| A1 | 185 | 29 | 逐位元相同 | 逐位元相同 |
| A2 | 129 | 22 | 逐位元相同 | 逐位元相同 |
| D24 | 685 | 41 | 逐位元相同 | 逐位元相同 |
| D30 | 740 | 125 | 逐位元相同 | 逐位元相同 |

40 份來源檔（含標註、音訊及既有姿態／附軌）前後 SHA-256 不變。沒有寫回其他 worktree 的 work 或封存。因為未部署新路徑，`prep.py` 既有「這支影片沒有聲音：擊球偵測要靠聲音，這支可能抓不到任何擊球」仍與實際行為一致，無須改提示。

## 重現

需要私有輸入與既有 venv。先把對應資料複製到本 worktree 的 `work/i63-silent-events/{A0,A1,A2,D24,D30}/`；每片保留 `pose.npy`、所有 `pose_t*.npy`、`ball.npy`、`proxy.mp4`、兩份原聲 `audio*.f32`，以及原本存在的 `src_fps.txt`／`pose_method.txt`；A1／A2／D24／D30 的原標註各複製成 `labels.csv`。切勿憑檔名補寫原本缺少的方法或來源 fps 紀錄。下列程式存成私有 `work/i63-silent-events/reproduce.py`，在 repo 根執行：

```sh
.venv/bin/python work/i63-silent-events/reproduce.py work/i63-silent-events
.venv/bin/python tests/test_events.py
.venv/bin/python tests/test_hits.py
```

程式重算的只有聲音候選、手速、既有球轉向及事件，不載入姿態模型；`reproduced.json` 留存四折參數、逐拍預測、計數及區間。這段程式與產生表格的原實驗腳本結果逐欄相同：

```python
import itertools, json, subprocess, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path("tools").resolve()))
import events
from common import size
from eval_hits import read_labels, score

def pose_candidates(hand, raw, params):
    if not len(raw) or np.any(raw != 0): return []
    width, gate, cooldown, offset = params
    if not len(hand): return []
    speed = np.convolve(np.nan_to_num(hand, nan=0., posinf=0., neginf=0.), np.ones(width) / width, 'same')
    peaks = [int(f) for f in np.flatnonzero(speed >= gate)
             if speed[f] == speed[max(0, f - 6):f + 7].max()]
    kept = []
    for f in sorted(peaks, key=lambda f: (-speed[f], f)):
        if all(abs(f - g) > cooldown * 60 for g in kept): kept.append(f)
    return sorted((f + offset) / 60 for f in kept if 0 <= f + offset < len(hand))


def wilson(k, n):
    if not n: return None
    z = 1.96; p = k / n; den = 1 + z*z/n
    centre = (p + z*z/(2*n))/den
    delta = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
    return [max(0., centre-delta), min(1., centre+delta)]


def measured(v, pred):
    tp, fn, fp = score(v['targets'], v['ignore'], pred, spans=v['spans'])
    a, b, c = len(tp), len(fn), len(fp)
    return dict(tp=a, fn=b, fp=c, recall=a/(a+b), precision=a/(a+c) if a+c else None,
                recall_ci=wilson(a, a+b), precision_ci=wilson(a, a+c),
                f2=5*a/(5*a+4*b+c), pred=list(map(float, pred)))


base = Path(sys.argv[1])
grid = list(itertools.product((1, 5, 9), (3, 6, 9), (.6, .9), (-6, -3, 0, 3)))
videos = []
for alias in ("A1", "A2", "D24", "D30"):
    d = base / alias
    for name in ("audio.f32", "audio_hp.f32"):
        raw = np.fromfile(d/name, np.float32)
        assert len(raw) and np.any(raw != 0)
        np.zeros_like(raw).tofile(d/("silent-"+name))
    for prefix in ("", "silent-"):
        subprocess.run([sys.executable, "tools/hits.py", str(d/(prefix+"audio_hp.f32")),
                        str(d/(prefix+"audio.f32")), str(d/(prefix+"repro-sounds.npy"))], check=True)
        subprocess.run([sys.executable, "tools/events.py", str(d/(prefix+"repro-sounds.npy")),
                        str(d/"ball.npy"), str(d/"pose.npy"), str(d/(prefix+"repro-events.npy"))], check=True)
    assert np.load(d/"silent-repro-sounds.npy").shape == (0, 4)
    assert np.load(d/"silent-repro-events.npy").shape == (0, 3)
    labels, spans = read_labels(d/"labels.csv")
    assert spans and all("kind" in row for row in labels)
    v = dict(alias=alias, spans=spans,
             targets=[float(x["t_sec"]) for x in labels if x["kind"] == "stroke"],
             ignore=[float(x["t_sec"]) for x in labels if x["kind"] != "stroke"])
    poses = [np.load(p).astype(float) for p in [d/"pose.npy", *sorted(d.glob("pose_t*.npy"))]]
    w, h = size(d/"proxy.mp4")
    hand = events.hands(poses, w/h)
    ball = np.load(d/"ball.npy"); n = min(len(ball), len(poses[0]))
    wrists = np.concatenate([np.where((p[:n, [15, 16], 2] > .2)[..., None],
                                     p[:n, [15, 16], :2], np.nan) for p in poses], axis=1)
    silent = np.fromfile(d/"silent-audio.f32", np.float32)
    v["baseline"] = measured(v, np.load(d/"repro-events.npy")[:, 0])
    v["turns"] = measured(v, np.array(events.ball_turns(ball[:n], wrists, w/h))/60)
    v["grid"] = [measured(v, pose_candidates(hand, silent, p)) for p in grid]
    videos.append(v)
folds = []
for i, v in enumerate(videos):
    train = [x for j, x in enumerate(videos) if j != i]
    best = max(range(len(grid)), key=lambda k:
               (np.mean([x["grid"][k]["f2"] for x in train]),
                np.mean([x["grid"][k]["precision"] or 0 for x in train]), -k))
    folds.append(dict(alias=v["alias"], params=grid[best], baseline=v["baseline"],
                      silent_pose=v["grid"][best], silent_ball_turns=v["turns"],
                      train=[x["alias"] for x in train]))
(base/"reproduced.json").write_text(json.dumps(folds, indent=2), encoding="utf-8")

```

另以 `git show origin/main:tools/events.py`、`git show origin/main:tools/hits.py` 保存基線腳本到同一私有目錄；執行時令 `PYTHONPATH` 指向 repo 的 `tools`，以相同原聲輸入各跑一次，再 `cmp` main 與本分支的 sounds／events。原實驗的 `manifest.json`、`results.json`、`diagnostics.json`、`prediction.json`、`experiment.log` 及合成自檢只留本機，不提交素材、標註、骨架或影片識別資訊。

## 本機驗證

逐一執行全部 `tests/test_*.py` 與 `tools/test_*.py` 共 24 支全部通過，包含私有資料測試與真模型合成片 prep E2E。另有實驗合成自檢 5 項全過；上列公開重現程式已實跑，四折選參、每筆預測、TP／FN／FP 與 Wilson 區間皆與原實驗 JSON 完全相同。此次僅新增文件，依 repo 規則不觸發三 OS CI，不能把它寫成三 OS 通過。

## 限制與下一步

- 本輪只研究手速峰及既有近腕球轉向，沒有新增揮拍方向分類、接觸模型或球拍定位。兩個失敗方法不能否定其他方法。
- 低 fps 開發片只有兩支；30 fps 開發片是對牆，本輪沒有額外取得 30 fps 對打片。既有四支留出片未使用，不能宣稱對打泛化驗證完成。
- 全片多人聚合手速與固定冷卻可能壓掉其他人的真拍，缺骨架時也無法找回；未重建追蹤，不改相關保護。
- 既有標註未在本輪重新逐拍審核；舊開發資料及同場次資料相關性會讓 LOVO 偏樂觀，結果仍遠低於事前門檻。
- 後續應先建立能定位球拍接觸時間的不同證據，再凍結方法並用新的獨立影片驗證；不將本批失敗結果調到過關後稱為留出成功。
