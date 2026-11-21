# 網球練習逐拍分析

用手機錄練習，讓 Claude Code 幫你找出每一拍，量膝蓋彎多少、擊球點多高，做成可以逐格看、並排比較的網頁，再剪一支精華影片。

骨架偵測用 MediaPipe，擊球瞬間用擊球聲抓。哪一拍是你、是自拋還是對打、該看哪幾拍，由 Claude 看縮圖判斷。所以這不是一鍵跑完的程式，而是一個 Claude Code skill。

## 需要

- macOS、Linux 或 Windows 10/11（Windows 見下方「Windows」）。
- Python 3.11–3.12（3.13 沒測過）、ffmpeg（macOS：`brew install python@3.12 ffmpeg`；Linux：`apt install python3.12-venv ffmpeg libegl1 libgles2 fonts-noto-cjk`，後兩個是 MediaPipe 要的系統庫，CJK 字型給標註圖用）。
- Claude Code。

## 安裝

```
git clone <這個 repo>
cd tennis-analyzer
python3 setup.py      # 或 ./setup.sh；會自己找 Python 3.12／3.11
```

結尾會印出 venv 的 Python 路徑。之後的指令都寫成 `python tools/run.py <script> ...`：它會用 venv 的 Python 跑（Mac/Linux 是 `.venv/bin/python`，Windows 是 `.venv\Scripts\python.exe`），任何 Python 都能啟動它。

### Windows

在 PowerShell 貼上（一般 Windows，不是 WSL）：

```
winget install Python.Python.3.12
winget install Gyan.FFmpeg
```

裝完**關掉並重開終端機**，讓 PATH 生效。再：

```
cd C:\dev
git clone <這個 repo> tennis-analyzer
cd tennis-analyzer
py -3.12 setup.py
```

- 有 NVIDIA 顯示卡：`py -3.12 setup.py --cuda`（偵測到 `nvidia-smi` 也會自動裝 CUDA 版 torch）。AMD／Intel 顯示卡不支援，走 CPU。CUDA 版 torch 需要夠新的 NVIDIA 驅動；setup 結尾若警告 `cuda False`，先更新驅動（https://www.nvidia.com/drivers），不然會用 CPU。
- 沒有 GPU 時追球很慢：CPU 全片推論約每秒影片 60–70 秒（橫式；直式約 4 倍；只在 CI 機器量過）。目前只追擊球候選附近的批次，耗時依候選密度而變，追球開始前會列出待推論格數與預估時間。
- clone 到短路徑（如 `C:\dev\tennis-analyzer`）；路徑太長時 prep 會先報錯。必要時開啟 Windows 的 LongPathsEnabled。
- 匯入 mediapipe 失敗時：`winget install Microsoft.VCRedist.2015+.x64`。
- 前處理：`python tools/run.py prep.py 2026-11-20`；看結果：`python tools/run.py open web/index.html`。

## 使用

1. 把一次練習的影片放進 `videos/<日期>/`，例如 `videos/2026-11-20/`。一次練習可以有好幾支影片。
2. 在這個資料夾開 Claude Code，說「幫我分析 videos/2026-11-20」。
3. 前處理（影片縮放、姿勢、擊球聲、追球）要的時間比影片長。實測：Apple M 系列、使用者的對牆影片 A 共 308 秒，`time tools/prep.sh 2026-11-20`（Windows PowerShell 可用 `Measure-Command { python tools/run.py prep.py 2026-11-20 }`）在追球仍跑整片的舊版，從空的 work 目錄跑完是 16 分 52 秒（約影片長度的 3.3 倍；CPU 時間約 8.6 分；當時機器同時有很多工作在跑，只測了這一次，僅供參考）。跑完後 Claude 會看縮圖、標註、修正擊球瞬間，最後寫重點。
4. 打開 `web/index.html`（`python tools/run.py open web/index.html`）就能看結果，不需要開 server。首頁依玩家列出所有場次和分數走勢；點進一場後分成總覽、影片、圖表、每一拍、建議五個分頁。

