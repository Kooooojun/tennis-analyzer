# 借鑑 #68：遠端姿態與單鏡頭 3D 角度

Refs #68

2026-11-17（台灣時間），基線 main `0624a5748d4868d8e16332b882dd69cc12a2c465`、METHOD 4。只研究偵測與角度，不修改正式工具、模型、METHOD 或計分。

**結論：遠端召回不借。RTMO-s 先重現公開 COCO AP，但開發遠端 9/44→6/44，比 main 差；近端與時間過門檻不能抵銷遠端失敗。單鏡頭 3D 也不借本次 VideoPose3D 預設設定：膝 28.81°／50.75°、肘 32.22°／58.92°，比既有裁切 world 差；上游原論文數字未重現。**

## 失敗方式與固定門檻

遠端人物在整張影像縮放後太小，近端有人又使自動模式維持全畫面；現有逐人裁切仍抓不到開發片段的遠端，搜尋小塊與逐人推論占大部分時間。另一方面，「裁切後能找到人」沒有解決單機 world 的深度與左右歧義，3D 角度仍有大誤差。

沿用[遠端負結果](far-pose.md)的門檻原文：

- 遠端比 main 多 ≥10 個百分點，或相對提升 ≥30%。
- 近端不低於 main 減 1 個百分點。
- 同一段總時間 ≤ main 的 1.5 倍。

[3D 原文](crop-world-angles.md)：「膝與肘分別須中位絕對誤差 ≤5°、p90 ≤10°」。原最低證據同時要求每場、每指標至少 30 個事件機位樣本、覆蓋至少 50% 參考合格候選；不能以縮小分母換取漂亮精度。本卡只允許開發資料，不能完成原本兩場（含保留）的驗收。

歷史基準為遠端合計 9/44（20.5%）、近端 48/73（65.8%）；其中問題片段兩候選遠端均 0/14，裁切耗時 2.644 倍。CalTennis 開發裁切膝中位／p90 為 6.41°／18.98°，肘 12.38°／33.19°，後者僅 20 個合格樣本；都不是本輪量測。這些數字來自不同既有研究基線，不能當本輪同機器重新比較的結果。

## 最多三個候選，讀實作而非只看摘要

候選不使用球場線、轉播專用鏡頭假設或 homography。RTMPose／RTMO 共列同一套可執行的 rtmlib 候選家族，本輪選其中單階段 RTMO-s；另外兩個候選專門處理時間上的 2D→3D lifting。

