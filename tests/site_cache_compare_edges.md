# 比較區同步與端點測試（issue #104）

比較同步改用 `requestAnimationFrame`，避免把 B 的端點恢復綁在 A 的 `requestVideoFrameCallback` 上。保留嚴格 `unpairedMs === 0`；共用 pause handler 與 `loader.visibility` 以同一個 `bAtLoopEnd` 判斷保護背景片尾，單片播放器與影片來源寫入流程沒有修改。

## 根因與可重現案例

在 main `0624a5748d4868d8e16332b882dd69cc12a2c465`，WebKit offset=-60 的 A 會先播放，B 停在片頭等待。原程式在播放期間依賴 A 的媒體格回呼處理共同區入口；若這個回呼延遲，A.currentTime 仍繼續前進，B 卻保持 paused。回呼恢復後的 seek 校正會增加 pauseCalls，這是事後恢復，不能避免先前的單側前進。

帶呼叫 stack 的 129 輪為 0，之後減少端點重複呼叫的追蹤開銷，再跑四實例 200 輪，捕捉到 640.466 ms 與 852.680 ms 的單側前進。640.466 ms 那輪的 A 媒體格回呼中斷 1346 ms，但 10 ms sampler 仍持續執行；兩側 readyState=4、都沒有 seeking，A 播放中而 B 停在片頭。該輪 pauseCalls=6；852.680 ms 那輪 pauseCalls=2，因此額外 pause 只是線索，不能當成發生不同步的必要條件。

先前約 12 ms 的無 trace 樣本仍不能確證為同一原因；這次修正針對已捕捉且可穩定重現的回呼中斷路徑，沒有把它歸為 WebKit 正常誤差。

