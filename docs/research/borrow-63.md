# #63：從手速峰改成接觸事件定位，能借什麼

2026-11-17（台灣時間）。對應 [#63](https://github.com/Kooooojun/tennis-analyzer/issues/63)，基線固定為 `0624a5748d4868d8e16332b882dd69cc12a2c465`，開工已執行 `git merge origin/main`。

**結論：不借這組預設切分規則。** 以我們既有球軌及姿態轉接 YuSak1 的 MIT 純訊號切分器，四折逐片召回為 5.88–21.88%、precision 為 5.26–10.45%，全部未過 70%／60%。相較全靜音 main 的零候選，它找回少量真接觸，也帶來大量誤報；不能稱為達標改善。有聲四片重產的 sounds／events 與固定 main 逐位元相同。這不否定其他時序模型。

## 失敗方式與固定門檻

**失敗方式一句話：手腕最快的時刻不穩定對準球拍接觸，且大量非接觸峰也會觸發；調整單一速度門檻與固定偏移不能同時補召回和刪誤報。** [既有負結果](events-silent.md)的四折召回僅 15.49–28.00%、precision 僅 7.14–14.89%，連樣本內 72 組參數也沒有一組逐片同時過線；[球軌研究](ball-hit-evidence.md)另指出漏拍時球可能根本沒追到，轉向也可能只是巧合。

沿用文件原文門檻：「**每片召回 ≥70%、precision ≥60%**」。issue 的另一條驗收：「**有聲音的影片，輸出和現在逐位元相同。**」不擴大容許時間或改成整段動作辨識。評分沿用 `tools/eval_hits.py` 的最近距離一對一配對、±3/60 秒、既有 span 與 ignore。

只用原研究四支開發片：兩支 60 fps（25、17 拍）、一支 24 fps（32 拍）、一支 30 fps（71 拍），共 145 拍；保留相同四個逐片留出折；本次候選參數集合只有上游預設這一組，每折沒有可選參數，不用當片真值調參。原研究若選參的逐片等權 F2、precision、固定列舉平手規則不變，本次不重跑 72 組峰值搜尋。同場次片段相關性仍存在。文件標為保留或已量過一次的資料均不讀取、不評分。

## 依失敗方式搜尋，而非重做專案總覽

搜尋 `tennis action spotting`、`tennis hit detection`、`T-DEED`，再以 `gh search code` 對準 `GRUPrediction`、`process_prediction` 與接觸吸附位置；搜尋索引沒有回傳吸附函式時，直接讀固定 commit 的本機 clone。三個候選的共同重點是「分辨接觸與隨揮」，而非再調一次峰值門檻。

下表的 LICENSE 均讀過該固定 commit 的原文。程式授權與權重授權分開判定；可公開下載不等於有明示的權重使用條款。表內上游數字均為作者自述，本輪未重現其數字。協調者執行中修訂規則：有內附範例才檢查正常運作，沒有則標「上游未重現」，仍可依預設參數跑我們開發資料；以下試跑依此修訂。

| 候選與固定 SHA | 確實處理這個失敗的原始碼 | 程式與權重 | 對方評測條件、數字及與目標域的差異 | 本輪判定 |
|---|---|---|---|---|
| [YuSak1/tennis-swing-analysis-v3](https://github.com/YuSak1/tennis-swing-analysis-v3/tree/39b5286310c0629e15f5126f0af27f4ce61f43e7)，`39b5286310c0629e15f5126f0af27f4ce61f43e7` | [`segmentation.py:129–176`](https://github.com/YuSak1/tennis-swing-analysis-v3/blob/39b5286310c0629e15f5126f0af27f4ce61f43e7/backend/app/services/segmentation.py#L129)：用近球證據排掉裸轉向，並把已選峰吸附到 ±0.15 秒內球腕距最小格；直接針對「峰在接觸後」 | [LICENSE 原文](https://github.com/YuSak1/tennis-swing-analysis-v3/blob/39b5286310c0629e15f5126f0af27f4ce61f43e7/LICENSE)為 MIT；純訊號切分不需權重。完整重現依賴的 TrackNet 程式與權重沒有在上游明示授權，不能由外層 MIT 推定 | [MILESTONE_1:7–9、43–50](https://github.com/YuSak1/tennis-swing-analysis-v3/blob/39b5286310c0629e15f5126f0af27f4ce61f43e7/backend/MILESTONE_1.md#L7)：單一底線後方 852×480、30 fps、約 10 秒片，6 個切點全落真接觸、零誤切；只在同片調參，未提供 ±0.05 秒逐拍評分或 recall 分母。實際[工作 fps 為 15](https://github.com/YuSak1/tennis-swing-analysis-v3/blob/39b5286310c0629e15f5126f0af27f4ce61f43e7/backend/app/config.py#L18)，不是手機斜側面 60 fps 的驗證 | 優先試跑純訊號版本；上游未重現，轉接我們既有訊號後四折皆未達標 |
| [jhong93/spot（E2E-Spot）](https://github.com/jhong93/spot/tree/edec4201471beed631bed374bd0b95fcdc8a2f4f)，`edec4201471beed631bed374bd0b95fcdc8a2f4f` | [`train_e2e.py:162–217`](https://github.com/jhong93/spot/blob/edec4201471beed631bed374bd0b95fcdc8a2f4f/train_e2e.py#L162)把逐格影像送進短期 GSM 與長期 GRU；[`model/modules.py:22–34`](https://github.com/jhong93/spot/blob/edec4201471beed631bed374bd0b95fcdc8a2f4f/model/modules.py#L22)輸出逐格類別，學習接觸外觀而非假定手速峰就是真值 | [LICENSE 原文](https://github.com/jhong93/spot/blob/edec4201471beed631bed374bd0b95fcdc8a2f4f/LICENSE)為 BSD-3-Clause；[獨立權重庫](https://github.com/jhong93/e2e-spot-models/tree/10d07a4fb01f2eb76785e15552e5648bf0793509)的 README 只有主庫連結、根目錄未見 LICENSE，權重條款未確認，不下載 | [論文 Table 2(e)](https://jhong93.github.io/pdf/spot-eccv22.pdf)：200MF RGB 在 Tennis 的 mAP@1/2 格＝96.1/97.7。網球來自[轉播 1080p、25/30 fps](https://github.com/jhong93/spot/blob/edec4201471beed631bed374bd0b95fcdc8a2f4f/data/tennis/README.md)，不是手機斜側面；另有滑冰等資料，但沒有手機擊球的數字 | 只保留不需球場線的學習機制；排除把轉播權重當成現成解法；授權與官方 CUDA CLI 前置條件未過 |
| [arturxe2/T-DEED](https://github.com/arturxe2/T-DEED/tree/d953b4de8a2ad941c565e1683c5b07255cbe644e)，`d953b4de8a2ad941c565e1683c5b07255cbe644e` | [`model/model.py:131–145`](https://github.com/arturxe2/T-DEED/blob/d953b4de8a2ad941c565e1683c5b07255cbe644e/model/model.py#L131)保留多尺度時序資訊，分別預測事件與位移；[`model/modules.py:406–414`](https://github.com/arturxe2/T-DEED/blob/d953b4de8a2ad941c565e1683c5b07255cbe644e/model/modules.py#L406)把分數搬回 `t-displacement`，直接處理時間偏移 | [LICENSE 原文](https://github.com/arturxe2/T-DEED/blob/d953b4de8a2ad941c565e1683c5b07255cbe644e/LICENSE)為 GPL-3.0；本機私人評估不是因 GPL 被排除。[官方權重下載頁](https://drive.google.com/drive/folders/1sxZalU_hCwL8ITZCU9VqSWE8dB94lJty)只列各資料集目錄，本輪未找到獨立權重條款 | [原論文 Table 1](https://arxiv.org/html/2404.05392v1#S3.T1)：200MF FineDiving mAP@1/2 格＝71.48/87.62；影片為 25–30 fps，跳水／滑冰，與網球接觸不同。原論文沒有 Tennis 成績；後續 repo 有 Tennis 設定，不把其他資料集成績冒充網球成績 | 可借鑑分類＋時間位移的設計；權重授權未確認，官方推論預設 CUDA，未試跑 |

E2E-Spot 與 T-DEED 的網球權重都源自轉播資料，**本輪排除直接套用這些權重**；保留候選的是不要求場線或 homography 的時序定位機制。沒有把依賴完整球場標定的專案列為可試方法。

## 優先候選的上游重現檢查

選 YuSak1 的純訊號切分，是因它直接描述「手速峰落在隨揮、改用局部球腕距定位」，並且切分本身不需要下載權重。讀到的實作與設計摘要還有三個差異：

- [`segmentation.py:146–154、194`](https://github.com/YuSak1/tennis-swing-analysis-v3/blob/39b5286310c0629e15f5126f0af27f4ce61f43e7/backend/app/services/segmentation.py#L146)中，單獨手速峰得 0.5，等於確認門檻，所以程式並不要求每一拍都有球轉向；它仍可能產生與我們相同的假峰。
- [`segmentation.py:81–99`](https://github.com/YuSak1/tennis-swing-analysis-v3/blob/39b5286310c0629e15f5126f0af27f4ce61f43e7/backend/app/services/segmentation.py#L81)只取影像 y 的轉向，有底線後方視角假設；這部分不能直接搬到斜側面。
- 最近距離吸附只重新定位已選候選，沒有恢復被漏掉的球。這是由程式可知的能力邊界，不能據此預告召回一定提高。

**上游未重現：原範例及可重播訊號未發佈。** 固定 commit 的 tracked tree 沒有 `sample_videos/` 影片，也沒有 `.posedet.pkl`／NPY／CSV 訊號。`.gitignore` 最後排除 `sample_videos/`；[`segment_preview.py:57–119`](https://github.com/YuSak1/tennis-swing-analysis-v3/blob/39b5286310c0629e15f5126f0af27f4ce61f43e7/backend/scripts/segment_preview.py#L57)必須讀原片或本機快取。demo `analysis.json` 只有既成分析結果，不是球腕軌跡或接觸真值，不能用「讀出 6 拍」冒充重現。

完整重跑又會載入 [`tracknet.py:4–6`](https://github.com/YuSak1/tennis-swing-analysis-v3/blob/39b5286310c0629e15f5126f0af27f4ce61f43e7/backend/app/services/tracknet.py#L4)註明原樣內嵌的 yastrebksv/TrackNet。其[上游](https://github.com/yastrebksv/TrackNet)根目錄未見 LICENSE，README 只連到權重，不能由本專案 MIT 推定這段第三方程式／權重也有授權；沒有匯入或執行它。本輪只匯入 MIT 的 config、schemas、kinematics、segmentation，直接轉接我們既有球軌，不載入這段 TrackNet。這不是重現上游偵測器，也沒有用我們資料調參。

另兩候選的上游權重條款仍未確認，故沒有下載。官方 CLI 的 [`test_e2e.py:74–79`](https://github.com/jhong93/spot/blob/edec4201471beed631bed374bd0b95fcdc8a2f4f/test_e2e.py#L74)及 [`inference.py:97–107`](https://github.com/arturxe2/T-DEED/blob/d953b4de8a2ad941c565e1683c5b07255cbe644e/inference.py#L97)未覆寫模型的 CUDA 預設；本機檢查 `cuda=False`。這只是原 CLI 的限制，**不是宣稱模型在技術上不能移植 CPU／MPS**；本輪沒有做移植或兩小時安裝嘗試，也沒有把預估安裝困難寫成實際失敗。

## 預設參數試跑與 main

原預測檔內容保留不改；協調者修訂規則後，於新增轉接層及試跑前追加新預測。原段落 SHA-256＝`76331091986c51ce6ed32465dc255a2e831636f71702cfeacf525d467bdead9c`，追加後整檔＝`c72017d6263610e667e773ec90df252b538e8c6b49fe4f58ebb082226d754fa8`。以分隔標題前的位元組重算，原段落雜湊仍相同。

追加預測：逐片召回 10–50%、precision 5–35%，預期不能全過線。實際只有第 3 折召回落在該範圍，其餘召回更低；四片 precision 均落在預測範圍，但全部遠低於 60%。

轉接層只做輸入對齊：60 fps proxy 每四格取樣，保持上游預設 15 fps；姿態及球座標由正規化值轉成各 proxy 的像素，不為某片重縮至作者範例尺寸。球軌沿用 `tools/ball.py` 既有產物，無有效信心者保持 NaN；球拍訊號全 NaN，因沒有既有球拍偵測。不新增球模型或插補。逐軌用上游 `infer_handedness`／`dominant_wrist_track`，再執行原 `SegmentationService`，時間取各軌聯集、只去完全相同的時間，不增設跨軌冷卻。上游預設 0.9 秒間距、0.15 prominence、60 px 近球、0.5 確認及 ±0.15 秒吸附都不變。這只測可缺球拍的訊號規則，不是上游完整偵測 pipeline。

同一批標註、span、ignore 及 ±3/60 秒配對，直接呼叫正式 `eval_hits.score`：

| 留出折 | 拍數／來源 fps | 候選 TP／FN／FP | 候選召回 | 候選 precision | 本輪全靜音 main TP／FN／FP | 過 70%／60% |
|---|---|---|---:|---:|---|---|
| 1 | 25／60 | 2／23／29 | 8.00% | 6.45% | 0／25／0 | 否 |
| 2 | 17／60 | 1／16／18 | 5.88% | 5.26% | 0／17／0 | 否 |
| 3 | 32／24 | 7／25／60 | 21.88% | 10.45% | 0／32／0 | 否 |
| 4 | 71／30 | 5／66／53 | 7.04% | 8.62% | 0／71／0 | 否 |

本輪固定 main 在同四片全零音訊重新產生的 sounds／events 均為空。其召回 0%，precision 分母為零、無定義；CLI 會顯示 0.00%，不能解讀成量到了可比較的 precision。新規則增加召回，同時新增 18–60 個逐片 FP，沒有過門檻，不能以召回高於零就建議借用。

有聲音不變性亦重新實跑：以 `git show 0624a57:tools/{hits,events}.py` 的基線程式及本分支程式，在相同四片原音訊、球軌與姿態上各重產 NPY；四片共八對 sounds／events 檔案 SHA-256 全相同。正式 `tools/`、`tests/` 零 diff。這項證據不表示已部署無聲分支；轉接器僅是研究腳本。

上游沒有原訊號，故無「作者 6 拍」的數值差距；不能把上述四片分數說成對方數字重現。未試其他參數，沒有看完結果再修近球距、取樣相位、拍手或時間偏移。沒有讀取／評分保留資料。

## 可重跑指令與驗證

第三方 clone、依賴及權重隔離規則不變；本題不下載模型，沒有執行 clone 的 setup／install，也未寫入共用 venv 或 models。套件只安裝到 `work/venvs/borrow-events`。先按表內 SHA clone／checkout，確認 LICENSE，再準備只含原四片開發資料的私有目錄，每片保留 `proxy.mp4`、`pose.npy`、附軌、`ball.npy`、`labels.csv`；不把任何輸入提交 git。

```sh
uv venv --python .venv/bin/python work/venvs/borrow-events
uv pip install --python work/venvs/borrow-events/bin/python numpy==2.5.5 scipy==1.18.1 opencv-python==5.0.0.93
work/venvs/borrow-events/bin/python -I docs/research/borrow/test_signal_adapter.py
work/venvs/borrow-events/bin/python -I docs/research/borrow/signal_adapter.py <四片開發資料目錄> work/borrow-events/signal-results.json
.venv/bin/python tests/test_eval_hits.py
.venv/bin/python tests/test_eval_attrib.py
```

合成自檢先寫，首次因缺少轉接器失敗，實作後 4 項全過：座標／時間、NaN／不修改輸入、缺球時仍可執行上游預設及多軌聯集、長度不符拒絕。兩支既有評分器合成測試亦通過。純訊號切分未執行模型推論；重模型仍須 heavy 鎖及至少 8 GiB free+inactive。

審查後新增 float32 像素精度與非有限球座標兩項案例，先在舊轉接器失敗再修正通過，共 6 項通過。NumPy 2.5.5 未重現審查指出的 float32 轉型例外，但舊原地運算會將像素結果寫回 float32；現在先轉 float 再運算，保留像素精度且不改輸入。球座標任一維非有限時，整個球位置設為 NaN。上游整合案例以測試檔位置推算 clone 路徑，從其他目錄執行亦通過；乾淨環境沒有 clone 時會明確列出原因，結果為 5 項通過、1 項跳過，不能稱為全部通過。本次只跑合成驗證，未重跑開發影片或保留資料，研究分數仍為前述試跑結果。

**不借：最近球腕距吸附沒有把這組預設規則變成合格接觸偵測器。** 本輪只否定此轉接版本；時序分類／位移仍未定，需不同接觸證據、新實驗及另建保留集，不能反覆調本批到過線後宣稱泛化。
