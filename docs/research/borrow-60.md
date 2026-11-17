# #60：擊球者歸屬需要穩定身分，不能只強迫輪流

2026-11-17（台灣時間）。對應 [#60](https://github.com/Kooooojun/tennis-analyzer/issues/60)，並讀取已關閉的 [#58](https://github.com/Kooooojun/tennis-analyzer/issues/58)；基線固定為 `0624a5748d4868d8e16332b882dd69cc12a2c465`。

**結論：未定。** SAM 2.1 tiny 在官方範例的 CPU 檢查正常，但 MPS 的長序列輸出異常；CPU 開發推論達 30 分鐘上限停止，尚無完整歸屬分數，不能說比 main 好或不好。強制近遠輪流不借，RacketVision 權重授權未確認。

## 失敗方式與固定門檻

**失敗方式一句話：當一條骨架軌混入不同身分，或真正擊球者的拍手腕缺失時，再用球距重排揮拍幅度，也不能恢復正確的人。** [既有實驗](hitter-attribution.md)在 42 拍調參資料只由 40 對增為 41 對，分段選法仍為 40/42；34 拍外部開發資料原幅度與融合均 13/34。本輪在相同封存輸入重算正式 who_hit，確認仍是 40/42 及 13/34；這不是重跑新版姿態的成績。#58 已關閉也不等於混人與缺失已在本題資料完全消失。

門檻照 issue 原文：「**目標 95%。**」正確率是依逐拍人工身分真值計算的 accuracy，不是球拍 PCK、分割 J&F、交替率或候選總數。只允許原 42 拍調參與 34 拍外部開發資料；兩組分開報，不能靠容易的單軌拍拉高合計來掩蓋外部失敗。**24 拍舊保留集已量過一次，本輪不讀取、不評分；其他已標保留資料亦不碰。** 若有改善，也只能說開發資料比 main 好，正式驗收要另建新保留集。

`tools/attrib.py` 的 `who_hit()` 比較拍手腕前 20／後 4 格的路徑長度，`tools/eval_attrib.py` 共用同一函式。單軌直接選該軌，所以「分割人影更準」與「這一拍選對人」之間仍缺兩步：mask 對應哪條骨架、哪個人真的接觸球。本輪不更動正式呼叫、測試及原資料；研究轉接器只在自己的 work 寫出新的骨架身分排列。

## 三個有針對性的檢查

用 `gh search code 'hitter alternation language:Python'` 尋找對投影球距失敗有負結果的球拍運動程式，再搜尋 SAM 2 的 `obj_id_to_idx` 與 RacketVision 的 `detect_and_estimate_pose`。後兩者雖已在 11/15 總覽出現，這裡只檢查具體的身分記憶與球拍輸出，不重寫一般功能摘要。

| 候選與固定 SHA | 處理失敗的原始碼 | 程式／權重授權 | 對方條件、自述數字及差異 | 本輪判定 |
|---|---|---|---|---|
| [facebookresearch/sam2](https://github.com/facebookresearch/sam2/tree/2b90b9f5ceec907a1c18123530e92e794ad901a4)，`2b90b9f5ceec907a1c18123530e92e794ad901a4` | [`sam2_video_predictor.py:118–143`](https://github.com/facebookresearch/sam2/blob/2b90b9f5ceec907a1c18123530e92e794ad901a4/sam2/sam2_video_predictor.py#L118)保留使用者物件 ID 與各物件獨立輸入／記憶；[`161–210`](https://github.com/facebookresearch/sam2/blob/2b90b9f5ceec907a1c18123530e92e794ad901a4/sam2/sam2_video_predictor.py#L161)接收點／框；[`545–630`](https://github.com/facebookresearch/sam2/blob/2b90b9f5ceec907a1c18123530e92e794ad901a4/sam2/sam2_video_predictor.py#L545)逐格輸出同一組 ID。這是候選身分錨點，不能保證不漂移 | [LICENSE 原文](https://github.com/facebookresearch/sam2/blob/2b90b9f5ceec907a1c18123530e92e794ad901a4/LICENSE)為 Apache-2.0；[官方 tiny model card](https://huggingface.co/facebook/sam2.1-hiera-tiny/blob/main/README.md)明列 `license: apache-2.0`，[repo README](https://github.com/facebookresearch/sam2/blob/2b90b9f5ceec907a1c18123530e92e794ad901a4/README.md#L196)另明示 checkpoints 同授權 | [官方表](https://github.com/facebookresearch/sam2/blob/2b90b9f5ceec907a1c18123530e92e794ad901a4/README.md#L162)：SAM 2.1 tiny 的 SA-V test J&F＝76.5、速度 91.2 fps；是一般影片分割，不是擊球者正確率。SA-V 影片 24 fps、標註 6 fps，物件不限人或球拍；與手機練習、斜側面、60 fps 歸屬任務不同 | 優先試跑；官方範例 CPU 遮罩檢查正常，MPS 僅 4/200 格非空；開發 CPU 試跑達 30 分鐘停止，未產生完整歸屬分數 |
| [OrcustD/RacketVision](https://github.com/OrcustD/RacketVision/tree/c44af2a08524d3cb54d818f19686f4cdea4d2793)，`c44af2a08524d3cb54d818f19686f4cdea4d2793` | [`RacketPose/tools/inference.py:66–108`](https://github.com/OrcustD/RacketVision/blob/c44af2a08524d3cb54d818f19686f4cdea4d2793/source/RacketPose/tools/inference.py#L66)逐個球拍框輸出 5 點與信心；[`rtmpose_m_racket.py:13–29`](https://github.com/OrcustD/RacketVision/blob/c44af2a08524d3cb54d818f19686f4cdea4d2793/source/RacketPose/configs/pose/rtmpose_m_racket.py#L13)定義 handle 等點。可提供比手腕更接近碰球位置的證據，但**沒有**穩定球員 ID 或 who-hit 分類器 | [LICENSE 原文](https://github.com/OrcustD/RacketVision/blob/c44af2a08524d3cb54d818f19686f4cdea4d2793/LICENSE)為 MIT；[資料集卡](https://huggingface.co/datasets/linfeng302/RacketVision/blob/main/README.md)也標 MIT；[獨立權重庫](https://huggingface.co/linfeng302/RacketVision-Models/tree/a3760773233a0988c9605259743fbdd87c59d3a3)無 README／LICENSE／cardData，**權重授權未確認**，不能把資料集 MIT 延伸成權重 MIT | [論文 Table 4、5](https://arxiv.org/html/2511.17045v1#Sx5.T4)：多運動 RTMPose 的網球 PCK@0.2＝89.6%、handle PCK＝92.6%、偵測 mAP@50＝79.4。資料來自專業轉播，論文未在所查章節給固定來源 fps／每片人數；不猜成 60 fps 或固定人數。球拍單格推論無場線輸入，但轉播訓練不證明手機泛化 | 未試跑：權重條款未確認；也沒有可直接重現的歸屬 accuracy。排除把轉播權重當成已驗證解法 |
| [jayclim/BadmintonAI](https://github.com/jayclim/BadmintonAI/tree/5c356f05cde0ed90c75316c133e0aba495e5232b)，`5c356f05cde0ed90c75316c133e0aba495e5232b` | [`doubles/strokes.py:3–20`](https://github.com/jayclim/BadmintonAI/blob/5c356f05cde0ed90c75316c133e0aba495e5232b/src/badminton/doubles/strokes.py#L3)明寫近腕距被空中球投影誤導；[`46–107`](https://github.com/jayclim/BadmintonAI/blob/5c356f05cde0ed90c75316c133e0aba495e5232b/src/badminton/doubles/strokes.py#L46)以影像 y 極值判近遠側、同側選最近者、強迫近遠交替 | [LICENSE 原文](https://github.com/jayclim/BadmintonAI/blob/5c356f05cde0ed90c75316c133e0aba495e5232b/LICENSE)為 MIT；這段規則不需權重，但完整 pipeline 的第三方權重不能由外層 MIT 推定；本輪不下載 | 模組註解自述雙打轉播由約 37% 到約 90%「原始交替率」，並明說**沒有雙打逐拍身分真值**。fps 在該模組未明示。其 `build():124` 讀 homography，近遠 y 定義也綁底線轉播視角，不適合無完整場線及任意側拍 | **排除，不借**。交替率不是身分 accuracy；其視角／場地依賴不符本卡，不列為可試方法 |

第三個專案有針對同一種球距失敗的原始碼，故記錄排除理由；它不是繞過「排除綁轉播／homography」條件的試跑候選。對牆或自拋允許同一人連續擊球；漏掉一拍時，強制交替也會把後面整串相位反轉。因此不能照抄其交替規則。這是任務邏輯的反例，不是我們開發資料上的新量測。

## 官方範例：CPU 正常，MPS 異常

協調者修訂了上游驗證規則：不再要求取得整個 SA-V 評測資料集；先跑官方內附範例，檢查正常運作即可，且要明確區分目視檢查與論文數字重現。本輪依修訂試跑，沒有申請 SA-V、提交個資或使用第三方鏡像。上游 76.5 J&F 仍未重現。

程式直接從固定 SHA clone 匯入，不執行它的 setup／install。官方 tiny 權重由公開的 [Meta 下載網址](https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt)下載至 `work/weights/`，SHA-256＝`7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69`。依賴只裝隔離 `work/venvs/borrow-events`，不寫共用 venv／models。

用 repo 內 `notebooks/videos/bedroom` 的 200 格、notebook 第一物件的兩個前景點 `(210,350)`／`(250,220)`，固定 SAM 2.1 tiny 預設模型，不再補提示或調參。兩次均將 video／state offload 至 CPU；CPU 使用 4 執行緒。兩次都出現缺少選用 CUDA `_C` 擴充的 warning，上游因此略過填洞後處理；沒有編譯擴充或把警告當成完整功能正常。

| 裝置 | 格數 | 非空遮罩格數 | 耗時 | 實際檢查 |
|---|---:|---:|---:|---|
| MPS、float32 | 200 | 4 | 91.46 秒 | 初始遮罩存在，第 50 格已空，未能正常持續追蹤 |
| CPU、float32 | 200 | 200 | 194.66 秒 | 第 50、199 格目視追住同一物件，遮罩面積 1,061–44,569 px |

這是「程式正常運作」的數字＋目視檢查，**不是** J&F 或擊球者 accuracy；非空本身也不保證分割正確。MPS 與 CPU 差異尚未定位到特定運算子，不能斷言是 MPS 不支援某個算子或權重損壞。後續開發試跑選 CPU，不用 MPS 的異常輸出評分。

## 自動身分轉接與開發試跑

先以同一份允許的封存姿態、名字與拍手重算 main：42 拍調參 **40/42（95.24%）**，34 拍外部 **13/34（38.24%）**，均與舊報告一致。調參第一段只以 mmap 讀取前 60 秒、複製為 3,600 格；後段保留區間不讀取／不推論。第二段全段與公開多人開發片按原長度。未取得或打開舊保留集標註。

先寫預測與失敗方式，再寫五項合成自檢（首次缺轉接器而失敗、實作後全過），接著執行以下固定轉接；不以擊球真值選提示、修正名字或改門檻：

1. 按時間找第一格：每人的四個軀幹關節有限、信心 ≥0.5、在畫面內，且各軀幹包圍框不交疊。各人軀幹平均點給一個前景提示；SAM ID 與該格既有軌名綁定，不手點。
2. 從此格往前及往後傳播。影像以隨取隨解碼轉接，使用上游相同 RGB／resize／ImageNet 正規化，避免一次預載全片的 1024 平方張量。維持 60 fps 時間軸、模型預設記憶／輸入尺寸，不降低 fps 或跳過事件間隔。
3. 每格計算可見、在畫面內的骨架關節（信心 ≥0.2）落在各物件 mask 的比例，以 Hungarian 最大總重疊作一對一配對。零重疊不補骨架；平手按固定索引，不讀真值。按 SAM ID 重組姿態，再用原 `who_hit` 與 `eval_attrib.read_holdout` 評分。身分錨點若初始舊軌名已錯，仍可能整段名字錯，這項方法不自動知道真實姓名。
4. 單軌保持原姿態。整支每格完成才輸出可評分的 pose；達 30 分鐘、free+inactive <8 GiB 或運算失敗就停止，部分序列不能拿來計算整支 accuracy。每支推論持有 heavy 鎖，一次一支。

**實際停止：CPU 用 1,800.66 秒只完成 1,266／14,404 格（8.79%）**，程式以狀態「未完成」、原因「單支推論達30分鐘，停止」及 exit 1 結束。輸出目錄只有 status.json，沒有可評分的重組姿態，未完整的序列不計分。heavy 鎖已釋放。依任務停止條件結束此候選，不再硬跑另一支多人調參片。

因此，34 拍外部與完整 42 拍的候選 accuracy 均**未量測**。42 拍中的 23 拍單軌部分只原樣輸出，另 19 拍多人部分未進行模型推論；這不是新模型的準確率。CPU 範例正常只證明模型能運作，未證明本機資源可完成此工作量，更沒有證明比 main 好或差。

## 事前預測與結果邊界

原預測段落不改，協調者修訂後於轉接實作與推論前追加新節。原段落 SHA-256＝`76331091986c51ce6ed32465dc255a2e831636f71702cfeacf525d467bdead9c`；追加後整檔＝`c72017d6263610e667e773ec90df252b538e8c6b49fe4f58ebb082226d754fa8`。原段落前綴雜湊仍相同。

| 項目 | 追加預測／固定參考 | 本輪實際 |
|---|---|---|
| 42 拍開發歸屬 | 預測 85–100%；main 40/42 | 候選未量測：多人部分隨候選停止；main 已重算 40/42 |
| 34 拍外部開發歸屬 | 預測 35–75%，預期不達 95%；main 13/34 | 候選未量測：30 分鐘僅處理 8.79% 格；main 已重算 13/34 |
| 官方範例 | 遮罩非空且跟隨物件；可能 MPS／資源失敗 | CPU 檢查通過、MPS 異常，沒有 SA-V 數字重現 |
| RacketVision | 權重條款未確認就不下載 | 未試跑，未下載權重 |
| 舊保留集 | 禁止再次使用 | 未讀取、未評分 |

預測列出的資源失敗實際發生；歸屬分數範圍因未量測無法對照，不能把它填成 0% 或成功。

RacketVision 的權重庫 README URL 回傳 404，固定 Hub revision `a3760773233a0988c9605259743fbdd87c59d3a3` 的 `cardData=null`、檔案只有 `.gitattributes` 與 6 個 checkpoint；因此不能用資料集 MIT 推定權重 MIT。其 CPU 可移植性不是本輪停止原因。

## 可重跑指令

按候選表 SHA clone／checkout SAM 2，檢查 LICENSE 與權重卡；不要執行上游 setup／install。先建立隔離 venv、安裝依賴與下載官方 tiny 權重，再執行合成自檢。影片、姿態、名字與拍手映射只放自己的 `work/`，不提交 git。

```sh
uv venv --python .venv/bin/python work/venvs/borrow-events
uv pip install --python work/venvs/borrow-events/bin/python torch==2.15.0 torchvision==0.29.2 numpy==2.5.5 scipy==1.18.1 pillow==13.0.0 hydra-core==1.3.8 iopath==0.1.10 tqdm==4.70.1 opencv-python==5.0.0.93
work/venvs/borrow-events/bin/python -I docs/research/borrow/test_sam_identity.py
# 先取得 heavy 鎖並確認 free+inactive；每次只跑一支。
work/venvs/borrow-events/bin/python -I docs/research/borrow/sam_identity.py <私有manifest.json> <片段別名> <本work輸出目錄>
.venv/bin/python tests/test_eval_attrib.py
```

官方範例的相同呼叫如下，在 repo 根目錄用隔離 venv 的 `python -I` 執行；亦須先拿 heavy 鎖。將 device 換成 `mps` 可重現本輪裝置對照，不能把異常結果當成成功：

```python
import sys
from pathlib import Path
import numpy as np
import torch
sys.path.insert(0, str(Path('work/repos/sam2').resolve()))
from sam2.build_sam import build_sam2_video_predictor
torch.set_num_threads(4)
p = build_sam2_video_predictor('configs/sam2.1/sam2.1_hiera_t.yaml',
    'work/weights/sam2.1_hiera_tiny.pt', device='cpu')
with torch.inference_mode():
    s = p.init_state('work/repos/sam2/notebooks/videos/bedroom',
        offload_video_to_cpu=True, offload_state_to_cpu=True)
    p.add_new_points_or_box(s, 0, 1, points=np.array([[210,350],[250,220]], np.float32),
        labels=np.ones(2, np.int32))
    areas = [int((m[0,0] > 0).sum()) for _, _, m in p.propagate_in_video(s)]
print(len(areas), sum(a > 0 for a in areas), min(areas), max(areas))
```

manifest 是陣列，每項含 `alias`、`video`（proxy 路徑）、`poses`（軌號→NPY 路徑）、`names`、`hands`、`frames`、`size`；姿態必須先裁成允許開發範圍。腳本不讀真值。成功才以相同原名字／拍手及新姿態構成評分器輸入，使用 `eval_attrib.read_holdout` 驗證允許的 42 拍 CSV，外部 34 拍按原 stroke 真值計算；未完成不得評分。公開 script 只含自寫轉接，第三方原始碼與權重不進 git。

資源守門用 `vm_stat` 與 `SIGALRM`，本研究腳本僅在 macOS 驗證；不宣稱三 OS 可用。上述簡短範例另需操作者監看 8 GiB 與 30 分鐘上限。

**SAM 2／球拍證據仍未定；強制近遠輪流不借。** 只有完整開發資料比 main 好且達 95% 才能建議另開卡量新保留集；目前沒有該項證據。
