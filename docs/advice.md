# 整體建議：一場只給一件最該練的事

目的：每場每位球員只給**一件**主要的事（最多再加一件次要的），每句話都要講得出：量什麼、為什麼可信、怎麼練、看哪幾拍、什麼時候不該講。量不準或資料不足就直說，並寫下次怎麼拍。

寫在 `web/sessions/<s>/notes.json` 的 `overall` 欄位（格式見最後一節），由 `tools/check_findings.py` 核對。這是練習參考，不能代替教練或醫療判斷。

## 證據等級

- **實證**：同儕審查論文直接支持。
- **教練共識**：兩份以上官方教材（ITF、USTA、Tennis Australia、LTA）一致。
- **單一來源意見**：只有一份教材或一位教練。

## 來源（全部公開，沒有用帳號）

| 縮寫 | 來源 | 讀到哪裡 |
|---|---|---|
| TA | Tennis Australia, *Technical Fundamentals*（2013，教練發展手冊）[PDF](https://www.tennis.com.au/wp-content/uploads/2014/11/Technical-and-Tactical-fundamentals-guidelines_low-res.pdf) | 全文 |
| LTA | LTA〈How to hit a tennis forehand〉[網頁](https://www.lta.org.uk/play/tennis-tips-and-techniques/how-to-play-a-tennis-forehand/) | 網頁內文 |
| USTA-G | USTA〈Get your forehand flowing〉（2018，USTA National Campus 教練）[網頁](https://www.usta.com/en/home/improve/tips-and-instruction/national/improve-your-tennis-game--get-your-forehand-flowing.html) | 網頁文字，影片沒看 |
| USTA-P | USTA〈Tennis 101: The Forehand〉（2017，USTA Player Development）[網頁](https://www.usta.com/en/home/improve/tips-and-instruction/national/learning-the-basics--forehand.html) | 網頁 |
| ITF-C | ITF 擊球修正檢核表（Crespo & Miley, *ITF Advanced Coaches Manual*, 1998）。原手冊沒拿到；內容取自用它做評量工具的論文（Frontiers in Sports and Active Living 2024，3 位教練現場評分，評分者間 ICC 0.97–0.98）[PMC11026554](https://pmc.ncbi.nlm.nih.gov/articles/PMC11026554/) | 論文全文 |
| REV | Reid, Elliott & Crespo 2013，〈Mechanics and Learning Practices Associated with the Tennis Forehand: A Review〉，JSSM 12:225 [全文](https://jssm.org/jssm-12-225.xml-Fulltext) | 全文 |
| EF | Tapan, Şahan & Erman 2023，Frontiers in Psychology 14:1308244（60 位 10 歲兒童，外部焦點口令的瞄準分數在後測與保留測都較高）[PMC10721975](https://pmc.ncbi.nlm.nih.gov/articles/PMC10721975/) | 全文 |
| COACH | 使用者的教練口頭確認（2026-11-22），單一來源意見 | 轉述，無文件 |
| SC | 本 repo [`docs/scoring.md`](scoring.md)（指標定義、閘門、驗證數字） | — |

Nesbit 2008（膝角）的出處與用法見 `docs/scoring.md`。Landlinger 2010（動力鏈順序）取自專案內部研究報告《網球分析關鍵指標》，未公開、這裡沒有連結。

**口訣與練法的出處（老實標）**：有來源的只有 LTA 的「非持拍手指著球」、對牆練習、空揮；USTA-G 的「用非持拍手接球練轉身，再加上擊球」；TA／LTA／USTA-P／ITF-C 的擊球點用詞。表裡其他口訣（「打在前腳前」「先坐下去，再打」「收到左肩」「肚臍轉向網子」「每球都在同一個點碰」）和大部分練法是**自擬**：照教練共識的要點改寫成短句，沒有經過真教練驗證。

**不再使用**：「等球升到腰再打」。教練確認自拋有兩種都對的打法（球彈地後打、球下落時直接打），這句會把落下直接打當成錯，和教練意見衝突；練法不得要求球升到某個高度才出手。

口訣用「外部焦點」寫（看球、看網柱、看前腳前方的位置），少用「手肘抬到哪」這種身體內部指令（EF，實證，但受試者是兒童）。

## 框架表

| # | 訊號（欄位） | 手機在什麼機位下可信 | 教練怎麼解讀 | 口訣 | 練習：對牆／自拋／對打 | 證據等級與出處 | 什麼情況**不該講** |
|---|---|---|---|---|---|---|---|
| 1 | **擊球點在身前**：`contact_fwd`（擊球時手腕在髖前多少，單位軀幹長）。兩種用法：同場「自拋 vs 對打」中位數差，或一致性 `cons` | 側面到側後方（`cam_az` 30–150°）；正前／正後為 null。只比同機位 | 擊球點在身體前方、側邊，是正反拍共同基本功；太靠身體＝來不及或站太近。教練確認（COACH）：在身體前方一點，約 2、3 點鐘方向的感覺，不是正側面；不要寫成越前越好 | 「打在前腳前」 | 對牆：站遠一點，讓球彈起後在前腳前方碰拍。自拋：球丟在身體側前方一大步。對打：看球時先側身、往前踩一步迎球 | 教練共識（TA 正拍／雙反「Contact made in front and to the side of the body」；LTA「ball in front of your body」；USTA-P「slightly in front of you and off to your right side」；ITF-C 第 8 項）。教練共識＋教練確認（COACH）。最佳距離沒有數字（SC） | 接觸格沒人工核過（錯 1 格約差 0.1）；兩組任一組 < 10 拍；差值的區間含 0 且沒有第二場同機位同方向；跨機位比絕對值；只靠一拍 |
| 2 | **準備（轉身拉拍）時機**：`prep` 只量「手腕最後方→擊球」，**不等於**轉身完成時間 | 數字：側面最好；對打、繞大圈的揮拍會偏短 | 教練要的是「球彈地前拉拍完成」、先轉身再拉拍 | 「球過網，左手指球」 | 對牆：球一離牆就側身、非持拍手指球。自拋：拋球時就已側身。對打：教練餵球、用非持拍手接球練轉身（USTA-G 的進程） | 教練共識（TA「Backswing is completed by the time the ball bounces」，並說常見「late racquet preparation」；USTA-G「unit turn rather than simply racquet back」；LTA 非持拍手指球）。`prep` 端點暫定（SC） | **沒看圖就不能講「引拍偏晚」**：要在縮圖上看到擊球前約 0.6 秒還沒側身才講。繞大圈的揮拍 `prep` 本來就短（試寫時看到準備很早、`prep` 卻偏短的例子）。`prep_trunc`；對打；沒有彈地時間 |
| 3 | **蹲低／腿部負荷**：`knee3d`（沒有才用 `knee`）、`leg_load`（重心降低） | 膝角只有側面可信（正前／正後由 `knee_warn` 擋掉）；`leg_load` 比較不受水平視角影響 | 引拍時外側腳負重、擊球時腿往上推 | 「先坐下去，再打」 | 對牆／自拋：拋球後先蹲到對打時的高度再出手。對打：分腿跳後落地就蹲 | 正拍前膝角有實證（Nesbit 2008，SC）；「外側腳負重、腿部驅動」為教練共識（TA；REV 引 Nesbit、Seeley：膝的活動和拍速正相關） | `knee_warn`；對打跑動（量膝的窗會混進跑步跨步）；跨機位比絕對值；已經達到參考值（≤ 125°）時不當問題 |
| 4 | **收拍完整**：`finish`（擊球後 0.5 秒內較高手腕高於肩多少） | 只在一個對牆側後方機位驗過（SC） | 收拍收到對側肩上方，代表揮拍有加速穿過球 | 「收到左肩，看手肘指前方」 | 對牆：每拍停住收拍姿勢一秒再回位。自拋同。對打：先求穩，不要求 | 教練共識但有分歧（TA「Racquet finishes over the opposite shoulder」；LTA 進階版收到非持拍手肩上，但對初學者說收拍可以短、像推）；實證弱（REV：「follow-through … poorly investigated」） | **數字不能單獨用**：試寫時看到收到對側肩的拍也讀到負值（手腕在肩下），只有看圖確認才能講；初學者控球階段不講 |
| 5 | **擊球時手腕高度**：`contact_h` | 很受接觸格誤差影響（SC） | 球的理想高度約膝到腰（LTA），但那是球、不是手腕。教練確認（COACH）：擊球在腰附近、再低一點都可以；只在明顯太高或太低時才提 | — | — | 單一來源意見（LTA、COACH）；SC 已把它降為只評一致性 | 幾乎都不該當主要的事；一致性低時先懷疑接觸格；高度落在腰附近或再低一點不提；**自拋打法（球彈地後打、球下落時直接打）兩種都對，本身不是問題，不得批評** |
| 6 | **身體出力**：`wrist_speed`、`trunk_share`、`turn` | `wrist_speed` 跨機位差大；`trunk_share`、`turn` 只顯示（SC §11） | 只用手臂打（肩不動）是常見問題 | 「肚臍轉向網子」 | 自拋：先轉身再揮。對打：同 | 動力鏈順序有實證（Landlinger 2010，內部研究報告），但 30–60 fps 解析不到；「用手臂打」為教練意見 | `trunk_share`、`turn` 不計分，不能當主要的事；手速只比同機位 |
| 7 | **一致性**（同一欄位的 `cons`） | 同上各欄位 | 業餘者擊球點不穩是常態；重點是擊球那一刻的位置可重複（REV 引 Knudson 1990） | 「每球都在同一個點碰」 | 對牆定點；自拋同一個位置丟球 | 實證（REV：重要的是擊球時關節位置的可重複性） | 一組 < 10 拍；一致性分區間很寬；`contact_h` 的一致性（主要反映接觸格誤差） |
| 8 | **看圖才看得出來**（沒有欄位，由分析者看四階段圖與縮圖） | 圖要拍到全身、球、球拍 | 非持拍手指球（LTA、TA）、拍子不舉超過頭（TA 正拍「Hitting hand does not raise above the head」）、分腿跳（ITF-C 第 3 項）、平衡（ITF-C 第 11 項） | 依項目 | 依項目 | 教練共識（依項目） | 只看到 1–2 拍；人在畫面邊緣被切掉；看圖結論要附拍號，並標「看圖觀察」 |
| 9 | 不用的欄位 | — | — | — | — | — | `elbow`（單機肘角 p90 誤差 37–48°）；`showOpen` 不是 true 時的 `open_min`；`open_contact`（隨站姿合理變化） |

## 挑選規則

**先過四道門檻（任何一道沒過就不能當主要的事）：**

1. **量得準**：用 `scores.json` 現成欄位判斷：`status == "ok"`；比較的每組可用拍數 ≥ 10；分數或差值的區間不含 0（或區間雖含 0，但**同人同機位的另一場**出現同方向）；不是框架表標「不該講」的情況。
2. **定義對得上口訣**：這個數字真的量到教練說的那件事（例：`prep` 量的是繞圈尾端，不是轉身完成，不能單獨代表「引拍晚」）。
3. **看圖確認**：兩邊各至少 3 拍在四階段圖（`tools/strip.py <s> final "N,N,…" --stages`）或縮圖上看得出差別。
4. **可練**：框架表那一列有對牆、自拋或對打的練法。

**過門檻後排序：**

1. **影響大**：照教練共識的基本功順序：擊球點在身前、準備時機 ＞ 腿部負荷 ＞ 收拍 ＞ 其他。
2. **重現**：同人同機位兩場同方向，優先。
3. **相對比較優先於絕對錨點**：同場「好拍 vs 壞拍」或「自拋 vs 對打」的差，偏差會互相抵消；絕對錨點多數是暫定的。目標數字只能用球員自己的好拍或對打中位數。

**次要的事**：同樣要過四道門檻，最多一件，和主要的事不同欄位；看圖觀察（框架表第 8 列，或數字不夠準的收拍、擊球高度、步法）也可以當次要的事，要附至少 3 拍拍號並標「看圖觀察」。

**沒有夠格的**：寫 `insufficient`（這場資料不足以給方向），並給具體拍法（`film_next`）：

- 機位：手機在球員側面約 90°，固定、全身入鏡、球員站在畫面中間（不要在邊緣被切掉）。
- 拍數：同一種擊球連續 30 拍以上（SC：一組要 30 拍以上，分數重測差才可能 ≤ 0.5，推算）。
- 練習類型：加一段「站定不跑」的餵球或自拋（讓膝角與準備時間可比）；只有對打跑動時，膝角與準備時間不拿來定方向。

資料不足也要給東西：除了下次怎麼拍，可以再給一件「保持」的優點或一件看圖觀察（放在 `second`）；標題和內文不能一邊說資料不足、一邊下技術判斷。

## 寫法

- 依序寫：主要的事 → 為什麼（數字、拍號，引用要能過 `check_findings.py`）→ 怎麼練（一個練法＋口訣）→ 看哪幾拍（好例、壞例拍號）→ 下次同機位看哪個數字。
- 舊建議若被看圖推翻，要在新建議裡講清楚（例如「引拍時機不是問題，數字偏短的原因是…」），不要讓兩個說法並存。
- 不寫次數組數；不寫進步／改善（沿用 SKILL.md）。
- **主張只講量到的那件事**：只量到「擊球點較靠身體」，就不要寫成「整個揮拍小一號」。寫之前把同一比較的其他欄位（`turn`、`wrist_speed`、`finish`）也列出來；有方向相反的，要在文字裡講。
- **差值要和接觸格誤差比**：`contact_fwd` 錯 1 格約差 0.1。差值 < 0.2 時，要寫「接近接觸格誤差」，並看圖確認擊球格；不能當成確定的事。
- **目標數字不要取自跑動中的拍**：對打的膝角若混了跑步跨步，就不能當成自拋的目標。
- **收拍、擊球高度、步法要看圖講**：教練從圖上最先講的是收拍有沒有收過對側肩、擊球高度、是不是伸手搆球。數字（`finish`、`contact_h`）不夠準時，看圖結論可以當次要的事。
- **證據和建議用同一套閘門算數字**（例：手腕可見度 < 0.5 的拍兩邊都要排除），否則讀者會以為數字寫錯。`cite` 的群組統計本來就過同一套閘門。

## `notes.json` 的 `overall` 欄位

每位球員最多一筆。範例在 `.claude/skills/tennis-analyze/SKILL.md`（`tests/test_check_overall.py` 會拿它跑核對）。

```json
"overall": [
  {"player": "me",
   "main":   {"title": "…", "why": "…", "cite": [...], "practice": "…", "cue": "…", "jump": [[13, "對打 #13"]]},
   "second": {"title": "…", "why": "…", "cite": [...], "practice": "…"},
   "look":   [2, 5, 13, 16]},
  {"player": "B",
   "insufficient": {"title": "B：這場資料不足以給方向", "why": "…", "cite": [...]},
   "look": [23, 24, 25],
   "film_next": "…"}
]
```

| 欄位 | 必填 | 內容 |
|---|---|---|
| `player` | 是 | 和 strokes.json 的 `player` 一樣（單人場次是 `me`） |
| `main` | 和 `insufficient` 二選一 | 這場最該練的一件事 |
| `insufficient` | 和 `main` 二選一 | 資料不足的說明（`title`、`why`、`cite`） |
| `second` | 否 | 次要的事，最多一件，格式同 `main`（`jump` 可省） |
| `look` | 是 | 看過四階段圖或縮圖的拍號：這位球員的拍、至少 3 個、不重複 |
| `film_next` | `insufficient` 時必填 | 下次怎麼拍（機位、拍數、練習類型）。不核對數字：「側面約 90°」是拍法不是量測 |

`main`／`second` 內：`title`、`why`（為什麼，含數字與拍號）、`cite`（格式同 finding，見 `docs/scoring.md` §8）、`practice`（一個練法；要看的數字寫成中性的「下次同一機位拍，看…是不是接近…」）、`cue`（口訣，可省）、`jump`（`[[拍號, "標籤"]]`，`main` 必填）。

`check_findings.py` 的核對（不過就 exit 1，`build_site.py` 也不寫檔）：

- `title`、`why`、`practice`、`cue` 裡的數字照 finding 文字的規則都要有 `cite` 對得上；`#NN` 與 `jump` 的拍號要存在；進退步詞彙照舊核對。
- `main` 至少要有**這位球員**的一個 metric 引用（`stat` 不是 `n`，或 `total` 等分組分數），或一個比較：同一欄位、同一拍種、兩種不同 `drill` 的 median／mean 引用，各 ≥ 10 拍可用（`MAIN_MIN_N`，暫定）；**也可以直接引 `drill_diff`**（`stat` 是 `diff`、`ci_lo` 或 `ci_hi`，格式見 `docs/scoring.md` §8；兩邊各 ≥ 10 拍才有值，不夠就報錯）。metric 引用不看拍數，門檻 1 的「每組 ≥ 10 拍」要自己確認。`jump` 每項是 `[拍號, 標籤]`。
- 引用 `drill_diff` 的 `diff`／`ci_lo`／`ci_hi` 而區間含 0 時，文字要寫「不確定」或「暫定」（同「差值不能當成確定的事」），否則報錯。區間含 0 又沒有第二場同機位同方向，挑選規則門檻 1 仍不讓它當主要的事，那是分析者的事。
- `insufficient` 不能和 `main` 同時出現，一定要有 `film_next`。
- 每位球員最多一筆；`main`、`second` 各是一個物件（不能塞陣列）。
- 問題型 finding（不是 `info`、不是 `good`）只要有引用 `prep`（`field` 或 `metric`），就必須有 `look`（≥ 3 個存在的拍號）。finding 的 `look` 可省；寫了就照同樣規則核對。
- 舊的 notes.json 沒有 `overall` 照常可用。