| 候選／固定 commit | 處理失敗的程式位置 | 程式授權、權重另外核對 | 對方數字與評測條件 | 能借的部分與本機決定 |
|---|---|---|---|---|
| [rtmlib](https://github.com/Tau-J/rtmlib/tree/5ea82df885d6f2a66923f1de2d15c799af0ed732)；`5ea82df885d6f2a66923f1de2d15c799af0ed732`，原模型 [MMPose](https://github.com/open-mmlab/mmpose/tree/759b39c13fea6ba094afc1fa932f51dc1b11cbf9)；`759b39c13fea6ba094afc1fa932f51dc1b11cbf9` | [`body.py:119–140`](https://github.com/Tau-J/rtmlib/blob/5ea82df885d6f2a66923f1de2d15c799af0ed732/rtmlib/tools/solution/body.py#L119)：先偵測框再以 RTMPose 估人；[`pose_tracker.py:219–245`](https://github.com/Tau-J/rtmlib/blob/5ea82df885d6f2a66923f1de2d15c799af0ed732/rtmlib/tools/solution/pose_tracker.py#L219)：降低人框重偵測頻率。選試的 [`rtmo.py:26–46`](https://github.com/Tau-J/rtmlib/blob/5ea82df885d6f2a66923f1de2d15c799af0ed732/rtmlib/tools/pose_estimation/rtmo.py#L26)則單次推論所有人，避免逐人裁切成本隨人數增加。 | 已讀兩份固定 SHA 的 [rtmlib LICENSE](https://github.com/Tau-J/rtmlib/blob/5ea82df885d6f2a66923f1de2d15c799af0ed732/LICENSE)、[MMPose LICENSE](https://github.com/open-mmlab/mmpose/blob/759b39c13fea6ba094afc1fa932f51dc1b11cbf9/LICENSE)：Apache-2.0。另讀作者的 [RTMPose 模型卡](https://huggingface.co/Tau-J/RTMPose/blob/cd4d7095f5cfc9cfc4f46289bee91ea4a1e1d9fd/README.md)，明示 `apache-2.0`，公開免帳號；原官方 RTMO-s zip 與該模型庫備份的 SHA256 一致。訓練資料的附加限制仍依 [rtmlib 權重提醒](https://github.com/Tau-J/rtmlib/blob/5ea82df885d6f2a66923f1de2d15c799af0ed732/README.md#L506)，本輪只本機研究、不散布權重。 | [官方表](https://github.com/open-mmlab/mmpose/blob/759b39c13fea6ba094afc1fa932f51dc1b11cbf9/projects/rtmo/README.md#L34)：RTMO-s body7 640²，COCO val2017 AP **68.6**、V100 ONNXRuntime **8.9 ms**；大模型的 74.8 AP／141 FPS 不屬於本輪模型。靜態多人圖片，沒有統一 fps、側面角度、手機或網球小目標子組；body7 是七資料集混合訓練。 | 可在 Mac CPU 用 ONNXRuntime，無須 CUDA。單階段節省偵測器與逐人推論，但 640² 全圖縮放仍可能漏遠端；17 點 2D 不會輸出 world，無法驗收膝／肘 3D。**先試 RTMO-s 的完整公開評測。** |
| [MotionBERT](https://github.com/Walter0807/MotionBERT/tree/705d3a95354db8bdb696b3492e47a3b5537174ff)；`705d3a95354db8bdb696b3492e47a3b5537174ff` | [`lib/model/DSTformer.py:329–358`](https://github.com/Walter0807/MotionBERT/blob/705d3a95354db8bdb696b3492e47a3b5537174ff/lib/model/DSTformer.py#L329)：空間／時間注意力融合後輸出 3D；[`dataset_wild.py:16–83`](https://github.com/Walter0807/MotionBERT/blob/705d3a95354db8bdb696b3492e47a3b5537174ff/lib/data/dataset_wild.py#L16)：Halpe26 轉 H36M17，按人物篩選及分段。可用多幀先驗降低單幀深度不確定性。 | 已讀該 SHA 的 [LICENSE](https://github.com/Walter0807/MotionBERT/blob/705d3a95354db8bdb696b3492e47a3b5537174ff/LICENSE)：Apache-2.0。另查 [Model Zoo 官方 OneDrive 連結](https://github.com/Walter0807/MotionBERT/blob/705d3a95354db8bdb696b3492e47a3b5537174ff/README.md#model-zoo)：免驗證請求回 HTTP 403，未取得下載頁權重授權原文；不從第三方鏡像猜授權。 | 官方表：H36M-SH scratch **39.2 mm**、微調 **37.2 mm MPJPE**；室內動捕 H36M、單一目標人，243 格序列。該表沒有手機 60 fps 或網球角度結果；[文件](https://github.com/Walter0807/MotionBERT/blob/705d3a95354db8bdb696b3492e47a3b5537174ff/docs/pose3d.md#L3)要求 H36M 註冊以使用資料。 | [`infer_wild.py:33–39`](https://github.com/Walter0807/MotionBERT/blob/705d3a95354db8bdb696b3492e47a3b5537174ff/infer_wild.py#L33)有 CPU fallback，不能僅因 README 的 CUDA 安裝範例便宣稱 Mac 不能跑；但未量效能，亦無手機推論證據。**未試跑：權重存取／授權前提與原評測資料未成立。** |
| [VideoPose3D](https://github.com/facebookresearch/VideoPose3D/tree/1afb1ca0f1237776518469876342fc8669d3f6a9)；`1afb1ca0f1237776518469876342fc8669d3f6a9` | [`common/model.py:100–138`](https://github.com/facebookresearch/VideoPose3D/blob/1afb1ca0f1237776518469876342fc8669d3f6a9/common/model.py#L100)：擴張時間卷積、殘差區塊把連續 2D 點升成 3D，模型不依賴球場或完整畫面。 | 已讀該 SHA [LICENSE 原文](https://github.com/facebookresearch/VideoPose3D/blob/1afb1ca0f1237776518469876342fc8669d3f6a9/LICENSE)：CC BY-NC 4.0。權重另由 [README 授權段](https://github.com/facebookresearch/VideoPose3D/blob/1afb1ca0f1237776518469876342fc8669d3f6a9/README.md#license)明示涵蓋 code/models；非商業本機研究可評估，非可任意商用／散布。 | [官方重現段](https://github.com/facebookresearch/VideoPose3D/blob/1afb1ca0f1237776518469876342fc8669d3f6a9/README.md#evaluating-our-pretrained-models)：H36M CPN 偵測、243 格，**46.8 mm**；本次 in-the-wild COCO 權重對應 Mask R-CNN 輸入列 **51.6 mm**，不混用 CPN 數字；HumanEva-I 三動作、27 格，**33.0 mm**。H36M loader 為 [50 fps](https://github.com/facebookresearch/VideoPose3D/blob/1afb1ca0f1237776518469876342fc8669d3f6a9/common/h36m_dataset.py#L211)，室內校正動捕，按人提供 2D，不是手機網球。 | 純時間卷積可 CPU 推論，官方 `run.py` 也僅在 CUDA 可用才搬裝置；本輪有 Mac CPU 實測，沒有手機延遲實測。原 [DATASETS.md:9](https://github.com/facebookresearch/VideoPose3D/blob/1afb1ca0f1237776518469876342fc8669d3f6a9/DATASETS.md#L9)要求 H36M 註冊，舊免註冊預處理連結已失效；HumanEva 的完整轉換另需其原資料與 MATLAB。**選作追加 3D 試跑：原 Human3.6M 數字標為上游未重現，改依官方 in-the-wild 預設 COCO 輸入權重在開發場次評估；不是原 CPN 權重。** |

多幀模型沒有獨立人體偵測器，遠端 2D 若整段缺失，不會自動恢復可靠影像證據；把 MediaPipe 33 點投進 H36M17 也不是免驗證的替換。人體位置的毫米誤差與膝／肘角度沒有固定換算，不能用 37.2 mm 當通過 5°／10°。

## 事前預測與公開重現

事前預測位於不進 Git 的 `testset/results/borrow-pose_pred.md`，SHA256 `b098877ded87338b96ee4d9d685827eee273c9b5ae4b01eaa5ded1f025b8a20e`，寫完未改。先固定 RTMO-s 完整 COCO val2017 5,000 張 AP 期待範圍 65–70，與官方 68.6 差距超過 **1.0 AP** 就停止；不以小子集替代完整公開評測，不靠開發資料調參數。

本輪自寫的[公開評測轉接](borrow/rtmo_coco.py)直接 import 固定 clone 的 RTMO 前處理／推論與 NMS，自己保留 bbox 分數及關節的索引對應，再呼叫標準 `pycocotools.COCOeval`。原評測用 [`score_mode='bbox'`、`nms_mode='none'`](https://github.com/open-mmlab/mmpose/blob/759b39c13fea6ba094afc1fa932f51dc1b11cbf9/configs/body_2d_keypoint/rtmo/body7/rtmo-s_8xb32-600e_body7-640x640.py#L369)，模型 [`score_thr=0.1`、`nms_thr=0.65`](https://github.com/open-mmlab/mmpose/blob/759b39c13fea6ba094afc1fa932f51dc1b11cbf9/configs/body_2d_keypoint/rtmo/body7/rtmo-s_8xb32-600e_body7-640x640.py#L531)；不能拿高階 demo 的 0.7 信心門檻重現 AP，也不能用關節均分代替 bbox 分數。

官方 zip SHA256 `3da7ad88b209f9da8be87ba5c325610639af04de3b5c8a96649b98cd9e2848a2`；ONNX SHA256 `d0703d40d19f3921da51ae725402d5fdae4d2478c7442072d3101bd396f370d8`。前者與模型卡固定 revision 的 `X-Linked-ETag` 一致。推論用隔離 venv、`python -I`、CPU／ONNXRuntime；權重與第三方 clone 僅在 worktree 的 `work/`，未動共用環境與模型目錄。

| 公開重現 | 官方 | 本輪實測 | 差距／判定 |
|---|---:|---:|---|
| COCO val2017 全 5,000 張 AP | 68.6 | **68.3994** | −0.2006 AP；符合事前 ±1.0 AP 重現條件 |
| 處理時間 | V100 單張 8.9 ms | CPU 全集 472.905 秒 | 含模型初始化、解碼、推論及轉接；不含最後寫 JSON／COCOeval；不能把這兩種時間直接當裝置加速比 |
| free+inactive 最低 | 未列 | 17.51 GiB | 未低於 8 GiB；heavy 鎖已釋放 |

產生 17,785 個預測人次，使用完整標準 COCOeval（maxDets=20），未改資料集或選較有利的子集。68.40 AP 落在事前 65–70 預測範圍；不能由 COCO AP 推論本 repo 遠端召回過門檻。

## 開發影片對照的方法

公開重現通過後，才啟動[單片研究入口](borrow/far_clip.py)。沿用遠端研究相同三段 30 秒／30 fps 來源、60 fps proxy、各段人數上限 4／4／2、同一個本機評分函式 `far_pose_lab.score`；每模式每段各一次，逐段持鎖，不用歷史計時替代目前 main。

main 直接執行本卡基線的 `tools/pose_full.py`。RTMO-s 維持公開重現的 640²、0.1 分數門檻及 0.65 NMS，原解析度解碼後才交模型縮放；不依開發結果改參數。每格取 bbox 分數最高的 N 人，將 COCO 17 點映射回同一組 MediaPipe 索引；其他點設 NaN，不捏造缺點或 world。兩者使用同一個 17 點、信心 >0.2 的框中心及單對單距離門檻，遠／近仍以標註中心 `y/1080 <0.35` 分組；無人標註不計分。

RTMO 輸出槽依當格分數排序，**沒有追蹤身分**；沿用 `pose_full.to60` 建立 60 fps 索引，所有既有標註恰落在原 30 fps 格上，沒有以混合身分的內插格評分。這只能比較稀疏標註的找人召回，不是能替換 33 點／world／身份追蹤的完整流程；也沒有驗證 17 點角度精度。計時含初始化、解碼、推論、格式轉換、後處理及姿態檔寫出，不含匯入、事前轉碼、等鎖與事後評分。

研究入口須保留同一份本機 manifest：每個匿名組別各有 main／rtmo 設定，欄位為 `source`、`proxy`、`out`、`n`、`video`；最後一項只供本機找到既有標註，不放公開文件。來源與 proxy 是原遠端研究的凍結片段，`out` 必須位於本卡自己的 `work/`，且尚不存在；`video` 由原研究的本機設定取得，不重新挑片。入口會先核對 `work/rtmo-coco/summary.json` 的重現判定，再啟動開發推論。

```sh
.venv/bin/python -I docs/research/borrow/test_far_clip.py
.venv/bin/python -I docs/research/borrow/far_clip.py \
  <本機manifest.json> A_main main
work/venvs/rtmlib/bin/python -I docs/research/borrow/far_clip.py \
  <本機manifest.json> A_rtmo rtmo
# 完成及釋鎖後，再依序執行 B_main、B_rtmo、C_main、C_rtmo。
```

main 用共用環境中既有 MediaPipe，RTMO 用隔離環境；兩者均由入口的父程序逐五秒監測記憶體。`far_pose_lab.py` 是原研究留在本機的評分／計時工具，沒有複製私人識別或標註進 Git；欠缺這份本機工具與 manifest 時，可重跑合成自檢與公開 COCO，不能宣稱已重跑私人開發比較。

### 開發實測：每段同門檻

36 張既有稀疏標註、117 個有效人次；以下不代表逐格完整真值或追蹤身分精度。

| 匿名片段 | main 遠端 → RTMO | main 近端 → RTMO | main → RTMO 秒 | 時間比 |
|---|---|---|---|---:|
| A | 9/30（30.0%）→6/30（20.0%） | 16/16（100%）→16/16（100%） | 97.202→35.656 | 0.367 |
| B | 0/14（0%）→0/14（0%） | 10/33（30.3%）→20/33（60.6%） | 32.582→43.577 | 1.338 |
| C | 無遠端標註，不計 | 22/24（91.7%）→22/24（91.7%） | 51.988→45.445 | 0.874 |
| 合計 | **9/44（20.5%）→6/44（13.6%）** | **48/73（65.8%）→58/73（79.5%）** | **181.771→124.678** | **0.686** |

三段 main 的召回計數與原研究相同，但時間用本輪重新量測值；每設定只跑一次，背景負載與框架不同，沒有耗時變異估計。RTMO 的近端改善不能推論遠端或 3D 精度改善。

| 固定驗收 | 結果 |
|---|---|
| 遠端多 ≥10 個百分點或相對 ≥30% | **未過**：A −10 個百分點，B 仍 0→0；合計 −6.8 個百分點、相對 −33.3% |
| 近端不低於 main −1 個百分點 | 通過：三段分別 0、+30.3、0 個百分點 |
| 同段總時間 ≤ main 1.5 倍 | 通過：0.367／1.338／0.874 倍 |
| 膝／肘各自中位 ≤5°、p90 ≤10° | **未過**：RTMO 不輸出 3D；追加 VideoPose3D 的膝與肘均未過，見下節 |

六次開發推論均退出 0；free+inactive 最低 19.01 GiB，逐段釋鎖。預測遠端 10–40%、近端 50–80%：合計 13.6%／79.5% 在範圍內，但沒有達成相對 main 的改善；預測總時間 1.0–2.5 倍，實際 0.686 倍，比預測快。原本條件式 3D 預測未執行；依追加規則另寫事前預測並試跑，見下節。

### 結論與界線

**遠端不借此 RTMO-s 640² 設定；3D 不借本次 VideoPose3D 設定。** 單階段在 A 比既有小塊搜尋省時間，但全圖縮放仍未補回 B 的遠端，A 還減少三個標註人次；不依結果加大模型、改分數門檻或新增選片規則。這只否定這次固定設定，不能否定所有 RTMPose／RTMO 模型或偵測框裁切方法。

沒有達成「開發資料比 main 好且過既定門檻」，因此不寫建議借，也不量任何保留場次。單人／使用者影片逐位元回歸未跑；正式程式完全未改，不能把未跑的回歸當通過。日後若另開更高解析偵測框裁切研究，仍需同樣的召回／速度門檻；時間模型的開發比較見下節，未重現原論文毫米精度的限制必須保留。

## 追加：VideoPose3D 單鏡頭時間模型

### 追加規則、授權與上游狀態

原規則要求先重現對方原數字；追加規則允許：官方免帳號範例能跑便檢查正常運作，沒有可直接執行的範例則標「上游未重現」，仍可用官方預設參數／權重作開發比較，不調參。此變更只適用本節，不改原預測與上線門檻。

固定 clone 沒有內附可直接餵入的 2D 數值範例；展示 GIF 並非數值輸入，Human3.6M 原資料需註冊。因此 **51.6 mm 上游未重現，無差距可報**。官方 [INFERENCE.md](https://github.com/facebookresearch/VideoPose3D/blob/1afb1ca0f1237776518469876342fc8669d3f6a9/INFERENCE.md#step-1-setup)指定 `pretrained_h36m_detectron_coco.bin`，輸入 COCO17、輸出 H36M17；採這份官方公開權重，不使用 CPN 格式權重，不換鏡像。README 明示 code/models 的 CC BY-NC，配合 LICENSE 原文，僅非商業本機評估，不散布權重或輸出骨架；方法出處為 [VideoPose3D 論文](https://arxiv.org/abs/1811.11742)。

下載權重 SHA256 `d3219e005b50591f694da5cbaf6849f060d6b2cf895864a779f8a992ac63a232`；`torch.load(weights_only=True)` 安全載入成功，epoch 80，17×2 輸入、17×3 輸出。轉接使用固定 SHA 的模型與 generator 原始碼，沒有執行 setup／install。隔離環境 Python 3.12、torch 2.15.0、numpy 2.5.5、OpenCV 5.0.0.93，可在 Mac CPU 執行；這不證明手機部署成本可接受。

追加預測寫在本機 `testset/results/borrow-pose-3d_pred.md`，SHA256 `a9f477f6e18a1adefa7955aedde2091a9597f960403683fdd17b19c24c6b73e6`，寫完未改。預測膝中位 5–15°／p90 15–35°、肘 10–25°／25–55°，預期均未過門檻；每機推論 30–300 秒，單機 30 分鐘或記憶體低於 8 GiB 停止。

### 相同開發場次與轉接

[轉接程式](borrow/lift_clip.py)只讀原裁切研究已揭露的同一場次、同兩機 120 秒、既有裁切 2D 與凍結參考事件；沒有重算 MediaPipe、改同步、參考拒判、事件、手別或窗口。原參考 52 個事件機位候選，膝合格 49、肘 20；不以模型成功輸出的子集另定分母。

- MediaPipe 33 點選出 COCO17，依既有 `proxy.map_pose` 還原來源像素，再按官方 `common/camera.py:14–18` 的寬度／長寬比正規化。推論輸入只有同機 2D，沒有校正、多機參考或角度真值。
- 模型沿官方 in-the-wild 設定：`3,3,3,3,3`、243 格、1024 channels、非 causal、eval、預設左右 test-time augmentation；沿官方 `common/generators.py` 和 `run.py:674–682` 反翻輸出再取平均。這種 TTA 不等於 #61 的左右錯標修復。
- 保持原 60 fps，不為開發結果改時序或調參；官方訓練為 50 fps、室內 CPN／Detectron 2D，與本輪 MediaPipe 網球 2D 有分布差異。每 256 格分段，保留左右各 121 格上下文，只有整段首尾使用 edge padding；不在段內重設時間窗口。
- 缺 2D 沿官方 custom preprocessing 的逐點線性內插及端點延伸；評分仍拒判原始 COCO17 有缺值或原髖中心未配對的格，不把填值視為觀測。H36M 只映回必要肩／肘／腕／髖／膝／踝，其餘為 NaN；沒有左右校正、對參考擬合或 Procrustes。
- 沿用 `ct_world.window_angle`：膝在事件前 −48…−6 格的雙膝較小角取 p10，至少 35 格；肘在 −2…+2 格取指定側中位，至少 4 格。使用原參考合格事件與拒判，沒有以新模型輸出重選事件。

啟動時曾因 repo 與上游同名 `common` 模組衝突，在推論前失敗；已改為以固定檔案路徑載入上游 model／generator，保留失敗 log 並用新輸出目錄重跑，未改權重或推論設定。成功兩機分別 7,191／7,197 格、保留原配對觀測 6,851／6,850 格；必要 12 點輸出有限、非零骨長，第一機股骨長度 0.164–0.472 m。這是數值完整性檢查，不能替代上游精度重現。

### 開發角度對照與預測

從同一份凍結事件列重新彙總既有 main 裁切值，精確回到原報告數字；main 這欄是既有輸出重算彙總，沒有宣稱本輪重新推論 main。單位為度，兩模式樣本相同。

| 指標 | n／參考合格；覆蓋 | main 裁切中位／p90 | VideoPose3D 中位／p90 | 判定 |
|---|---:|---:|---:|---|
| 膝 | 49／49；100% | 6.41／18.98 | **28.81／50.75** | 比 main 差，未過 5／10 |
| 肘 | 20／20；100% | 12.38／33.19 | **32.22／58.92** | 比 main 差，未過 5／10，且 n<30 |

| 機位 | 膝 n；中位／p90 | 肘 n；中位／p90 |
|---|---:|---:|
| A | 24；36.54／53.94 | 9；52.91／62.76 |
| B | 25；21.29／43.38 | 11；26.23／37.79 |

兩指標都比預測的上界更差，未達採用門檻。每機含載入權重與時間模型推論分別 0.632／0.635 秒；含資料轉接、參考幾何配對與程序管理則 9.658／9.564 秒，最低 free+inactive 20.20 GiB，兩次均退出 0 並釋鎖。**只量既有 2D 之上的 lifting，不含 MediaPipe 找人與 2D 推論，不能把這個耗時拿來宣稱整個流程或手機即時能力。** 推論時間比事前 30–300 秒預測快，但精度失敗。

**結論：不借本次 VideoPose3D 官方 COCO 權重＋MediaPipe 轉接設定。** 這是開發場次負結果；無法區分模型分布、關節定義、60／50 fps、既有 2D 誤差與深度歧義各自造成多少誤差，也不代表 MotionBERT 或所有時間模型都無效。不放寬門檻、不因負結果換參數重試、不碰任何保留場次。

### 可重跑命令

先跑不需私人資料的[合成自檢](borrow/test_lift_clip.py)，涵蓋左右索引、H36M 回映、缺點／整關節缺失、形狀拒絕、分段上下文與輸出格數；先缺實作退出 1，再完成實作，既有及隔離環境均通過。

```sh
.venv/bin/python -I docs/research/borrow/test_lift_clip.py
git clone https://github.com/facebookresearch/VideoPose3D.git work/repos/VideoPose3D
git -C work/repos/VideoPose3D checkout 1afb1ca0f1237776518469876342fc8669d3f6a9
uv venv --python .venv/bin/python work/venvs/videopose3d
uv pip install --python work/venvs/videopose3d/bin/python --only-binary :all: \
  torch==2.15.0 numpy==2.5.5 opencv-python==5.0.0.93
curl -fL https://dl.fbaipublicfiles.com/video-pose-3d/pretrained_h36m_detectron_coco.bin \
  -o work/weights/pretrained_h36m_detectron_coco.bin
```

本機 config 只有 `split: "development"`、`manifest`、`rows` 三欄；後兩者須指向原裁切研究的**開發** manifest 與凍結事件列，不使用保留場次。檔案路徑與事件列留本機，不進 Git。用同一全新輸出目錄依序執行，入口逐機持鎖、監測 8 GiB／30 分鐘停止線；summary 讀凍結列與輸出，沒有模型推論。

```sh
work/venvs/videopose3d/bin/python -I docs/research/borrow/lift_clip.py \
  <本機config.json> work/lift-new 0
# 第一機完成及釋鎖後才執行第二機。
work/venvs/videopose3d/bin/python -I docs/research/borrow/lift_clip.py \
  <本機config.json> work/lift-new 1
work/venvs/videopose3d/bin/python -I docs/research/borrow/lift_clip.py \
  <本機config.json> work/lift-new summary
```

## RTMO 自檢與可重跑方式

先寫合成自檢，缺實作時退出 1，再寫轉接後共用與隔離 venv 均通過。自檢涵蓋 NMS 篩選後索引排序、bbox 分數與關節一致、座標縮放、空輸出不造假人、輸入不可變、非法形狀／非有限值／比例拒絕、5,000 張完整性、ID 唯一與缺圖／路徑越界。所有測試只用合成數字及暫存檔，不需私人素材。

```sh
.venv/bin/python -I docs/research/borrow/test_rtmo_coco.py
git clone https://github.com/Tau-J/rtmlib.git work/repos/rtmlib
git -C work/repos/rtmlib checkout 5ea82df885d6f2a66923f1de2d15c799af0ed732
uv venv --python .venv/bin/python work/venvs/rtmlib
uv pip install --python work/venvs/rtmlib/bin/python --only-binary :all: \
  numpy==2.5.5 opencv-python==5.0.0.93 onnxruntime==1.32.0 \
  pycocotools==2.0.11 tqdm==4.70.1
```

已有 venv 時跳過建立；不執行 clone 的 setup／install。固定版本為 Python 3.12、numpy 2.5.5、OpenCV 5.0.0.93、ONNXRuntime 1.32.0、pycocotools 2.0.11、tqdm 4.70.1。原 COCO 圖片／標註網域的 HTTPS 憑證不符，未關閉驗證，改用同一官方 bucket 的 HTTPS 路徑：

```sh
curl -fL https://s3.amazonaws.com/images.cocodataset.org/zips/val2017.zip \
  -o work/coco/val2017.zip
curl -fL https://s3.amazonaws.com/images.cocodataset.org/annotations/annotations_trainval2017.zip \
  -o work/coco/annotations.zip
curl -fL https://download.openmmlab.com/mmpose/v1/projects/rtmo/onnx_sdk/rtmo-s_8xb32-600e_body7-640x640-dac2bf74_20231211.zip \
  -o work/weights/rtmo-s.zip
```

在本機安全解開 `val2017/`、`annotations/person_keypoints_val2017.json` 與模型 `end2end.onnx` 後執行；輸出目錄須不存在。程式自行檢查既有姿態／追球／prep 程序，取得 heavy 鎖，逐張監測 free+inactive ≥8 GiB，離開時釋鎖；其他工作持鎖時須先等待，不能刪別人的鎖。

```sh
work/venvs/rtmlib/bin/python -I docs/research/borrow/rtmo_coco.py \
  --annotations work/coco/annotations/person_keypoints_val2017.json \
  --images work/coco/val2017 --model work/weights/rtmo-s/end2end.onnx \
  --rtmlib work/repos/rtmlib --out work/rtmo-coco
```

COCO 原圖、逐人預測與逐格骨架不提交，只提交彙總數字。CalTennis 與既有開發影片的保留部分均不納入本輪。RTMO 完成公開重現後才作開發比較；VideoPose3D 依上述追加規則作探索比較，上游未重現的限制另列，不宣稱精度重現。
