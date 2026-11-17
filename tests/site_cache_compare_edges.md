# 比較區同步時序調查（issue #104）

目前 main 無法重現 WebKit 約 12 ms 的樣本，原因尚未判定；保留 `unpairedMs === 0`，沒有調整容許值或比較區配對。以下結果只適用於所列合成情境，不能據此宣稱原問題已修復。

## 環境與事前預測

基準 `f33a6c1ad855f7f94f931826d37090a58e99ec26`；Playwright 1.64.1、Chromium 156.0.8078.4、WebKit 27.2（revision 2370，iPhone 13 模擬設定）。沿用 `site_i93_fixture.mjs` 的合成場次與測試原有的 60 fps、3 秒／1.5 秒合成片，全程沒有使用私人影片。

事前預測是 10 ms 輪詢跨過 pause／seek 或端點轉換，把整段 currentTime 差歸到取樣終點狀態；其次是 rVFC 與 currentTime 來自不同時間來源；另一個必須排除的可能則是真正單側前進。區分方式是同時記下兩側 currentTime、paused、seeking、readyState，以及 timeupdate／seeked／rVFC 的時間和順序，再檢查實際呈現格是否持續分離。

事前列出的失敗方式包括單側暫停、停用配對、固定偏移一格、seek 誤算為前進、端點等待誤判、停止循環、兩側卡住，以及追蹤本身改變時序。缺少異常當下的追蹤，無法選定其中一個原因。

## main 原始 sampler 十輪

只加外層重跑與失敗前 state 保留，未加入瀏覽器事件追蹤；每格為該輪的 unpairedMs，單位 ms。

| 輪次 | Chromium +30 | Chromium −60 | WebKit +30 | WebKit −60 |
|---:|---:|---:|---:|---:|
| 1 | 0 | 0 | 0 | 0 |
| 2 | 0 | 0 | 0 | 0 |
| 3 | 0 | 0 | 0 | 0 |
| 4 | 0 | 0 | 0 | 0 |
| 5 | 0 | 8.1 | 0 | 0 |
| 6 | 0 | 0 | 0 | 0 |
| 7 | 0 | 0 | 0 | 0 |
| 8 | 0 | 0 | 0 | 0 |
| 9 | 0 | 0 | 0 | 0 |
| 10 | 0 | 0 | 0 | 0 |

Chromium 第 5 輪的嚴格斷言確實失敗，訊息為 `共同可播區間不得單側前進`、`8.099999999999996 !== 0`；該輪沒有事件追蹤，不能把它認定為取樣誤差。另一組加入完整追蹤的十輪，各引擎、各 offset 均為 0。

額外 WebKit −60 實驗：低干擾 rVFC 追蹤 30 輪、6 ms／17 ms 忙碌主執行緒 10 輪、18 ms／20 ms 忙碌主執行緒 3 輪、延後 5 ms 啟動以改變取樣相位 10 輪，全部為 0。另以 Chromium 六倍 CPU 節流跑 10 輪，也全部為 0。這些壓力結果不能取代異常樣本的根因證據。

## 四個並行 WebKit 實例

確認 free + inactive 超過 8 GiB 才啟動，不使用 heavy 鎖。四個獨立實例各 13 輪，均在同一 main 基準、offset=−60，每輪仍播放 7.2 秒。以下逐次 unpairedMs 單位為 ms。

| 輪次 | 實例 1 | 實例 2 | 實例 3 | 實例 4 |
|---:|---:|---:|---:|---:|
| 1 | 0 | 0 | 0 | 0 |
| 2 | 0 | 0 | 0 | 0 |
| 3 | 0 | 0 | 0 | 0 |
| 4 | 0 | 0 | 0 | 0 |
| 5 | 0 | 0 | 0 | 0 |
| 6 | 0 | 0 | 0 | 0 |
| 7 | 0 | 0 | 0 | 0 |
| 8 | 0 | 0 | 0 | 0 |
| 9 | 0 | 0 | 0 | 0 |
| 10 | 0 | 0 | 0 | 0 |
| 11 | 0 | 0 | 0 | 0 |
| 12 | 0 | 0 | 0 | 0 |
| 13 | 0 | 0 | 0 | 0 |

52 次全為 0，符合「至少 50 輪負載下仍未重現時，保留斷言並交付診斷與 mutation」的收斂條件；本次 PR 只引用 issue，不關閉它。

## 時間來源的依據

