# 比較區同步與端點測試（issue #104）

比較同步改用 `requestAnimationFrame`，避免把 B 的端點恢復綁在 A 的 `requestVideoFrameCallback` 上。保留嚴格 `unpairedMs === 0`；影片載入控制器與單片播放器沒有修改。

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

## 驗證

- main：帶 stack 追蹤 129 輪，加減少重複追蹤的四實例 200 輪；329 輪中捕捉到上述兩輪非零，另有一輪在播放窗結束時仍待播。
- PR：WebKit offset=-60 單實例 25 輪、四實例各 7 輪，共 53／53 通過，非零 0 次。單實例 run 9、並行實例 0 run 7、實例 1 run 4 的 pauseCalls=4；三輪的四次暫停呼叫間隔皆為 0／0／0／0 ms，恢復間隔皆為 0 ms。這是 JS 呼叫的觀測差，不是 GPU 原子同步保證。
- frame-stall 初次紅綠對照：main 的 Chromium／WebKit -60 分別為 69.500／60.443 ms；PR 四案全為 0。main 與 PR 都量到約 195–199 ms 的 A rVFC 間隔，不能靠沒有施加故障通過。

- frame-stall 重複三輪：main 的兩引擎 -60 六案全紅（59.307–68.000 ms），PR 的兩引擎 × 兩 offset × 三輪共 12／12 通過、皆為 0。
- 修後 unpaired mutation：Chromium／WebKit -60 分別累計 3778.100／3757.550 ms，仍以「共同可播區間不得單側前進」失敗；兩側都卡住不能通過。

- `.venv/bin/python tests/test_site_smoke.py`：完整套件退出碼 0，包含快取回歸 70、round4 22、端點 28、比較端點 4、重試 4、載入停滯 75、載入控制器 58、鍵盤 2、最終 UI 52 案，以及 CSS／導覽／手機／接觸高度等檢查。
- 額外評分／建議、兩引擎背景載入與 drip、六案背景播放策略皆通過。
- 首次與其他瀏覽器測試並行時，WebKit backgroundReload 的續播意圖斷言失敗；該案例 main／PR 單獨跑均通過，完整套件不並行重跑亦通過。保留首輪失敗，未更動斷言。
- `node --check tests/site_cache_compare_edges.mjs`、`git diff --check` 通過。

沒有實體 iPhone 驗證，也沒有宣稱 12 ms 是瀏覽器可接受誤差。比較畫面改由顯示更新排程繪製，低速播放時可能比原本媒體格通知畫得更頻繁；同步仍使用原有偏移與 1.5 格校正門檻。
