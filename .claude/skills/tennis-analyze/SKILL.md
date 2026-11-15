---
name: tennis-analyze
description: Analyze a tennis practice session from phone videos in videos/<date>/ — find the player's strokes, measure knee bend / contact height per stroke, build the review page and a highlight reel. Use when the user adds new tennis videos, asks to analyze a practice, asks about a stroke number or timestamp, or wants highlights or rallies.
---

# Tennis session analysis

The pipeline is half scripts, half your eyes. Scripts find hit sounds, track one body with MediaPipe, and measure angles. You decide which candidates are the user's real strokes, whether each was self-fed or in a rally, where contact really is, and what the session means. Do every judgment step by looking at the images. Never label from the numbers alone.

Run everything from the repo root with `.venv/bin/python tools/<script>`. If `.venv` is missing, run `./setup.sh`. A session is a folder name under `videos/`, conventionally the date (`2026-11-05`).

Reply to the user in the language they write in. The page and reel text are Traditional Chinese; write findings and reel text in the user's language if it differs.

## 1. Prepare

```
tools/prep.sh <s>
```

This makes the proxy, audio, pose, onsets, ball track (`ball.npy`, RacketVision), hit events (`events.npy` = hit sounds confirmed by a fast wrist on the tracked player, timed with the ball track) and match files per video in `work/<s>/<video>/`, plus `videos.json`, which fixes the order (video 1, 2, 3 by filename). Pose runs about real time and the ball tracker adds about 2.4 s per second of video on an Apple GPU (portrait is 4x that), so 40 minutes of video takes about 2.5 hours. Run it in the background and tell the user how long it will take. It resumes where it stopped.

Portrait and landscape 16:9 video both work (proxy is 540x960 or 960x540; each stroke stores its `size`). The tracker follows one body, so with two or more people in frame expect runs on the wrong person and mark them `x other-player`.

## 2. Candidates and labels (judgment)

```
.venv/bin/python tools/candidates.py <s>
```

This writes `work/<s>/sheet0.jpg`… with 24 candidates per sheet. Each row shows 5 crops around one hit sound (-45, -25, -8, 0, +12 frames at 60 fps), labeled `<idx> v<video> m:ss`. Read every sheet. Fill `work/<s>/labels.txt`, one line per idx, in the form `idx kind drill [comment]`:

- `kind` is FH, BH, SV (serve), OH (overhead), or `x`. Use `x` when it is not the user (another player the tracker jumped to), not a stroke (a bounce, a pickup, a practice swing with no ball), or a duplicate of the stroke just before (the follow-through of the previous candidate).
- `drill` is `feed` if the user tossed the ball to themselves (look at -45 / -25: the ball is in their hand or a free hand is releasing it), `rally` if it came from the other side, `high` if it was self-fed high, `unsure` if you can't tell. SV takes no drill.
- First ask the user, or work out from the sheets, which person they are (shirt colour, side of court). If several people appear, the tracker may follow someone else for whole stretches. Mark those runs `x other-player`.
- A rally shows a gap of roughly 3–6 s between candidates. A run of feeds shows toss motions. Use the timing to settle doubtful feed / rally calls.

**Players' hand and backhand (do this the first time you see each player).** Ask the user, for every player name in the session (`me` when there is one person), which hand holds the racket and whether the backhand is one-handed or two-handed. Write them to `work/profiles.json` (private, not in git; names are friends' data):

```json
{"white": {"hand": "R", "backhand": "two"}, "black": {"hand": "L", "backhand": "one"}}
```

Every hitting-arm metric (elbow, contact height and position, prep time, FH/BH guess, arm checks) follows each stroke's player. A lefty with the right-hand default gets wrong FH/BH guesses and wrong elbow numbers, so do not skip this. If a player has no entry, `assemble.py` guesses the hand from wrist speed during the swings, prints `GUESSED` (and `UNSURE` when the two wrists are within 15%), and marks every stroke `hand_guess: true`: tell the user, ask them to confirm, and say in `notes.json` `caveat` that the hand was guessed. A guess cannot be right for a mirrored phone video (selfie camera) or a one-hander's helper hand; only the user knows. Add the entry and re-run assemble → export → refine; old sessions without `hand` count as right-handed, numbers unchanged.

Then build the stroke list:

```
.venv/bin/python tools/assemble.py <s>
```

It validates labels.txt and lists the candidates where its automatic FH/BH guess disagrees with yours. Re-check those on the sheet.

## 3. Clips and contact frames (judgment)

```
.venv/bin/python tools/export_session.py <s>
.venv/bin/python tools/strip.py <s> raw 1,2,3,...      # -> work/<s>/strip.jpg, frames -8..+4 around contact
```

The hit sound arrives 1–3 frames after the ball meets the strings. Look at the strips in batches of 10–15 strokes and find the frame where the ball touches the strings. Write `work/<s>/refine.json`:

```json
{"default_off": -2, "off": {"5": -21}, "drop": [39, 50], "set": {"65": {"drill": "rally"}}}
```

