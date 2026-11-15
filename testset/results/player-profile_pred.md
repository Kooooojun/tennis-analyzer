# player-profile 事前預測與失敗方式（2026-11-15，寫在改程式之前）

## 設計（預測的前提）

- 設定檔 `work/profiles.json`（不進 git）：`{"white": {"hand": "R", "backhand": "two"}}`。key = 每拍的 `player`（單人場次是 `"me"`）。
- `metrics.py` 的 `_core / measure_full / measure_clip` 多一個 `hand="R"` 參數。左手 = 把 J 裡的 `rs/re/rw` 換成左側關節，並把 `ls/rs` 對調（`_core` 其他地方對 ls/rs 是對稱用法，所以只影響手肘角與擊球手腕）。
- `measure_full` 的 auto_kind：左手時把「手腕相對髖的 x」與「揮拍後 x 位移」乘 −1，等於鏡像後套用原規則。
- 猜慣用手：整支影片兩個手腕（15 / 16）逐格影像速度（只用 visibility ≥ 0.5 的格），取第 98 百分位，大的那隻 = 持拍手。同一玩家跨影片把速度樣本合併再取百分位。
- 沒設定檔的玩家：輸出標「猜的」，提示使用者確認。assemble 把 `hand`、`hand_guess`、`backhand` 寫進每拍；export / refine 一路帶下去。舊資料沒有 `hand` → R。

## 預測

1. (a) 右手回歸：用 `testset/archive/prep-contact` 的 35 拍 clip（`measure_clip` 重算）與 wall-1 的 `pose.npy`（`measure_full` 重算），改前先存快照；改後 hand 不傳（預設 R）與 hand="R" 都 **逐欄位完全相同（差 0）**。
2. (b) 翻轉片：把 wall-1 IMG_8460 proxy 水平翻轉（ffmpeg hflip），重新跑 pose，hand=L 後：
   - `auto_kind` 與原片右手一致 ≥ 90%（排除原片就在邊界的拍）。
   - `knee`、`knee3d` 中位差 ≤ 3°（骨架左右腿對稱，翻轉只帶來姿態估計雜訊）。
   - `contact_h` 中位差 ≤ 0.05、`contact_fwd` 中位差 ≤ 0.1、`prep` 中位差 ≤ 0.05 s、`elbow` 中位差 ≤ 6°、`open_min` 中位差 ≤ 6。
   - 逐拍差會比中位差大（MediaPipe 左右肢本來就不完全對稱，個別拍可差 10° 以上）。
   - 若錯把 hand 設成 R（對照組）：auto_kind 大量互換 FH/BH（預期 ≥ 50% 錯）、elbow／contact_h 明顯偏掉。
3. (c) 猜慣用手：wall-1 的白衣、黑衣各自猜對；翻轉片猜 L。把握度：白衣高（打球多、揮拍大）；黑衣中等（出鏡少、揮拍少，樣本可能不足）。猜完會逐一用畫面核對真實慣用手，而不是假設。
4. 速度第 98 百分位在兩手腕差距 < 15% 時不可信，我會把「差距比」一併輸出；差距太小標「很不確定」。

## 失敗方式（先列，再寫程式）

猜慣用手：
1. 非持拍手（雙反的輔助手、拋球手）在發球／雙反時也很快 → 速度差縮小，雙手反拍者尤其容易誤判。
2. 追蹤在中途換人（multi-player 的 track 換號），兩個人的手腕混在一起 → 結果取決於誰的樣本多。
3. 手腕被遮住（visibility 低）時 MediaPipe 的位置亂跳 → 假的高速度。要用 visibility 閘門，並看第 98 而不是最大值。
4. 影片很短、沒有擊球（portrait-test）→ 樣本太少，應回「無法判斷」而不是亂猜。
5. 走路、撿球時手臂擺動也算速度；比賽影片裡沒揮拍的人可能兩手差不多。
6. 影片被鏡像（自拍鏡頭預設鏡像）→ 骨架 L/R 也跟著翻，猜出來的「慣用手」其實是反的。這是無法從影片判斷的，只能靠使用者設定。要寫進 SKILL.md。

左右手指標：
7. `ls/rs` 對調漏掉某處（例如 `openp` 或 `_front`）→ 左手數字悄悄偏掉。逐一檢查呼叫點。
8. FH/BH 規則在左手鏡像後，原本右手規則裡的非對稱門檻（`side > 0.04` vs `side < -0.02`）會被鏡像成相反的不對稱 → 邊界拍可能互換。翻轉片驗證會看到。
9. `_front` 的方向（`u` 反號）已有左手處理，不重寫；`arm_checks` 已接受 hand，只需把值傳進去。
10. 同一個 session 左右手玩家混在一起：`refine.json` 的 `hand`／`one_hand_bh` 是整場設定，必須改成「以每拍的 player 查設定」，refine.json 的整場設定退為備援。
11. 舊資料（沒有 `hand`、沒有 `player`）→ 必須視為 R、`me`，不能報錯，數字不變。
12. 設定檔被打錯（hand 寫成 "left"、"l"）→ 要報錯，不能默默當 R。
13. 與 multi-player（#9）同時改 `assemble.py`／`export_session.py`：只動最少行，merge 時靠名字對齊。
