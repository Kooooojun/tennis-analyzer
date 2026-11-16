# 明列方向嚴格核對，舊文字的否定與練習指令不冒充已觀察的變化。
import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
from check_findings import check


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
    *[(t, noise, 'total', False) for t in (
        '總分無法判定是否退步', '不能說膝蓋更穩', '沒有變好', '不算變差', '無法判定膝蓋改善')],
    *[(t, noise, 'total', True) for t in (
        '建議：總分比前場退步', '總分比前場進步請繼續維持')],
    ('下次練習改善膝蓋彎曲', noise, 'total', False),
    ('建議先改善膝蓋彎曲', noise, 'total', False),
]
for text, runs, metric, expected in cases:
    actual = errors(text, runs, metric)
    if bool(actual) != expected:
        failures.append((text, expected, actual))

for text, runs, metric, direction, expected in [
    ('觀察結果', noise, 'total', 'up', True),
    ('觀察結果', noise, 'total', 'down', True),
    ('下次練習改善膝蓋彎曲', noise, 'total', 'up', True),
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
assert not failures, failures
print('方向引用、否定句與練習指令核對通過')
