# 借鑑 #61：側面整身左右對調

Refs #61

2026-11-17（台灣時間），基線 main `0624a5748d4868d8e16332b882dd69cc12a2c465`、METHOD 4。

**結論：未定。本輪沒有取得可先重現公開數字、再合法轉用單機的候選，不導入正式流程；沒有新的開發召回數字，更沒有通過 E8。**

## 失敗方式與固定門檻

側面時整身左右標籤一起交換，位置幾乎不動；只找關節跳躍會漏掉，肩線變號也可能是真轉身。既有單機規則四機召回均為 0%；雙端錨點補參考只把可判定率從 27.35% 提高到 27.68%，未達 40% 停止線；沿原雙機幾何與三種同步擾動條件，即使全補對也僅有 35.29% 幾何上限。這些是[既有負結果](pose-lr-side-temporal.md)，不是本輪新量測。

[E8 原文](pose-lr-side-temporal.md)：

> E8 上線門檻保持原定義：未用過的場次每機召回 ≥70%、正常格誤翻 ≤0.5%，拒判格不算正常，真轉身不能強翻；通過後才改正式左右修正與 METHOD，並驗證使用者的對牆影片 A 正常拍不誤翻、指標不退步。

本卡只能用已揭露的 CalTennis 開發場次；即使開發數字過線，也只能說「開發資料上比 main 好」，不能當未用過場次的驗收。拒判格不補成正常格，沒有取得參考或結果時不填零。

## 依失敗方式找程式

以 `gh search code` 搜尋左右交換、反轉誤差與修正函式，讀取官方 clone 原始碼；另核對 PoseFix 論文的 inversion 定義。候選固定於下列 SHA；沒有執行第三方 setup／install，沒有複製第三方程式進本 repo。

