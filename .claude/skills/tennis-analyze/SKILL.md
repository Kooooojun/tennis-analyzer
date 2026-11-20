---
name: tennis-analyze
description: Analyze a tennis practice session from phone videos in videos/<date>/ — find the player's strokes, measure knee bend / contact height per stroke, build the review page and a highlight reel. Use when the user adds new tennis videos, asks to analyze a practice, asks about a stroke number or timestamp, or wants highlights or rallies.
---

# Tennis session analysis

The pipeline is half scripts, half your eyes. Scripts find hit sounds, track up to N bodies with MediaPipe, and measure angles. You decide who each tracked person is, which candidates are real strokes and by whom, whether each was self-fed or in a rally, where contact really is, and what the session means. Do every judgment step by looking at the images. Never label from the numbers alone.

Run everything from the repo root with `python tools/run.py <script> ...` (it runs the script with the venv's Python: `.venv/bin/python` on Mac/Linux, `.venv\Scripts\python.exe` on Windows; works on all three; use `python3` if there is no `python`, as on a stock Mac). If `.venv` is missing, run `python setup.py` (on Windows `py -3.12 setup.py`; add `--cuda` with an NVIDIA GPU).

Write files (labels.txt, profiles.json, findings, players.txt) with the Write tool, never with shell redirection (`>`, `Set-Content`): on Windows those write UTF-16 or ANSI and the scripts stop with an encoding error.
Keep every command on one line: no `$(...)`, no `VAR=1` prefixes, forward slashes in paths, so the same command works in zsh and PowerShell. A session is a folder name under `videos/`, conventionally the date (`2026-11-05`).

Reply to the user in the language they write in. The page and reel text are Traditional Chinese; write findings and reel text in the user's language if it differs.

## 1. Prepare

```
python tools/run.py prep.py <s> [people]
```

`people` 是追蹤人數（預設 2，可用 1–4）。每支影片會在 `work/<s>/<video>/` 產生 proxy、音訊、每人的姿態、擊球聲、球軌（`ball.npy`，RacketVision）及事件（`events.npy`，聲音經任一人的手速確認，再由球軌估計聲音延遲並扣掉；延遲存在 `lag.txt`，log 在 `events.log`）；`videos.json` 固定影片順序。姿態單人約即時，多人約半速。

追球只推論第一輪擊球候選附近的原批次，窗外全 NaN；無候選時不載入或執行模型，仍解碼整片以保留輸出長度。省時幅度隨候選密度而變：研究中 Apple GPU 的對牆片耗時為全片 26.74%，30 fps 開發片為 62.77%（各一次，非通用速度保證，見 [視窗研究](../../../docs/research/ball-windows-continuity.md)）。全片推論參考值：Apple GPU 約每秒影片 2.4 秒；CPU 約 60–70 秒（僅 CI 機器量過）；CUDA 預期約 1–2 秒（未實測），直式約為橫式 4 倍。新版耗時要依候選批次估算；CPU 的 prep 提示會列出待推論格數，實際裝置與平均 ms/frame 見 `ball.log`。在背景執行並告知使用者預估；可中斷續跑。聲音或任一姿態軌更新時會重算球軌；輸入未更新的舊全片球軌仍可沿用。

Portrait and landscape 16:9 video both work (proxy is 540x960 or 960x540; each stroke stores its `size`). 比例偏離 16:9 超過 1% 的來源會等比例縮放後補黑邊並提示；±1% 內沿用舊縮放命令、座標與快取，不寫補邊版本記錄。姿態方法版本不變。超出容許範圍的舊場次重新執行 prep，缺少或不符合目前濾鏡的 proxy_filter.txt 會觸發 proxy、姿態、球軌與事件重算；之後重跑 candidates 產生正確的原片裁切 sheet，再依既有標註核對流程更新下游產物。 Ask for 60 fps video: a source under 50 fps makes prep print a warning (the proxy duplicates frames to 60 fps; pose runs on the source's own frames and is interpolated to 60 fps, which halves wrist speeds compared with older runs on duplicated frames, so speed numbers such as wrist speed and prep time are unvalidated) and the page shows 「來源 30 fps」. Each tracked person gets a track per video (`pose.npy` is track 0, the person seen most; `pose_t1.npy` track 1, and so on). The tracker keeps identities by position and shirt colour. It works well for 2 people near the camera (wall practice). When the full frame finds someone in fewer than 60% of about 60 frames sampled across the video (a far camera, people ~100 px tall on the proxy), pose switches to crops of the original video around each person, found again in overlapping tiles when lost (a new find must show its legs, so a floodlight is not taken for a person; a tracked person whose legs are hidden stays tracked); this is slower per frame. A far player in a video where someone near the camera is seen still gets the full-frame path and is often missed, and people in the same colour can swap tracks. Changing the pose method (`pose_method.txt`) makes prep redo pose.

For sources below 50 fps, hit selection uses sustained wrist speed only when the adjacent `pose_method.txt` contains an integer >=2; missing or invalid method records retain the existing peak-speed rule, as does sound-lag estimation. Evaluate annotated intervals using `# span start end` lines in hit-label CSVs; predictions just outside a boundary may match within the timing tolerance but never count as false positives. Read [the calibration results](../../../docs/research/events-hand-gate.md) for the small, exploratory leave-one-video-out differences and the limitations of the in-sample results before claiming validation across frame rates.

## 1b. Who is who (judgment, only when more than one person was tracked)

The first run of `candidates.py` stops and writes `work/<s>/players.jpg`: one row per tracked person per video (`v<video> t<track>`), 10 crops spread over the video. It also writes `work/<s>/players.txt` with one `<video no> <track> ?` line per row. Ask the user what to call each friend (or use shirt colour, e.g. `white`, `black`), look at the sheet and replace each `?` with a name. Use the same name for the same person in every video, and `x` for a track that is nobody (a passer-by, a ghost skeleton). Names are one word without spaces.

Then ask each named player's racket hand and backhand type and write `work/<s>/profiles.json` (see "Players' hand and backhand" below) before re-running `candidates.py`: it checks each person's racket wrist (a lefty's left wrist) and pre-fills the kind with that hand. If you add a profile later, rename labels.txt to labels.txt.bak (Windows has no `trash`) and re-run it.

To measure who-hit-it attribution (developers): `python tools/run.py eval_attrib.py <s> <labels.csv>` with lines `<video>,<t seconds>,<name>` labelled from the original frames (prints N, accuracy, Wilson lower bound); `eval_attrib.py <s> --check` confirms it picks the same track as `cands.json`. Never tune on the hold-out you measure with.

If one row shows two different people, the tracker swapped them partway. Name the row after the person it shows most; you fix the strokes after the swap one by one in labels.txt (next step).

## 2. Candidates and labels (judgment)

```
python tools/run.py candidates.py <s>
```

This writes one sheet per candidate, `work/<s>/sheet<idx>.jpg` (1500×1000): 12 wide crops of the hitter around the estimated contact (−12, −9, −6, −3, −2, −1, 0, +1, +2, +3, +6, +9 frames at 60 fps, brightened, cut from the original video in `videos/<s>/`), and under them the whole frame at −45, −20 and 0. Frame 0 (red border, labelled `est. contact (sound-lag)`) is the hit sound moved back by this video's sound lag (`work/<s>/<video>/lag.txt`), not the raw sound. Sessions without the original video get crops from `proxy.mp4` and say "proxy resolution only" (the ball is about half as big). `--legacy` (`tools/candidates.py <s> --legacy`) writes the old small sheets (24 candidates each, 5 square crops) instead. Read every sheet, in batches of about 10: read 10 sheets, write those 10 lines into labels.txt, then the next 10 (one sheet per candidate, so 100 candidates are 100 images; a batch keeps what you saw next to what you write). Fill `work/<s>/labels.txt`, one line per idx, in the form `idx kind drill [comment]`:

- **Keep a line only when you see the ball touch the racket** on that sheet: the ball on the strings, or just leaving them with its direction changed (it was coming in, now it goes back out). A hit sound plus a swinging arm is not proof: bounces, a ball dropped from the hand that falls past the racket, a swing while the ball is still in the other hand, shadow swings, the follow-through of the previous hit and picking a ball up all make a candidate. When you cannot see contact, write `x` and the reason as the comment: `x dropped` (ball fell past, untouched), `x in-hand` (ball still in the free hand during the swing), `x shadow` (swing with no ball near), `x follow-through` (end of the previous stroke), `x pickup` (picking up a ball, walking), `x no-swing`. A ball hidden behind the body at contact is not contact: look at the frames after it (+3 … +9) for the ball leaving the racket.
- 複核完整動作後能定位真接觸就用 `refine.json` 的 `off` 修正；已確認擊球卻因畫外或遮擋無法定位接觸格，才在 `set` 標 `contact_untrusted: true` 並重跑 refine 與 score，假擊球仍標 `x`／`drop`。
- A kind already filled in only means the backswing looked like that stroke (`kind_conf` ≥ `PREFILL_MIN` in tools/kind.py). It is **not** evidence that the ball was hit: check contact on every line, prefilled or not. Fill every `?` yourself from its sheet; never replace them in bulk (`sed`, an editor's replace-all). `assemble.py` warns when there are 10 or more lines and under 3% of them are `x` (ignore it if every line really is a hit, e.g. a clean feeding drill).
- With several players each line is prefilled `idx <kind guess or ?> ? @name`: the person whose wrist swung most at that hit sound, named from players.txt. The sheet label shows the same `@name`, the crops follow that person, and the dot on the whole frames marks them. If the crops show a different person than the name says (a tracker swap), change the name. If the crops show someone who is not hitting, use `x`. A partner's shadow swing or ball bounce can look like a stroke while the other player really hit: check the whole frames.
- `kind` is FH, BH, SV (serve), OH (overhead), or `x`. Use `x` also when it is not a player (another person the tracker jumped to) or a duplicate of the stroke just before.
- `drill` is `feed` if the user tossed the ball to themselves (look at the whole frames −45 / −20: the ball is in their hand or a free hand is releasing it), `rally` if it came from the other side, `high` if it was self-fed high, `unsure` if you can't tell. SV takes no drill.
- Solo sessions (people 1, or one person in frame): first ask the user, or work out from the sheets, which person they are. If the tracker follows someone else for a stretch, mark those runs `x other-player`.
- A rally shows a gap of roughly 3–6 s between candidates. A run of feeds shows toss motions. Use the timing to settle doubtful feed / rally calls.

**Players' hand and backhand (do this the first time you see each player).** Ask the user, for every player name in the session (`me` when there is one person), which hand holds the racket and whether the backhand is one-handed or two-handed. Write them to `work/<s>/profiles.json` (private, not in git; names are friends' data). `candidates.py` and `assemble.py` read that file first, then `work/profiles.json` for any name it does not list, so the same name (`me`) can be right-handed in one session and left-handed in another. Use the global `work/profiles.json` only for a person whose hand is the same in every session (old sessions with only the global file work as before):

```json
{"white": {"hand": "R", "backhand": "two"}, "black": {"hand": "L", "backhand": "one"}}
```

Every hitting-arm metric (elbow, contact height and position, prep time, FH/BH guess, arm checks) follows each stroke's player. A lefty with the right-hand default gets wrong FH/BH guesses and wrong elbow numbers, so do not skip this. If a player has no entry, `assemble.py` guesses the hand from wrist speed during the swings and checks it against wrist height (the racket wrist rises higher); when the two disagree, the speed ratio is under 1.15 or there is too little video, it stops and asks for the player's entry in `work/<s>/profiles.json`. When they agree it prints `GUESSED` and marks every stroke `hand_guess: true`: tell the user, ask them to confirm, and say in `notes.json` `caveat` that the hand was guessed. A guess cannot be right for a mirrored phone video (selfie camera) or a one-hander's helper hand; only the user knows. If labels.txt moves a line to another player with `@name` and the two hold the racket in different hands, `assemble.py` warns once: the FH/BH pre-fill of that line was worked out for the original player's hand (it mirrors), so look at the sheet again. Add the entry and re-run assemble → export → refine; old sessions without `hand` count as right-handed, numbers unchanged.

Then build the stroke list:

```
python tools/run.py assemble.py <s>
```

It validates labels.txt and lists the candidates where its automatic kind (`auto_kind`: FH/BH/SV/OH, or `?` = it would not guess) disagrees with yours. Re-check those on the sheet. `candidates.py` pre-fills the kind column of labels.txt with that guess when `kind_conf` >= `kind.PREFILL_MIN` (a guess about the stroke kind, not about contact: confirm it on the sheet, and fill in the drill). `assemble.py` also lists the FH/BH strokes with `kind_conf` below `PREFILL_MIN` (weak swing evidence: look again for contact). SV and OH are left out: their `kind_conf` is fixed below that line by design, so it says nothing about contact. It is reliable for forehands, much weaker for backhands, and only a hint for OH vs SV; see docs/research/stroke-classify.md.

## 3. Clips and contact frames (judgment)

```
python tools/run.py export_session.py <s>
python tools/run.py strip.py <s> raw 1,2,3,...      # -> work/<s>/strip.jpg, frames -8..+4 around contact
```

Contact times already have each video's sound lag taken out: prep measures it from ball turns next to the wrist and writes it to `work/<s>/<video>/lag.txt` (frames; `0 fallback` when fewer than 3 hits matched a ball turn or they disagreed, so that video's times are the raw sound, which reaches the camera a little after contact). Sessions prepped before `lag.txt` existed have no such file; to get one, delete that video's `events.npy` and re-run prep (only events re-run, not pose or ball). Look at the strips in batches of 10–15 strokes and find the frame where the ball touches the strings; look harder at videos whose lag fell back. Write `work/<s>/refine.json`:

```json
{"default_off": 0, "off": {"5": -21}, "drop": [39, 50], "set": {"65": {"drill": "rally"}}}
```

`default_off` moves every stroke of the session, so leave it at 0 (or out). Set it only when the strips show the same offset across the whole session; the lag differs per video, so fix single strokes with `off`.

Numbers are raw stroke numbers (the numbers export printed). Use `drop` for false strokes you only notice now. Use `set` for relabels.

```
python tools/run.py refine.py <s>
```

It always starts from `strokes_raw.json`, so you can edit refine.json and re-run safely. After refine, strokes are renumbered #01…, and every later file uses the final numbers.

## 4. Findings, page, reel

Compute what matters from `web/sessions/<s>/strokes.json`. Each stroke has these fields:

- `player`: who hit it (`me` for single-player sessions). Compare and score each player separately.
- `knee`: the 10th-percentile knee angle 0.8–0.1 s before contact. Lower means more bent. ≤130 is good, >150 is nearly straight.
- `contact_h`：擊球時手腕高度（2D），接觸格附近五格（前後各兩格）的中位數。資料以肩髖長為單位，顯示乘以 100：髖＝0、肩＝100（身體傾斜時肩的垂直投影略低）。只評一致性，不給絕對分；保留可見度閘門。30–80 只可標中性色「參考（暫定）」，不能當理想區間或要求打在腰到胸。LTA 正拍教材約膝到腰的建議因來球而異，是教練教材而非實驗結論，且描述球的位置，不能套作手腕高度目標。
- `knee3d` (same window on the 3D skeleton, null for sessions without `pose_world.npy`) and `knee_warn` (true when the angle is unreliable for that stroke; `knee_warn_why` says why: `"gap"` = |knee3d - knee| > 20°, `"view"` = the camera is within 30° of straight in front or behind, from `cam_az`, the estimated camera azimuth 0 = front, 90 = side, 180 = behind). Neither 2D nor 3D knee angles are view-proof: side-on is the most accurate, and front/back views get no knee number. The web page and reel show `knee3d` when present. Thresholds above were set on 2D `knee`; 3D reads about 9° lower on average.
- `prep`: seconds from backswing end (hitting wrist furthest back relative to the hips, searched 1.0 s before contact; when the furthest-back frame is the window start it is followed back until the wrist moves forward again, up to 1.5 s) to contact. Longer means the racket was ready earlier. On 對牆影片 A it matched hand-picked frames within 2 frames (median). `prep_trunc: true` = still furthest back at the clip start, the time is a lower bound (show it as ≥, left out of the score). Camera within 30° of front / behind: prep uses the 3D swing direction and `contact_fwd` is null.
- `contact_fwd`: wrist ahead of the hip centre along the swing direction at contact, in torso lengths (same unit as `contact_h`). Its spread across strokes is the contact-point consistency. It moves about 0.1 per frame of contact error, so set refine.json contacts carefully before reading the spread, and compare only same-camera sessions.
- `serve_arm_straight` (SV) and `bh_elbow_ok` / `bh_front_ok` (one-handed BH: the player's `"backhand": "one"` in `work/<s>/profiles.json`, names it does not list fall back to `work/profiles.json`; a lefty uses the left arm): true / false / null (null = cannot tell from this view). They are checks, not scores, and the page shows them as grey reference only (never pass/fail: no bent arm was caught in test data, so do not cite a null or true as "fine"); rules in docs/scoring.md §9. Forehands get none.
- Body use, less sensitive to the camera angle than joint angles (docs/scoring.md §11): `trunk_share` (racket-side shoulder peak speed ÷ wrist peak speed, both relative to the hips; low = arm-only swing), `turn` (degrees the shoulder line travels from backswing end to 0.3 s after contact), `leg_load` (shown on the page as 重心降低) / `leg_drive` (hip drop before contact and rise at contact, share of standing hip height; this is how low the body gets, not a knee angle: a wide stance lowers the hip too), `wrist_speed` (torso lengths/s). `knee2d_ok` false = the leg was not side-on, so the 2D `knee` is unreliable (the 3D knee is less affected, but still not view-proof). The score caps a group's total at its power score (wrist speed, leg load = 重心降低) + 1.2, so an upright arm-only swing cannot score high; `scores.json` shows `power`, `uncapped` and `capped`.
- `elbow` (never cite it in findings: single-camera elbow error p90 is 37–48°), `open_min` (shoulder turn, 0% is fully side-on; citable only when `showOpen` is true), and `vis` (wrist visibility).

Good comparisons are self-fed vs rally forehand medians, the best and worst examples by number, and other sessions shot from the same camera position.

Before you write a finding about a specific stroke, look at it (`strip.py <s> final N -48 30 6`). Pose errors happen. For example, a 79° knee on a straight-standing player is a tracking glitch, so call it out in the caveat instead of praising it. Before you write "best ever" or "lowest", check the other sessions.

Write `web/sessions/<s>/notes.json`:

```json
{
 "sub": "3 支影片共 41 分鐘（夜間）",
 "camera": "手機放地上往上拍",
 "showOpen": false,
 "caveat": "數字的限制：鏡頭位置、被排除的片段、骨架抓錯的拍號。",
 "findings": [
  {"title": "自拋還是比對打站得直", "text": "自拋 33 拍膝蓋中位數 155°，對打 135°。", "cite": [{"kind": "FH", "drill": "feed", "field": "knee3d", "stat": "median", "value": 155}, {"kind": "FH", "drill": "rally", "field": "knee3d", "stat": "median", "value": 135}], "jump": [[5, "好球：#05"], [41, "問題：#41"]]},
  {"good": true, "title": "#17 蹲得最低", "text": "#17 膝蓋 118°。", "cite": [{"stroke": 17, "field": "knee3d", "value": 118}], "jump": [[17, "看 #17"]]},
  {"info": true, "title": "這場正拍拍數", "text": "可用的正拍有 40 拍。", "cite": [{"kind": "FH", "field": "knee3d", "stat": "n", "value": 40}]}
 ],
 "presets": [{"a": 5, "b": 41, "label": "對打 #05 vs 自拋 #41"}, {"a": ["2026-10-27", 23], "b": 17, "label": "跨場比較"}]
}
```

- `camera` decides comparability. Sessions with the same camera text can be compared in absolute numbers. A phone on the ground close to the player makes knees read about 15° straighter than a raised phone behind the baseline.
- Filming advice for the user: put the camera at the player's side (about 90° to the direction they face), still, whole body in frame. Straight behind or in front gives the worst knee angles (CalTennis: back 2D 34°, 3D 22° median error) and those strokes get no knee number.
- Set `showOpen` to true only when the camera is roughly behind the player at hip height or higher (shoulder turn needs that view; knees will then mostly be gated).
- Every finding needs `cite`: the numbers it states (single stroke, group stat or score), checked by the script below. Formats: `docs/scoring.md` §8.
- Keep 3–5 findings, each tied to stroke numbers the user can click. Mark the good ones `good: true`. Use `info: true` for neutral notes. Good and info findings need `cite` too: every finding is checked, with no exemption.

Then score the session and update the long-term trend:

```
python tools/run.py score.py <s>    # -> scores.json, one 1–10 per player and kind (FH/BH)
python tools/run.py trend.py        # -> web/sessions/trend.json, flags 缺點改善 / 優點退步 vs earlier same-camera sessions
```

After writing or editing `notes.json` and running score.py, always run the check. If it fails, fix the finding (the number or the cite), never loosen the check:

```
python tools/run.py check_findings.py <s>    # exit 1 + the failing findings
```

Anchors, sources, coverage gate and which metrics each camera excludes are in `docs/scoring.md`. Add trend flags to the findings (re-save `notes.json` after running these) only when they compare sessions with the same `camera` text.

寫跨場建議先看 `trend.json`：標題與內文遇「在誤差內」只能描述觀察到的差值及「無法判定進退步」，不得寫成進步、退步、改善或變得更穩。缺少區間／SEM、拍數不足或版本不同時也不下進退步結論；重跑 `score.py` → `trend.py` → `check_findings.py` 核對，失敗就修建議文字。區間要寫明是「同一場內抽樣的誤差，不是跨日重測」。

確定宣稱跨場進步／退步時，必須在每個對應分數的 `metric` 引用明寫 `"change": "up"`／`"change": "down"`，分項一致性另寫 `"stat": "cons"`；不可把方向寫在單拍或原始統計引用。`change` 會無條件核對差值、誤差與方向，不能靠「建議／請」等字跳過。中性觀察與未來練習指令不加 `change`；舊文字僅作保守詞彙核對，不把它當成理解自然語言的保證。

`cite.change` 是權威宣告，文字判斷只是保守輔助，不保證抓到所有寫法；逐項確認文字與宣告方向一致。遇到新的文字寫法漏抓，列已知限制，不再擴充文字規則；改用明確的分數引用與 `change` 表達確定變化，誤差內或無估計仍只能寫中性觀察。

Highlight reel (optional, when asked or when the session has clear examples). Write `work/<s>/reel.json`. The format is in the header of `tools/highlights.py`: cards plus one- or two-up clips by final stroke number. Then:

```
python tools/run.py highlights.py <s>
python tools/run.py build_site.py
```

Open `web/index.html` (`python tools/run.py open web/index.html`) and look at it before you report. Check that the findings, jump buttons, compare presets and reel all work.

## Answering questions later

- To answer "what time is #38", look up `clock` in strokes.json. It means `video·m:ss`, and `videos.json` maps the video number to its file.
- To find rallies, look for runs of strokes with gaps ≤ 6.5 s, then look at a 1 fps contact sheet of that stretch before you claim a rally length. The opponent is usually off camera, so say that shot counts are inferred.

## What not to do

- Don't put videos, `work/` or `web/sessions/` in git. They hold the user's footage.
- Don't change the metric definitions in `tools/metrics.py` silently. Every session's numbers are only comparable because they share them.