WebKit 的 `serviceRequestVideoFrameCallbacks` 在沒有 videoFrameMetadata 時會直接返回；媒體格通知與 currentTime 的時間估算是不同路徑，不能用前者是否到達判斷後者是否前進。[HTMLVideoElement 原始碼](https://github.com/WebKit/WebKit/blob/0807569c0b5f24d910008489967f88bc47532619/Source/WebCore/html/HTMLVideoElement.cpp)、[MediaPlayerPrivateRemote 原始碼](https://github.com/WebKit/WebKit/blob/0807569c0b5f24d910008489967f88bc47532619/Source/WebKit/WebProcess/GPU/media/MediaPlayerPrivateRemote.cpp)

## 額外 pause 的來源

在每輪 7.2 秒觀測窗，通常兩次 A.pause 來自兩次原生循環的 A.seeking。常見的額外兩次依序是：

```text
cmpTick 偵測 B 落後超過 1.5 格
  cmpWait → A.pause、B.pause
  設定 B.currentTime
B.seeking
  cmpWait → 再呼叫 A.pause、B.pause（此時已暫停）
B.seeked
  cmpStart → A.play、B.play
```

另一個來源是 canplay／seeked 到達時另一側仍在 seeking，`cmpStart` 的準備條件檢查再次成對暫停。呼叫數不等於 pause 事件數；同一個同步迴圈的兩次 pause 呼叫，也不能保證兩個媒體程序完全同時處理。

## 執行方式

使用現有合成 HTTP fixture，設定可用的 `PLAYWRIGHT_MODULE` 與 `SITE_E2E_URL`。測試自行產生 60 fps、3 秒／1.5 秒合成片，不讀私人影片。

```sh
node tests/site_cache_compare_edges.mjs
env SITE_COMPARE_RUNS=10 SITE_COMPARE_TRACE=compare-traces node tests/site_cache_compare_edges.mjs
env SITE_COMPARE_MUTATION=frame-stall SITE_COMPARE_TRACE=frame-stall-traces node tests/site_cache_compare_edges.mjs
env SITE_COMPARE_MUTATION=unpaired node tests/site_cache_compare_edges.mjs
```

- `SITE_COMPARE_RUNS`：1–100，預設 1；每輪跑 Chromium／WebKit × offset=+30／-60。
- `SITE_COMPARE_TRACE`：選填輸出目錄，記錄 currentTime、paused、seeking、readyState、媒體事件、rVFC metadata 及非零樣本前後讀值；不包含媒體 URL 或影像。追蹤會改變工作量與排程。
- `SITE_COMPARE_MUTATION=frame-stall`：讓 A 在共同區入口前的媒體格回呼延遲 180 ms，原生播放與 sampler 照常執行；修正前 -60 會紅，修正後應通過。它模擬媒體通知停頓，不延遲 requestAnimationFrame 或改產品函式。
- `SITE_COMPARE_MUTATION=unpaired`：停掉 B 恢復與同步校正，保留 A 真實播放；-60 必須持續變紅。+30 可經 seek 路徑重新配對，是這個既有 mutation 的已知限制。

兩種故障注入都只作用於測試 context，沒有修改媒體資產。正常案例另要求循環持續前進、端點停等、不反覆 pause／seek、不留在待播狀態，不能靠兩側都卡住通過。

## 批准後固定副本驗證

- main `d465be6` 與 PR：WebKit offset=-60 各 **53／53** 通過（單實例 25、四實例負載 28），單側前進全為 0。最新 main 的研究文件合併不影響網頁基準。
- main 有十二輪、PR 有一輪 `pauseCalls!=2`；以下列全數兩側呼叫時間差。每次 pause 完成後兩側皆 paused，每次共同區恢復後兩側皆播放，兩側呼叫間沒有 sampler 或媒體事件插入。0–1 ms 是 JS 觀測差，不是媒體程序原子同步保證。

| 版本／批次 | run | pauseCalls | unpairedMs | A→B pause 間隔 ms | 共同區 A→B play 間隔 ms |
|---|---:|---:|---:|---|---|
| main-single | 1 | 4 | 0 | 0, 0, 0, 0 | 0 |
| main-single | 2 | 4 | 0 | 0, 0, 0, 0 | 0 |
| main-single | 4 | 4 | 0 | 0, 0, 0, 0 | 0 |
| main-single | 8 | 4 | 0 | 0, 0, 0, 0 | 0 |
| main-single | 9 | 4 | 0 | 1, 0, 0, 0 | 0 |
| main-single | 12 | 6 | 0 | 0, 0, 0, 0, 0, 0 | 0, 0 |
| main-single | 13 | 4 | 0 | 0, 0, 0, 0 | 1 |
| main-single | 16 | 4 | 0 | 0, 0, 0, 0 | 0 |
| main-single | 18 | 4 | 0 | 0, 0, 0, 0 | 0 |
| main-single | 19 | 4 | 0 | 0, 0, 0, 0 | 0 |
| main-single | 22 | 4 | 0 | 0, 0, 0, 0 | 0 |
| main-single | 23 | 4 | 0 | 0, 0, 1, 0 | 0 |
| pr-load-1 | 1 | 4 | 0 | 0, 0, 0, 0 | 0 |

- `SITE_COMPARE_RUNS=3 SITE_COMPARE_MUTATION=frame-stall`：main 兩引擎 −60 六案精確紅（63.538–72.500 ms）；PR 兩引擎 × 兩 offset × 三輪 **12／12** 綠，單側前進全 0。兩版每個 −60 案的 A.rVFC 在共同區入口均實際中斷 194–203.600 ms，確認注入生效。
- `SITE_COMPARE_MUTATION=unpaired`：PR −60 Chromium／WebKit 仍以「共同可播區間不得單側前進」紅燈，分別 **3772.200／3739.892 ms**；皆保持兩次循環與超過七秒前進。+30 仍可由 seek 重新配對，保留既有限制。
- Chromium continue-policy main／PR 各二十輪串行交錯：main **19／20**、PR **20／20**，無無效樣本。main 第 9 輪直接捕捉 `stopDead(vB)`：A 剛循環、paused=false／want=true；B ended=true／want=true／edgeWait=false。PR 各輪隱藏時 A 實際循環兩次，沒有 stopDead 呼叫。
- 停止 rAF 跨循環：兩版各二十案通過，Chromium／WebKit 各十輪，單側前進全 0；每輪回前景一秒最大誤差皆 <25 ms。中位數取各輪一秒最大值，兩版同一契約，不要求 PR 各引擎最大值小於 main。

| 版本 | 引擎 | 輪數 | 每輪一秒最大誤差的中位數 ms | 最大值 ms | 非零 unpaired 輪數 |
|---|---|---:|---:|---:|---:|
| main | chromium | 10 | 0.550000 | 0.900000 | 0 |
| main | webkit | 10 | 3.669645 | 6.393625 | 0 |
| pr | chromium | 10 | 0.100000 | 0.200000 | 0 |
| pr | webkit | 10 | 8.022905 | 9.539625 | 0 |

本批 WebKit 的 PR 中位數與最大值較高，皆符合原有 25 ms 契約；列為已知量測差異，不推論時鐘讀值分布改善。

- 生命週期：PR **12／12** 通過；main 十二案精確四紅，兩引擎各晚到 playing／載入取樣，另八案綠。播放中切片、使用者暫停與未 ended 的原生政策暫停仍綠，回前景不會自行恢復已取消的意圖。
- `.venv/bin/python tests/test_site_smoke.py`：批准後固定副本本批一次完整退出 0，包含快取 70、round4 22、端點 28、比較端點 4、生命週期 12、回前景 2、重試 4、停滯 75、載入控制器 58、鍵盤 2、UI 52 與 CSS／手機／接觸高度等檢查。
- 額外評分／建議／膝角標示、兩引擎背景載入與 drip 七組全通過。
- 六案背景策略（兩引擎 × continue-policy／natural／native-pause）全部通過。
- 三個比較測試的 `node --check`、`git diff --check` 通過。

## 保留的失敗

修正載入取樣前的二十輪政策 main／PR 都是 **19／20**；PR 當輪 stack 為 `loader.visibility → stopDead → A/B.pause`，B 在原生片尾、尚未標記 edgeWait。pause wrapper 未擷取 stopDead 入參，不把群組暫停後狀態當成直接入參證據；新增真實片尾 capture 次序案例另證實 B 的載入取樣能先清意圖，兩引擎紅、共用判斷後綠。原始失敗 trace 保留，不以最後重跑綠燈掩蓋。

更早完整套件曾在 Chromium backgroundReload 失敗，當輪沒有 trace，不能確證同因。另一輪 WebKit 單片 abortPrefetch 的 signal.aborted=false；未改動的 main／PR 各五輪交錯對照，兩版 WebKit 各 1／5 同樣失敗、Chromium 全過。沒有修改該預載取消流程或放寬斷言。

首輪 main 329 輪追蹤捕捉到 640.466／852.680 ms 非零與一輪結束仍待播；這些歷史證據及各次失敗皆保留在本機調查報告，與最終副本驗收分列。

## 背景循環與回前景

分頁隱藏而 rAF 停送時，A 由原生 loop 繼續播放，B 可由原生片尾停止。B 的舊一圈 ended 可能晚於 A 回片頭才派送，原共用 pause handler 以 A 新一圈的 cmpInRange 判斷，誤走 stopDead 並清掉兩側播放意圖。現在共用 `bAtLoopEnd` 判斷 B ended 且 A 仍有播放意圖，pause handler 標記 edgeWait，不以當下 A 的圈位置否定預期片尾；載入取樣早於 pause 事件、尚無 edgeWait 時，也依同一判斷保留意圖。沒有 ended 的原生政策暫停仍走原本停止路徑。

回前景時，兩側仍有播放意圖便重啟 tick；比較區可見時立即呼叫原有 cmpStart。若需 seek，cmpWait 先停兩側，seeked 再一起恢復，無須等第一個 rAF 才配對。畫面外若停在對齊 barrier，既有 NEAR observer 在捲回可見範圍時再以兩側 want／shown／前景條件呼叫 cmpStart；使用者已暫停時不會自動恢復。

cmpTick 在 hidden 直接停止，避免晚到 playing 在 B 原生片尾 pause 處理前先 seek B、清掉 ended。回前景明確啟動 tick，A 已播放而不再發 playing 時仍有排程。沒有增加 observer 或背景計時器。

`tests/site_cache_compare_visibility.mjs` 使用 3 秒／3.5 秒真實合成片，明確扣住 hidden 期間的 rAF，跨過 A 原生循環，再量回前景一秒內的偏移、單側前進及實際續播。這是控制排程的 continue-policy 模擬，另以既有背景策略測試涵蓋自然隱藏／原生暫停。

```sh
env SITE_REF=d465be6 SITE_VISIBILITY_RUNS=10 node tests/site_cache_compare_visibility.mjs
env SITE_VISIBILITY_RUNS=10 node tests/site_cache_compare_visibility.mjs
node tests/site_cache_compare_lifecycle.mjs
```

生命週期測試播放中點選預設比較並延遲新片回應，要求載入中與完成後都停在 contact−48、沒有誤設 edgeWait。修前殘留 rAF 會把第 62 格改成 0；cmpTick 現在先清掉自己的回呼，再於隱藏／暫停／metadata 未就緒時返回，所有停止入口都受同一檢查保護。另有 A 已暫停與使用者暫停早於片尾事件處理的反例，要求兩側停止、不保留端點等待，下一次點擊可恢復。

另以 A 先循環、B 再真實片尾的媒體時序，將晚到 playing 延到 B 原生 pause 的 capture 階段派送。修前 cmpTick 在 hidden seek B，將 ended 由 true 改成 false，隨後兩側意圖被清掉；修後保留 ended／edgeWait／意圖並能回前景續播。只控制事件順序與播放速率以製造交界，不 mock paused 或 ended。

合併前追加測試的逐輪數字與完整 trace 保存在本機調查報告；正式測試保留原有 1.5 格門檻與零單側前進斷言。

## 已知限制

rAF 或原媒體回呼的間隔大於 1.5 格時，共同區入口仍有輪詢視窗限制；未實測低耗電裝置。低速播放會按顯示更新頻率重繪。frame-stall 在缺少 rVFC 的環境不注入，既有 unpaired mutation 仍用 rVFC；本次紅綠驗證的兩引擎均支援 rVFC，這些限制未擴大修改。
