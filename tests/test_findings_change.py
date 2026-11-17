# 明列方向嚴格核對，舊文字的否定與練習指令不冒充已觀察的變化。
import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
from check_findings import check
from trend import _entry, compare


def run(session, day, total, consistency):
    u = {'ci': [1, 10], 'sem': 0.3}
    group = dict(player='me', kind='FH', n=20, total=total, form=total,
                 consistency=consistency, power=None, uncapped=total,
                 score_version=10, knee_src='knee', form_metrics=['knee'], form_n=1,
                 uncertainty={k: copy.deepcopy(u) for k in ('total', 'form', 'consistency', 'uncapped')},
                 metrics={'knee': dict(score=total, cons=consistency, median=130, n=20,
                                       uncertainty={'score': copy.deepcopy(u), 'cons': copy.deepcopy(u)})})
    return dict(session=session, date=day, camera='側面', groups=[group])


noise = [run('a', '2026-01-01', 7, 7), run('b', '2026-01-02', 6.5, 6.5)]
down = [run('a', '2026-01-01', 9, 9), run('b', '2026-01-02', 6, 6)]
up = [run('a', '2026-01-01', 3, 3), run('b', '2026-01-02', 8, 8)]


def errors(text, runs=noise, metric='total', **cite):
    group = runs[-1]['groups'][0]
    value = group.get(metric) if metric in group else group['metrics'][metric][cite.get('stat', 'score')]
    finding = dict(title=text, cite=[dict(kind='FH', metric=metric, value=value, **cite)])
    return check(dict(findings=[finding]), [], runs[-1], runs=runs)


failures = []
cases = [
    ('一致性比前場不穩', down, 'consistency', False),
    ('一致性比前場不穩', up, 'consistency', True),
    ('一致性變不穩', down, 'consistency', False),
    ('一致性變不穩', up, 'consistency', True),
    ('膝蓋不穩', [down[-1]], 'knee', False),
    ('一致性不穩', [down[-1]], 'consistency', False),
    ('一致性不穩', noise, 'consistency', False),
    *[(t, noise, 'total', False) for t in (
        '總分無法判定是否退步', '不能說膝蓋更穩', '沒有變好', '不算變差', '無法判定膝蓋改善')],
    *[(t, noise, 'total', True) for t in (
        '建議：總分比前場退步', '總分比前場進步請繼續維持')],
    ('下次練習改善膝蓋彎曲', noise, 'total', False),
    ('建議先改善膝蓋彎曲', noise, 'total', False),
    *[(t, noise, 'total', True) for t in ('總分下降', '總分降低', '一致性降低')],
    *[(t, down, 'total', False) for t in ('總分下降', '總分降低', '一致性降低')],
    *[(t, noise, 'total', False) for t in ('總分沒有下降', '無法判定總分降低', '下次練習降低失誤')],
    *[(f'無法確定位置{word}總分進步', noise, 'total', True) for word in ('但', '而', '所以', '因此')],
]
for text, runs, metric, expected in cases:
    actual = errors(text, runs, metric)
    if bool(actual) != expected:
        failures.append((text, expected, actual))

for text, runs, metric, direction, expected in [
    ('觀察結果', noise, 'total', 'up', True),
    ('觀察結果', noise, 'total', 'down', True),
    ('下次練習改善膝蓋彎曲', noise, 'total', 'up', True),
    ('膝蓋不穩', noise, 'knee', 'up', True),
    ('觀察結果', down, 'total', 'down', False),
    ('觀察結果', down, 'total', 'up', True),
    ('觀察結果', up, 'consistency', 'up', False),
    ('觀察結果', up, 'consistency', 'down', True),
    ('觀察結果', up, 'knee', 'up', False),
    ('觀察結果', up, 'total', 'flat', True),
]:
    actual = errors(text, runs, metric, change=direction)
    if bool(actual) != expected:
        failures.append((text, metric, direction, expected, actual))
if not errors('觀察結果', up, 'knee', stat='median', change='up'):
    failures.append('原始統計引用不得宣告分數方向')
if errors('觀察結果', up, 'knee', stat='cons', change='up'):
    failures.append('分項一致性應使用自己的方向與 SEM')
if not errors('觀察結果', [up[-1]], change='up'):
    failures.append('明列方向仍須有可比歷史')
mixed = dict(title='觀察結果', cite=[dict(stroke=1, field='knee', kind='FH', metric='total', value=8, change='up')])
if not check(dict(findings=[mixed]), [dict(kind='FH', knee=8)], up[-1], runs=up):
    failures.append('單拍引用不能混入分數方向')