單拍畫面的影片下面只留播放、逐格、停在引拍完成、停在擊球、速度和「顯示 ▾」；骨架、輔助線、手腕軌跡、3D 回放、深淺色收在「顯示 ▾」裡（骨架、輔助線、手腕軌跡會記在這台裝置），快捷鍵說明收在「操作說明」。「顯示 ▾」裡的「3D 回放」會打開一個跟影片同一格的 3D 骨架，可以拖曳旋轉（單鏡頭估計，轉到影片沒拍到的角度會更不準）。打開面板後，正拍的膝蓋比你自己對打時的中位數直 10° 以上時，會多畫一副藍色的「膝蓋調整示意」：腳不動、重心往下壓、大腿小腿長度不變，膝蓋往腳尖那側彎到你對打時的程度；它只調整膝蓋，不是驗證過的正確動作。示意只在面板打開時畫；膝角被閘門擋掉（標「看不準」）的拍不給示意。「停在膝蓋最彎」停在卡片膝角那一格（窗口內膝角最接近卡片數字、第 10 百分位的那格），會畫膝角弧線，數字和卡片相同；弧線只在用面板按鈕、逐格或拖時間軸停下來時畫，用播放鍵暫停不畫。

之後可以直接問：「#12 是幾分幾秒」、「有沒有比較長的來回」、「幫我做精華」。

## 拍攝建議

- 直拍、橫拍都可以；比例偏離 16:9 超過 1% 的影片會等比例縮放後補黑邊。橫拍時人比較小，盡量讓人佔畫面高度一半以上。
- 放在你側面（和你面向大約垂直），固定不動，整個人（含腳）都要在畫面裡。正後方拍的膝蓋角度誤差最大（2D 約 34°、3D 約 22°），正前方 2D 也會讀太直約 20°（`docs/research/multiview-angles.md`）。
- 每次練習盡量放同一個位置。鏡頭高度會改變膝蓋角度的讀數（放地上會比架高看起來直約 15°），只有同機位的場次能直接比數字。
- 2–4 個朋友一起練也可以：每人一條追蹤，Claude 看縮圖確認誰是誰，每一拍記在打的人名下，數據分開算。對牆或近拍的 2 人最準；遠景雙打的遠端球員常抓不到。

## 驗證膝蓋角度：兩支手機同時錄

膝蓋角度用 MediaPipe 的 3D 骨架算。用公開多機位資料集 CalTennis 驗證過（`docs/research/multiview-angles.md`）：3D 比 2D 少了大誤差（p90 23° vs 34°）、沒有 2D 的偏直偏差，但同一拍兩機的 3D 還是可能差到 33°（p95），**不能說不受拍攝角度影響**；側面拍時 2D 反而最準。手肘角度單機 3D 沒有比 2D 準。想用自己的雙機資料再驗證：

1. 兩支手機同解析度、同幀率（1080p、60fps），固定在三腳架，高度約腰到胸，離你 6–8 公尺。關掉自動縮放和防手震裁切。
2. 機位 A 在正面（你朝向鏡頭），機位 B 在側面（和 A 夾 90°，用膠帶標地面確認）。穿深色、和背景對比大的衣服。
3. 兩機都開始錄後，在兩機都看得到、聽得到的地方「擊掌＋喊一聲」，每支影片開頭和結尾各做一次，之後用來對時（誤差 ±1 格，開頭結尾差超過 1 格就線性校正）。
4. 正手至少 20 次，慢速、正常速度都要。
5. 把 A、B 各放一個 session（例如 `videos/dual-A`、`videos/dual-B`），照一般流程分析。同一拍在兩個 session 各有 `knee`（2D）和 `knee3d`（3D）。
6. 比較，並用 `angle.md` 第 7 節的標準（先寫死）：
   - A、B 兩機的 `knee3d` 差：p95 < 10°，而且小於兩機 `knee`（2D）差的 p95，才算 3D 可以當主要指標；否則維持「2D 加視角限制」。
   - 側面機位的 2D 膝角最接近真值，看正面 2D 和兩機 3D 各離它多遠。
   - 看 `knee_warn` 旗標是否真的抓到兩機差很大的那些拍。

## 資料夾

| 路徑 | 內容 | 進 git |
|---|---|---|
| `tools/` | 分析腳本 | ✓ |
| `web/index.html` | 網頁 | ✓ |
| `.claude/skills/tennis-analyze/SKILL.md` | 給 Claude 的流程說明 | ✓ |
| `videos/` | 你的原始影片 | ✗ |
| `work/` | 中間檔（姿勢、縮圖、標註），一場約 1–2 GB | ✗ |
| `web/sessions/` | 你每場的片段和數據 | ✗ |

影片和分析結果都只留在你自己電腦上。想分享網頁，把 `web/` 整個資料夾傳給對方即可。