| 候選／固定 commit | 真正處理失敗的程式 | 程式與權重授權 | 對方評測與數字 | 與本任務的落差／試跑決定 |
|---|---|---|---|---|
| [PoseFix](https://github.com/mks0601/PoseFix_RELEASE/tree/5556364bb0f43b0743a5fcd820de48f34b3d4360)；`5556364bb0f43b0743a5fcd820de48f34b3d4360` | [`main/gen_batch.py:89–114`](https://github.com/mks0601/PoseFix_RELEASE/blob/5556364bb0f43b0743a5fcd820de48f34b3d4360/main/gen_batch.py#L89) 產生對側關節的 inversion 候選，`:212–237` 注入反轉誤差；[`main/model.py:1–12`](https://github.com/mks0601/PoseFix_RELEASE/blob/5556364bb0f43b0743a5fcd820de48f34b3d4360/main/model.py#L1) 是影像條件化修復網路，使用 `tensorflow.contrib.slim`。影像提供骨架連續性以外的證據。 | 已讀該 SHA 的 [LICENSE 原文](https://github.com/mks0601/PoseFix_RELEASE/blob/5556364bb0f43b0743a5fcd820de48f34b3d4360/LICENSE)：MIT。另讀 [README 的官方權重連結](https://github.com/mks0601/PoseFix_RELEASE/blob/5556364bb0f43b0743a5fcd820de48f34b3d4360/README.md#results)及下載頁；未取得獨立明示的權重授權，不能把程式 MIT 自動延伸到權重。未下載權重。 | [COCO val2017 表](https://github.com/mks0601/PoseFix_RELEASE/blob/5556364bb0f43b0743a5fcd820de48f34b3d4360/README.md#results-on-mscoco-2017-dataset)：HRNet AP 76.3→77.3，test-dev 75.5→76.7。是多人物單張影像 AP，沒有統一 fps、視角或每圖人數；沒有整身對調召回／真轉身誤翻報告。 | 最接近「左右反轉」的單機候選，但訓練是逐關節擾動，不證明能修整身一致交換。官方測試環境為舊 Ubuntu／CUDA／TensorFlow；本機套件探測無相容 TensorFlow 1.15.5 wheel。**未試跑：相容性與權重授權前提未成立。** |
| [Pose2Sim](https://github.com/perfanalytics/pose2sim/tree/c9eaab597c9774817e295e8b87d5c1dbff7d37e3)；`c9eaab597c9774817e295e8b87d5c1dbff7d37e3` | [`Pose2Sim/triangulation.py:492–559`](https://github.com/perfanalytics/pose2sim/blob/c9eaab597c9774817e295e8b87d5c1dbff7d37e3/Pose2Sim/triangulation.py#L492)：重投影誤差太大時枚舉交換部分相機的左右點，再選誤差較低者。不是單純平滑，也不需要球場線或 homography。 | 已讀該 SHA 的 [LICENSE 原文](https://github.com/perfanalytics/pose2sim/blob/c9eaab597c9774817e295e8b87d5c1dbff7d37e3/LICENSE)：BSD-3-Clause。交換／三角化本身無權重；若重跑上游偵測器須另核對其權重，不能由 BSD 推論。 | [README](https://github.com/perfanalytics/pose2sim/blob/c9eaab597c9774817e295e8b87d5c1dbff7d37e3/README.md#L51)自述多機位關節角誤差 2–6°；該摘要沒有此交換分支的獨立召回、fps、固定鏡頭數或逐視角成績，不能當交換分支的數字。 | 需要同步、校正、同人跨機關聯；迴圈要求交換機數小於有效機數的一半，兩機不進交換搜尋。無法只拿手機單機用；原雙機參考也不能靠同類方法自證解剖左右。**未試跑：不符合單機輸入，不能把額外鏡頭當部署條件。** |

兩者都不依賴球場線，但只有 PoseFix 符合單機輸入。沒有因為候選不足而將訓練用水平翻轉、test-time flip averaging 或一般骨架平滑列為「已處理左右錯標」。

### 查過但不列為可試候選

- [Sports2D 固定 SHA `570ff4fa09852d1179efb1a1d12ec462f5fda8aa`](https://github.com/davidpagnon/Sports2D/blob/570ff4fa09852d1179efb1a1d12ec462f5fda8aa/Sports2D/process.py#L2174)：`handle_LR_swap` 雖有設定，但 `LR_unswap` 呼叫在註解中；[README](https://github.com/davidpagnon/Sports2D/blob/570ff4fa09852d1179efb1a1d12ec462f5fda8aa/README.md#L889)仍列未修左右交換。這正是 11/15 看過的專案，本輪只核對這段，不重寫一般介紹。
- [SwapPF 論文](https://www.scitepress.org/Papers/2026/144493/144493.pdf)確實用步態週期與左右對稱性修交換，但本輪未找到作者公開 repo、固定程式 SHA 或可重跑資料。論文只對步態辨識驗證，不能把其表中 85.87→87.76% 身分辨識率當整身交換召回；步行週期先驗也不適合直接套網球轉身。只有論文，未當作程式候選或試跑。

## 事前預測、重現關卡與實際

預測先寫在不進 Git 的 `testset/results/borrow-pose_pred.md`，SHA256 `b098877ded87338b96ee4d9d685827eee273c9b5ae4b01eaa5ded1f025b8a20e`，之後不修改。失敗方式包含反轉持續、真轉身被翻錯、拒判算正常、權重不明、舊套件與跨機輸入不相容。

| 階段 | 事前預測／停止條件 | 實際 |
|---|---|---|
| PoseFix 公開數字 | 先重現 COCO AP 才進開發資料 | 未試跑，無重現 AP，不能報差距；相容套件與權重授權關卡未過 |
| 條件式開發預測 | 若前段成立：四機召回 0–50%、誤翻 0–3%，預期不過 E8 | 未執行，兩項皆無新數字；不是 0% 召回／0% 誤翻 |
| 下一候選 | 單機可執行且有授權 | Pose2Sim 需要多機位，未試跑 |
| 本輪 main 比較 | 同一開發資料、逐機分母、拒判另列 | 未執行；不能寫開發資料上較好或較差 |

實際唯讀安裝探測：

```sh
uv pip install --python work/venvs/rtmlib/bin/python \
  --only-binary :all: --dry-run tensorflow==1.15.5
```

退出碼 1：本機 CPython 3.12 的 ABI 無可用 wheel，索引只有 `cp36m`／`cp37m`。這只證明本機已選環境不能直接安裝；不是宣稱任何 CPU 移植都不可能，也沒有把一個乾跑等同已花兩小時安裝。本輪未移植舊網路或繞過不明的權重授權。

## 可重跑查證

clone 放在各自 worktree 的 `work/repos/`，用下列查詢記錄 SHA，再 `git -C work/repos/<目錄> show <SHA>:<檔案>` 核對表列原文與行號。安裝探測不執行第三方安裝腳本，不改共用環境。

```sh
gh issue view 61 --comments -R Kooooojun/tennis-analyzer
gh search code '"inversion" repo:mks0601/PoseFix_RELEASE' --limit 10
gh search code '"handle_LR_swap" repo:perfanalytics/pose2sim' --limit 10
gh search code '"handle_LR_swap" repo:davidpagnon/Sports2D' --limit 10
gh api 'repos/mks0601/PoseFix_RELEASE/commits?per_page=1' --jq '.[0].sha'
gh api 'repos/perfanalytics/pose2sim/commits?per_page=1' --jq '.[0].sha'
```

上述 API 會回當時最新 SHA；重讀本研究必須使用表內固定 SHA。沒有執行新的私人影片／CalTennis 推論，也沒有讀取保留場次。`tools/eval_lr_swap.py` 仍只能量相鄰肘／腕換邊與跳躍，不能代替整身真值；日後若取得可用候選，須沿用 `ct_lr.label_pose` 的六組全身配對與原三種同步一致拒判，不能只報旗標變少。

後續需要可授權、可重現的影像條件化反轉模型，或獨立左右標註。只有開發資料比 main 好且過既定數值門檻，才有理由另開卡量未用過的場次；本輪沒有這項證據。