def expect_claim(label, text, runs, cites, expected, strokes=(), missing=False):
    try:
        actual = check(dict(findings=[dict(title=text, cite=cites)]), strokes, runs[-1], runs=runs)
        if bool(actual) != expected or missing and not any('沒有足夠的誤差估計' in x for x in actual):
            failures.append((label, actual))
    except Exception as exc:
        failures.append((label, type(exc).__name__, str(exc)))


raw = copy.deepcopy(noise)
raw[-1]['groups'][0]['metrics']['knee'].update(median=125, spread=5)
for text, metric, stat, value in (
    ('膝蓋降低重心', 'knee', 'score', 6.5),
    ('引拍時降低重心', 'total', 'score', 6.5),
    ('膝蓋角度下降到 125°', 'knee', 'median', 125),
    ('散佈下降', 'knee', 'spread', 5),
):
    finding = dict(title='觀察結果', text=text,
                   cite=[dict(kind='FH', metric=metric, stat=stat, value=value)])
    actual = check(dict(findings=[finding]), [], raw[-1], runs=raw)
    if actual: failures.append((text, '動作與原始統計不得當成分數退步', actual))


leg = copy.deepcopy(noise)
for r, value in zip(leg, (8, 7.8)):
    r['groups'][0]['metrics']['leg_load'] = dict(score=value, cons=None, uncertainty={'score': {'ci': [7, 9], 'sem': .3}})
    r['groups'][0]['form_metrics'] = ['knee']
leg_cite = dict(kind='FH', metric='leg_load', value=7.8)
expect_claim('指標名稱不是退步宣稱', '重心降低 7.8', leg, [leg_cite], False)
for word in ('下降', '降低'):
    expect_claim('指標名稱後仍可宣稱退步', '重心降低分數' + word, leg, [leg_cite], True)
expect_claim('下降明列方向超門檻放行', '總分下降', down,
             [dict(kind='FH', metric='total', value=6, change='down')], False)


scoped = copy.deepcopy(up)
for r, value in zip(scoped, (7, 7.1)):
    r['groups'][0]['metrics']['knee']['cons'] = value
expect_claim('多筆引用不改查整組一致性', '一致性改善', scoped,
             [dict(kind='FH', metric='knee', stat='cons', value=7.1), dict(kind='FH', metric='total', value=8)], True)
scoped = copy.deepcopy(up)
for r, value in zip(scoped, (7, 7.1)):
    r['groups'][0]['metrics']['prep'] = copy.deepcopy(r['groups'][0]['metrics']['knee'])
    r['groups'][0]['metrics']['prep'].update(score=4, cons=value)
expect_claim('更穩只查引用的 cons', '更穩', scoped,
             [dict(kind='FH', metric='knee', stat='cons', value=8), dict(kind='FH', metric='prep', value=4)], False)
expect_claim('每筆 cons 都須通過', '一致性改善', scoped,
             [dict(kind='FH', metric='knee', stat='cons', value=8), dict(kind='FH', metric='prep', stat='cons', value=7.1)], True)
expect_claim('未有評分組不能跳過', '總分進步', up,
             [dict(stroke=1, kind='OH', field='knee', value=130)], True, [dict(kind='OH', knee=130)], missing=True)
for where in ('missing', 'group', 'metric', 'history'):
    absent = copy.deepcopy(up)
    cite = dict(kind='FH', metric='total', value=8, change='up')
    if where == 'missing': del absent[-1]['groups'][0]['uncertainty']
    elif where == 'group': absent[-1]['groups'][0]['uncertainty'] = None
    elif where == 'metric':
        absent[-1]['groups'][0]['metrics']['knee']['uncertainty'] = None
        cite.update(metric='knee', stat='cons')
    else: absent[0]['groups'][0]['uncertainty'] = None
    expect_claim(f'缺估計或 null：{where}', '觀察結果', absent, [cite], True, missing=True)
try:
    rows = [_entry(r, r['groups'][0]) for r in up]
    rows[0]['uncertainty'] = None
    if compare(rows): failures.append('null 歷史列仍被比較')
except Exception as exc:
    failures.append(('null 歷史列', type(exc).__name__))
shared = [run('a', '2026-01-01', 9, 3), run('b', '2026-01-02', 6, 8)]
expect_claim('總分與一致性更穩不得漏總分', '總分與一致性更穩', shared,
             [dict(kind='FH', metric='total', value=6), dict(kind='FH', metric='consistency', value=8)], True)
expect_claim('未具名更穩維持原本的一致性判斷', '更穩', shared,
             [dict(kind='FH', metric='total', value=6)], False)
assert not failures, failures
print('方向引用、否定句與練習指令核對通過')
