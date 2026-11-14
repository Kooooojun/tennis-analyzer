# 開源網球影片分析專案比較

查證日期：2026-11-15。授權、最後 push 日期、star 數由 `gh api repos/<repo>` 查得；其餘欄位來自各 repo README，未逐一實跑的標「未實測」。

| 專案 | 授權 | 最後 push | ★ | 訓練畫面 | 對我們（手機、對牆、多角度）的問題 | 可借用 |
|---|---|---|---|---|---|---|
| [yastrebksv/TrackNet](https://github.com/yastrebksv/TrackNet) | 無 | 2024-03-17 | 259 | 轉播 | 轉播遠景訓練；無授權不能放進 repo | 只能本機評估 |
| [yastrebksv/TennisCourtDetector](https://github.com/yastrebksv/TennisCourtDetector) | 無 | 2024-03-15 | 288 | 轉播 | 要看到完整 14 個場地點；對牆、近拍沒有 | 無 |
| [qaz812345/TrackNetV3](https://github.com/qaz812345/TrackNetV3) | MIT | 2026-09-03 | 329 | 羽球轉播 | 權重是羽球；靠固定背景，手持晃動會差 | 架構、InpaintNet 補斷軌 |
| [OrcustD/RacketVision](https://github.com/OrcustD/RacketVision) | MIT | 2026-04-11 | 100 | 網／羽／桌球，含網球 | 球追蹤同樣假設固定背景 | 球追蹤、球拍 5 點姿勢 |
| [abdullahtarek/tennis_analysis](https://github.com/abdullahtarek/tennis_analysis) | 無 | 2024-08-12 | 910 | 轉播 | 球速、小地圖全靠球場 homography | 無（無授權） |
| [Sh-31/Tennis-Analysis-System](https://github.com/Sh-31/Tennis-Analysis-System) | 無 | 2024-08-06 | 1 | 轉播 | 同上 | 無 |
| [ArtLabss/tennis-tracking](https://github.com/ArtLabss/tennis-tracking) | Unlicense | 2024-02-14 | 724 | 轉播 | README 說只支援正式比賽影片 | 落地點偵測思路 |
| [dentsusoken/tennis-shot-analysis-ai](https://github.com/dentsusoken/tennis-shot-analysis-ai) | 無 | 2023-05-18 | 2 | 手機 | 只能一人入鏡、沒有追球 | 無（無授權） |
| [davidpagnon/Sports2D](https://github.com/davidpagnon/Sports2D) | BSD-3 | 2026-11-12 | 350 | 單鏡頭 | 要求動作平行於鏡頭平面，斜角會失真 | 角度計算、濾波 |
| [perfanalytics/pose2sim](https://github.com/perfanalytics/pose2sim) | BSD-3 | 2026-11-13 | 874 | 多鏡頭 | 需要多支同步、校正過的相機 | 多人關聯、濾波 |
| [yohanshin/WHAM](https://github.com/yohanshin/WHAM) | MIT | 2024-04-18 | 1178 | 單鏡頭 3D | 重、要 GPU（未實測 Mac） | 單鏡頭 3D 人體 |
| [facebookresearch/sam2](https://github.com/facebookresearch/sam2) | Apache-2.0 | 2026-05-30 | 20147 | 通用 | 重（未實測 Mac） | 點一下鎖定某人追整支影片 |

## 結論

- 沒有現成專案能處理「手機、對牆、任意角度、多人」；大多綁轉播畫面與球場線。
- 無授權的 repo（多數網球專用者）只能拿來本機比較，不能把程式或權重放進這個 repo。
- 可放心借用的：RacketVision、TrackNetV3（MIT）、Sports2D、pose2sim（BSD-3）、SAM 2（Apache-2.0）。
- 實測結果見 `testset/results/`（本機、不進 git）與後續 PR。