Numbers are raw stroke numbers (the numbers export printed). Use `drop` for false strokes you only notice now. Use `set` for relabels.

```
.venv/bin/python tools/refine.py <s>
```

It always starts from `strokes_raw.json`, so you can edit refine.json and re-run safely. After refine, strokes are renumbered #01…, and every later file uses the final numbers.

## 4. Findings, page, reel

Compute what matters from `web/sessions/<s>/strokes.json`. Each stroke has these fields:

- `knee`: the 10th-percentile knee angle 0.8–0.1 s before contact. Lower means more bent. ≤130 is good, >150 is nearly straight.
- `contact_h`: the wrist height at contact, with hip = 0 and shoulder = 1. 0.3–0.8 is the waist-to-chest target.
- `knee3d` (same window on the 3D skeleton, null for sessions without `pose_world.npy`) and `knee_warn` (true when |knee3d - knee| > 20°, so the angle is unreliable for that stroke). The web page and reel show `knee3d` when present. Thresholds above were set on 2D `knee`; 3D reads about 9° lower on average.
- `prep`: seconds from backswing end (hitting wrist furthest back relative to the hips, searched up to 1.0 s before contact) to contact. Longer means the racket was ready earlier. On wall-1 it matched hand-picked frames within 2 frames (median); a backswing finished more than 1.0 s before contact is cut to the window.
- `contact_fwd`: wrist ahead of the hip centre along the swing direction at contact, in torso lengths (same unit as `contact_h`). Its spread across strokes is the contact-point consistency. It moves about 0.1 per frame of contact error, so set refine.json contacts carefully before reading the spread, and compare only same-camera sessions.
- `serve_arm_straight` (SV) and `bh_elbow_ok` / `bh_front_ok` (one-handed BH: the player's `"backhand": "one"` in profiles.json; a lefty uses the left arm): true / false / null (null = cannot tell from this view). They are checks, not scores; rules in docs/scoring.md §9. Forehands get none.
- Body use, readable from any horizontal camera angle (docs/scoring.md §11): `trunk_share` (racket-side shoulder peak speed ÷ wrist peak speed, both relative to the hips; low = arm-only swing), `turn` (degrees the shoulder line travels from backswing end to 0.3 s after contact), `leg_load` / `leg_drive` (hip drop before contact and rise at contact, share of standing hip height; this is how low the body gets, not a knee angle: a wide stance lowers the hip too), `wrist_speed` (torso lengths/s). `knee2d_ok` false = the leg was not side-on, so the 2D `knee` is unreliable (3D is unaffected). The score caps a group's total at its power score (wrist speed, turn, leg load) + 1.2, so an upright arm-only swing cannot score high; `scores.json` shows `power`, `uncapped` and `capped`.
- `elbow`, `open_min` (shoulder turn, 0% is fully side-on), and `vis` (wrist visibility).

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
- Set `showOpen` to true only when the camera is roughly behind the player at hip height or higher.
- Every finding needs `cite`: the numbers it states (single stroke, group stat or score), checked by the script below. Formats: `docs/scoring.md` §8.
- Keep 3–5 findings, each tied to stroke numbers the user can click. Mark the good ones `good: true`. Use `info: true` for neutral notes. Good and info findings need `cite` too: every finding is checked, with no exemption.

Then score the session and update the long-term trend:

```
.venv/bin/python tools/score.py <s>    # -> scores.json, one 1–10 per player and kind (FH/BH)
.venv/bin/python tools/trend.py        # -> web/sessions/trend.json, flags 缺點改善 / 優點退步 vs earlier same-camera sessions
```

After writing or editing `notes.json` and running score.py, always run the check. If it fails, fix the finding (the number or the cite), never loosen the check:

```
.venv/bin/python tools/check_findings.py <s>    # exit 1 + the failing findings
```

Anchors, sources, coverage gate and which metrics each camera excludes are in `docs/scoring.md`. Add trend flags to the findings (re-save `notes.json` after running these) only when they compare sessions with the same `camera` text.

Highlight reel (optional, when asked or when the session has clear examples). Write `work/<s>/reel.json`. The format is in the header of `tools/highlights.py`: cards plus one- or two-up clips by final stroke number. Then:

```
.venv/bin/python tools/highlights.py <s>
.venv/bin/python tools/build_site.py
```

Open `web/index.html` (`open web/index.html`) and look at it before you report. Check that the findings, jump buttons, compare presets and reel all work.

## Answering questions later

- To answer "what time is #38", look up `clock` in strokes.json. It means `video·m:ss`, and `videos.json` maps the video number to its file.
- To find rallies, look for runs of strokes with gaps ≤ 6.5 s, then look at a 1 fps contact sheet of that stretch before you claim a rally length. The opponent is usually off camera, so say that shot counts are inferred.

## What not to do

- Don't put videos, `work/` or `web/sessions/` in git. They hold the user's footage.
- Don't change the metric definitions in `tools/metrics.py` silently. Every session's numbers are only comparable because they share them.