- [WebKit currentTime 修正](https://github.com/WebKit/WebKit/commit/0e4cfc6b8f5fa42166bb9e05a7e4ed227ec91f79)：跨程序播放器估算時間與非同步通知曾造成 currentTime 非單調，並移除 HTMLMediaElement 的重複估算；它沒有給出 12 ms 或一格的通用誤差上限。
- [TimeProgressEstimator](https://github.com/WebKit/WebKit/blob/0807569c0b5f24d910008489967f88bc47532619/Source/WebKit/WebProcess/GPU/media/MediaPlayerPrivateRemote.cpp)：currentTime 依 cachedMediaTime、effectiveRate 與單調時鐘差估算；pause 先凍結估算，再透過 IPC 送出 pause。
- [HTMLMediaElement](https://github.com/WebKit/WebKit/blob/0807569c0b5f24d910008489967f88bc47532619/Source/WebCore/html/HTMLMediaElement.cpp)：currentMediaTime 在 seeking 時回 lastSeekTime，paused 時可回 officialPlaybackPosition；timeupdate 透過事件佇列發送。
- [HTMLVideoElement](https://github.com/WebKit/WebKit/blob/0807569c0b5f24d910008489967f88bc47532619/Source/WebCore/html/HTMLVideoElement.cpp)：rVFC 使用 player.videoFrameMetadata，另行轉換 presentationTime／expectedDisplayTime 的 performance 時間精度。因此 mediaTime 與 currentTime 不是相同讀值。

正常追蹤範例（相對 performance.now，單位 ms；影片時間為秒）：

| 時間 | 事件 | A currentTime | B currentTime | rVFC mediaTime | paused（A／B） |
|---:|---|---:|---:|---:|---|
| 452 | A rVFC | 1.000073 | 0 | 0.966667 | false／true |
| 453 | B play | 1.001220 | 0 | — | false／false |
| 469 | A rVFC | 1.017167 | 0.007764 | 1.000000 | false／false |

這顯示 currentTime 與呈現格時間可以不同，卻不是非零 unpairedMs 當下的證據，也不能支持把嚴格斷言放寬至 16.7 ms。瀏覽器的 currentTime 估算、事件順序或真正不同步，仍須等抓到異常時序才能分辨。

## 重跑、追蹤與 mutation

先設定既有測試所需的 `PLAYWRIGHT_MODULE`、`SITE_E2E_URL`；本機合成 HTTP fixture 可用 `node tests/site_i93_fixture.mjs` 啟動，使用它輸出的 URL。

```sh
env SITE_COMPARE_RUNS=10 SITE_RESULTS=compare-results.json node tests/site_cache_compare_edges.mjs
env SITE_COMPARE_TRACE=compare-traces node tests/site_cache_compare_edges.mjs
env SITE_COMPARE_TRACE=mutant-traces SITE_COMPARE_MUTATION=unpaired node tests/site_cache_compare_edges.mjs
```

重跑次數限 1–100，預設仍為 1；追蹤與 mutation 預設關閉。開追蹤後，每個引擎／offset／輪次產生一份純時間與狀態 JSON，包含 currentTime、timeupdate、seeking、seeked、play、pause、rVFC metadata 與非零樣本的前後讀值；不記錄影片 URL、影像或場次資料。追蹤會增加工作量，可能改變重現機率，因此一般重跑與追蹤分開量測。

mutation 只在測試的瀏覽器 context 裡替換 cmpTick：保留 A 的真實影片播放與渲染回呼，停掉端點處理、B 恢復與同步校正；沒有修改產品檔案。offset=−60 時 B 起初停在片頭，A 進入共同區後繼續播放，必須讓原始的共同區斷言變紅。

| 引擎 | offset | unpairedMs | 結果 |
|---|---:|---:|---|
| chromium | 30 | 0.0000 | 通過 |
| chromium | -60 | 3779.4000 | 預期失敗 |
| webkit | 30 | 0.0000 | 通過 |
| webkit | -60 | 3760.6652 | 預期失敗 |

mutation 命令退出碼為 1，兩引擎的 −60 案例都報 `共同可播區間不得單側前進`，而且依然完成兩次循環、總前進超過 7 秒；不是因為播放器卡住才變紅。+30 未受到這個特定破壞充分影響，仍通過。

## 最終驗證與限制

- `env SITE_COMPARE_RUNS=10 node tests/site_cache_compare_edges.mjs`：Chromium／WebKit 各兩種 offset × 10 輪，40／40 通過，每輪 unpairedMs 都是 0；一般模式未開追蹤。
- 開追蹤的四案 4／4 通過，輸出都包含 currentTime、timeupdate、seeked、rVFC；mutation 四案中兩個 −60 預期失敗。
- `.venv/bin/python tests/test_site_smoke.py`（設定既有本機 fixture 與 Playwright 環境）：完整建站與網頁 E2E 通過，包含 cache regression、round4、edges、compare edges、retry、載入、鍵盤、手機、CSS、導覽、接觸高度與缺值提示。
- 另跑 `site_cache_background.mjs` 的 Chromium／WebKit、`site_cache_drip.mjs`、`site_cache_playing_background.mjs` 六案，以及 `site_score_uncertainty.mjs`、`site_score_count.mjs`、`site_advice_uncertainty.mjs`，全部通過。
- 額外測試先遇到設定問題：headed Chromium 未安裝，後改用既有 Google Chrome；三個評分測試須使用各自內建合成 fixture，不能套無評分的外部 fixture。背景播放先用 3 秒合成片時，continue-policy 因片段自然結束而失敗；改用 10 秒片（0.25 倍速下涵蓋 25 秒測試窗）後六案全過。上述失敗未透過放寬斷言處理。
- `node --check tests/site_cache_compare_edges.mjs` 與 `git diff --check` 通過。

未使用實體 iPhone；原 WebKit 約 12 ms 與本次 Chromium 8.1 ms 的原因仍未判定，issue #104 保持開啟。沒有修改比較區產品程式、媒體資產、資料格式或加入依賴。
