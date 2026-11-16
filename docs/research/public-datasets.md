# 公開網球資料集：影像授權與側面小樣本

查證日期：2026-11-16（台灣時間）。對應 #70 留言的授權核對與 Tennis Shot 試用；30 fps 留出片只比較取得成本，沒有下載。這份文件不結案 #70 的其他資料補強需求。

## 授權核對

「資料集／程式標示授權」與「轉播影像權利」分開判斷。以下只記錄官方頁能支持的結論；公開下載、論文可讀或程式 MIT，都不能單獨證明影像獲得再授權。

| 候選 | 官方原文與網址 | 影像本身可否用於評估 |
|---|---|---|
| Tennis Shot Side-View and Top-View，第 4 版 | [Mendeley 官方頁](https://data.mendeley.com/datasets/75m8vz7jr2/4)標示 **CC BY 4.0**；頁面內嵌授權說明： “You can share, copy and modify this dataset” | **依發佈者宣告可用**。資料頁描述自行錄製側面與俯瞰、切成單拍影片；授權對象是這份資料集，而不只是程式。資料集 DOI 為 `10.17632/75m8vz7jr2.4`；使用時保留 DOI、版本及[授權連結](https://creativecommons.org/licenses/by/4.0/)，註明縮放與姿態推論等修改；未將原始素材或衍生影像公開。 |
| RacketVision | [GitHub](https://github.com/OrcustD/RacketVision#license)： “This project is released under the MIT License.”；[Hugging Face 原始 dataset card](https://huggingface.co/datasets/linfeng302/RacketVision/raw/main/README.md)：`license: mit` | **轉播影像權利未確認**。HF 的資料集標籤比 repo 程式授權更直接，但[官方論文第 3 節](https://arxiv.org/html/2511.17045v1)說影片取自 YouTube 職業賽事轉播；上述頁面未提供轉播權利人的授權鏈，不能據此宣稱原始影像也已合法改授 MIT。本次不下載。 |
| MUVY | [Zenodo 官方紀錄](https://zenodo.org/records/13883315)可開啟；頁面擷取未顯示授權，改查[同筆官方 API](https://zenodo.org/api/records/13883315)：`"license": {"id": "cc-by-4.0"}`。[官方建置腳本 README](https://github.com/swperfi-project/muvy-dataset-scripts#input-eventscsv)： “Only Creative Commons-licensed videos should be included.” | **資料集宣告 CC BY 4.0，逐支來源影像權利未確認**。Zenodo 說明原始來源是 YouTube 使用者影片；腳本的收錄規則不是每支影片授權查核證據。未下載 7.8 GB 壓縮檔，也未逐支核對網球原片授權。 |
| F3Set | [官方 repo](https://github.com/F3Set/F3Set)根目錄未見 LICENSE；[官方論文第 3.2 節](https://arxiv.org/html/2504.08222v1#S3.SS2)：“We do not redistribute video content, providing only YouTube links”；同節要求 “strictly for academic research”。 | **原始轉播影像授權未確認**。這是作者對研究用途的說明，不是轉播權利人授出的影像授權；論文本身的 CC BY 4.0 也不延伸為比賽影片授權。取得影像仍需個別來源與使用條款核對。本次不下載。 |
| UCF101／TennisSwing | [CRCV 官方頁](https://www.crcv.ucf.edu/data/UCF101.php)：“collected from YouTube”；“If you use this data set, please refer to the following technical report” | **未確認**。官方頁提供下載與引用要求，但本次未找到明確的影像授權條款，尤其未找到先前候選表所寫「僅限研究用途」的授權原文，故不把那個標籤當已確認。本次不下載。 |

F3Set 正確論文是 [F³Set 官方論文（arXiv:2504.08222）](https://arxiv.org/abs/2504.08222)。Tennis Shot 資料頁實際連結的論文 DOI 是 [10.1016/j.dib.2024.110438](https://doi.org/10.1016/j.dib.2024.110438)，與 issue 初查表的尾碼不同。

## Tennis Shot 側面試用

### 抽樣、事前預測與取得證據

固定取四組側面子目錄（室內／室外 × 直線／斜線），每組依官方檔名字典排序取前兩段，共 **8 段**；不下載俯瞰影片或整包，沒有依分析結果換片。官方共 472 段，其中側面 236 段，本次只是便利小樣本，不能估計整份資料的平均表現。

原片留在不進 git 的 `testset/raw/tennis-shot-sideview/`。使用 `curl -q` 直接讀官方公開 API 與個別下載網址，不使用帳號、cookie 或瀏覽器 profile；逐檔比對官方大小與 SHA-256，**8/8 相符**。官方 API 路徑為 `public-api/datasets/75m8vz7jr2/folders/4`，再以 `files?folder_id=<側面目錄>&version=4&$start=0&$limit=1000` 取得每組清單。

`ffprobe -v error -show_streams -show_format -of json <原片>` 實測：8/8 為 **1920×1080、60000/1001 fps（約 59.94）**；長度 1.37–2.35 秒，合計 13.91 秒、39,060,398 bytes；**6/8 無音軌，2/8 有音軌**。這裡不能把「資料集 60 fps」當成恆等的 60.000 fps，也不能假設室內片都有音軌。

在下載與姿態執行前，已於私有 `testset/results/i70-datasets_pred.md` 寫下預測與失敗方式；下載並看過均勻時序圖、仍未跑姿態時補上數字預測：整體姿態偵測率 ≥90%，人工接觸時間附近膝角 3D 與手肘各 ≥6/8 可用，拍種預填 FH ≥6/8，完整流程候選合計 ≤2。主要失敗模式包括無聲、短片邊界、前 48 格不足、遮蔽、持拍手錯誤、授權或下載失敗、heavy 鎖忙及記憶體不足；不為通過預測調閾值。

### 執行與量測口徑

依 `.claude/skills/tennis-analyze/SKILL.md` 執行 `prep.py`，每段獨立 session、追蹤一人；`work/` 中間結果留在本 worktree。開跑須同時滿足 heavy 鎖不存在、`pgrep -fl 'pose_full|prep.py|ball.py'` 無結果、`vm_stat` 的 free+inactive ≥8 GB；`mkdir testset/results/heavy.lock` 成功後寫 owner，一次一段、每段結束釋放鎖。

原片以來源 symlink 提供給獨立的 `videos/<session>/`；取得鎖後逐段執行下列前處理，釋放鎖後再產生候選。持拍手設定僅記原片可確認的右手，反拍單／雙手未知，未據此虛填。

```sh
.venv/bin/python tools/prep.py <session> 1
.venv/bin/python tools/candidates.py <session>
```

姿態偵測率定義為 `pose.npy` 中鼻部 x 非 NaN 的影格數／全部 proxy 影格數；這是 pipeline 有回傳姿態的比例，並非正確人體或角度的準確率。膝角與手肘以人工看原片圈定的接觸附近時間（容許 ±2 個原始影格，屬診斷標記，不是正式逐格真值）呼叫既有 `metrics.measure_full`，分別計算 `knee3d`、`elbow` 非空的拍數／8；手肘指既有 2D 指標，非 3D 精度驗證。拍種使用同一時間點的 `kind.classify` 與 `kind.prefill`，持拍手須先看原片確認；另記標準 `candidates.py` 實際預填數，避免把人工時間的診斷結果當作自動命中。

### 試用結果

8/8 段 `prep.py` 與 `candidates.py` 均以退出碼 0 完成；姿態方法紀錄均為 3，未改任何門檻。以下分母為 proxy 的 834 格或人工接觸診斷的 8 拍。

| 指標 | 事前預測 | 實測 |
|---|---|---|
| 姿態回傳率 | ≥90% | **799/834＝95.8%**；6 段全格有回傳，另 2 段為 122/139、123/141 |
| 膝角 3D 非空率 | ≥6/8 | **8/8＝100%**，但其中 **5/8 有 `knee_warn`**，均為 `view`；無警告且非空僅 3/8 |
| 手肘 2D 非空率 | ≥6/8 | **8/8＝100%** |
| 人工接觸時間的拍種預填 | FH ≥6/8 | **FH 8/8**，信心 0.60–0.99；與原片人工判為 FH 一致，但只有單一拍種，不能代表多類分類準確率 |
| 標準流程擊球候選 | 合計 ≤2 | **0/8 拍產生候選**；sounds、events、candidates 全部為 0；標準流程實際預填 0 筆 |

人工接觸時間往前後各移 1、2 個來源影格，40/40 次診斷的膝角與手肘仍非空。這只檢查回傳可用性，沒有用偏移挑出最佳分類或數字。`pose_jump`、`lr_swap` 在 8 個基準接觸窗均為 false，也不等於已人工證明追蹤完全正確。

數值預測皆達成，但候選「不超過 2」是對聲音依賴的失敗預測，**不是偵測成功**：資料每段一拍，而自動候選覆蓋為 0/8；即使有音軌的 2 段也沒有聲音候選。本資料可在另行人工標接觸時間後測試姿態與拍種，不能直接當目前聲音驅動流程的成功 E2E 案例。膝角雖皆非空，5/8 的視角警告也顯示「側面資料集」名稱不足以保證模型估計的視角可靠；本次沒有角度真值，不能判定警告或角度誰才正確。

## 30 fps 留出片：取得成本比較（未下載）

| 項目 | F3Set | RacketVision |
|---|---|---|
| 現成真值 | 逐格擊球接觸事件，另有左右手與近端／遠端球員資訊；須確認挑到的事件類型與 fps | 球座標、可見度與球拍關鍵點；不是現成逐拍接觸時間，需另外人工標註 |
| 取得步驟 | [官方 data README](https://github.com/F3Set/F3Set/tree/main/data/f3set-tennis)要求依清單從 YouTube 取得 720p 原片、核對幀率並切片／抽格；不可下載時可向作者詢問。帳號／cookie 限制下有失效或被擋風險 | [HF dataset card](https://huggingface.co/datasets/linfeng302/RacketVision/raw/main/README.md)提供靜態原始影片及標註；可先列 tennis/test 清單再選檔，不需採用整套模型訓練環境。匿名個別影片下載本次未實測 |
| 真值整理成本 | 較低，但仍需原始 fps、片段起格、事件 frame 與來源秒數對齊，抽查 ±1–2 格；只挑實際 30 fps 的來源，不能把 25 fps 混稱 30 fps | 較高：逐格人工看球碰拍、補接觸時間及持拍者；原論文採稀疏標註，不能把每格都有球／球拍真值當前提 |
| 權利成本 | 仍需確認轉播原片可用的依據；作者不重新散布影片，論文研究用途說明不等於原片授權 | HF 標 MIT 仍缺轉播權利鏈，亦須先釐清原片用途與條件 |
| 留出污染風險 | 先按完整比賽切開、凍結清單與標註，再測既有低 fps 規則 | 本專案追球已使用 RacketVision 權重；即使對低 fps 擊球門檻而言是新片，仍不能聲稱整個系統從未見過其訓練來源。先核對權重訓練 split，再按比賽留出 |

取得成本的推論：若先取得清楚的原片使用依據且可匿名下載，F3Set 的現成接觸時間較省標註工；RacketVision 的檔案入口較直接，但補標擊球時間較費工。兩者都未通過影像權利確認，現階段不能把任一個寫成可立即使用的 30 fps 留出集；本次不做下載選擇。

## 限制與後續

- 這 8 段是單拍側面片，不涵蓋左右手混合多人、發球或 30 fps；不能用來結案 #70 所列全部缺口。
- 有回傳膝角／手肘不代表讀數準確；沒有關節 3D 真值，無法量角度誤差，也未驗證側面與俯瞰的同步。
- 原始檔、影片識別碼、畫格、骨架與詳細 manifest 均不進 git；公開文件只留資料集名稱、來源入口、方法與彙總。
