# 場內 bootstrap 與誤差門檻；不讀取私人資料。
import math
import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import numpy as np
import score
from trend import compare, _entry
from check_findings import check

strokes = [dict(kind='FH', video=i // 10, knee=128 + i % 10 * 2, prep=0.3 + i % 10 * 0.03,
                vis=0.9, contact_h=0.4 + i % 5 * 0.03) for i in range(20)]
g = score.bootstrap_group(strokes, False)
again = score.bootstrap_group(strokes, False)
assert g == again
plain = score.score_group(strokes, False)
assert {k: v for k, v in g.items() if k != 'uncertainty' and k != 'metrics'} == {k: v for k, v in plain.items() if k != 'metrics'}
for key, value in plain['metrics'].items():
    assert {k: v for k, v in g['metrics'][key].items() if k != 'uncertainty'} == value
assert g['uncertainty']['total']['ci'][0] < g['uncertainty']['total']['ci'][1]
assert g['uncertainty']['total']['sem'] > 0
assert g['metrics']['contact_h']['uncertainty']['score'] is None
assert g['metrics']['contact_h']['uncertainty']['cons']['sem'] is not None
small = score.bootstrap_group(strokes[:2], False)
assert small['total'] is None and small['uncertainty']['total'] is None
bad = score.bootstrap_group([dict(s, knee_warn=True) for s in strokes], False)
assert bad['metrics']['knee']['score'] is None and bad['metrics']['knee']['uncertainty']['score'] is None
border = score.bootstrap_group(strokes[:3] + [dict(s, knee_warn=True) for s in strokes[3:6]], False)
u = border['metrics']['knee']['uncertainty']['score']
assert border['metrics']['knee']['score'] is not None and 0 < u['valid'] < u['samples']
assert u['ci'] is None and u['sem'] is None
# 每片重抽原數量，正式閘門重跑；SEM 是 bootstrap 樣本 SD，沒有除 sqrt(B)。
rng = np.random.default_rng(score.BOOTSTRAP_SEED)
by_video = [[s for s in strokes if s['video'] == v] for v in (0, 1)]
samples = []
for _ in range(score.BOOTSTRAP_N):
    draw = [clip[i] for clip in by_video for i in rng.integers(0, len(clip), len(clip))]
    samples.append(score.score_group(draw, False)['total'])
assert g['uncertainty']['total']['sem'] == float(np.std(samples, ddof=1))
assert g['uncertainty']['total']['ci'] == list(np.percentile(samples, [2.5, 97.5]))

def row(s, value, sem=0.3, **kw):
    return dict(session=s, camera='c', n=20, score_version=10, knee_src='knee',
                items={'total': value}, uncertainty={'total': {'ci': [value-0.6,value+0.6], 'sem': sem}}, **kw)
assert compare([row('a',7),row('b',6.5)])[0]['flag'] == '在誤差內'
assert compare([row('a',4),row('b',7)])[0]['flag'] == '缺點改善'
assert compare([row('a',9),row('b',6)])[0]['flag'] == '優點退步'
threshold = 1.96 * math.sqrt(0.3**2 + 0.3**2)
f = compare([row('a',7),row('b',7+threshold)])[0]
assert f['flag'] == '在誤差內' and abs(f['threshold']-threshold)<1e-12
f = compare([row('a',7),row('b',7),row('c',7),row('d',7.5)])[0]
assert abs(f['threshold'] - 1.96 * math.sqrt(0.3**2 + 3*0.3**2/9)) < 1e-12
assert compare([row('a',7),dict(row('b',3),score_version=9)]) == []
assert compare([row('a',7),dict(row('b',3),uncertainty={})]) == []
assert compare([row('a',7),dict(row('b',3),uncertainty={'total':{'sem':None}})]) == []
assert compare([dict(row('a',7),cons_set=['knee']),dict(row('b',3),cons_set=['prep'])]) == []
# 舊資料缺少版本也不視為可比。
assert compare([dict(row('a',7),score_version=None),dict(row('b',3),score_version=None)]) == []
# 最新一場的區間進入走勢資料。
e = _entry(dict(session='b',date='2020-01-02',camera='c'), dict(g,player='me',kind='FH'))
assert e['uncertainty']['total'] == g['uncertainty']['total']

# 宣稱變化連標題也核對；未在 cite 明列的具名指標仍須查。
def run(s, day, total, knee):
    group = dict(g, player='me',kind='FH',total=total)
    group['uncertainty'] = {**g['uncertainty'], 'total': {'sem':0.3,'ci':[total-0.6,total+0.6]}}
    group['metrics'] = {**g['metrics'], 'knee': {**g['metrics']['knee'], 'score':knee, 'uncertainty':{'score':{'sem':0.6,'ci':[knee-1.2,knee+1.2]}}}}
    return dict(session=s,date=day,camera='c',show_open=False,groups=[group])
a,b = run('a','2020-01-01',7,9.3),run('b','2020-01-02',6.5,8)
cite=[dict(kind='FH',metric='total',value=6.5)]
def errors(title,text=''):
    return check(dict(findings=[dict(title=title,text=text,cite=cite)]),strokes,b,runs=[a,b])
assert errors('膝蓋退步')
assert errors('總分退步')
assert errors('觀察','總分下降，確定退步')
assert errors('總分在誤差內，仍然退步')
assert errors('膝蓋在誤差內，無法判定退步') == []
assert errors('膝蓋在誤差內，無法判定進退步') == []
assert errors('總分在誤差內') == []
assert check(dict(findings=[dict(title='總分進步',cite=[dict(stroke=1,field='knee',value=128)])]),strokes,b,runs=[a,b])
# 同一分項的一致性宣稱須用該分項 SEM，不能拿整組一致性代替。
for run in (a,b):
    run['groups'][0]['metrics']['contact_h'] = {**run['groups'][0]['metrics']['contact_h'], 'uncertainty': {'cons': {'sem':1.0,'ci':[1,10]}}}
a['groups'][0]['metrics']['contact_h']['cons']=4
b['groups'][0]['metrics']['contact_h']['cons']=4.2
assert errors('擊球時手腕高度（2D）更穩')
b['groups'][0]['metrics']['contact_h']['cons']=9
assert errors('擊球時手腕高度（2D）更穩') == []
assert check(dict(findings=[dict(title='這個分項更穩',cite=[dict(kind='FH',metric='contact_h',stat='cons',value=9)])]),strokes,b,runs=[a,b]) == []
# 真正超過門檻，既有數字核對與建議宣稱都可通過。
a['groups'][0]['total']=3
assert errors('總分進步') == []
# 審查回歸：大變化也必須寫對方向；練習建議與同場比較不套跨場歷史閘門。
assert errors('總分退步')
a['groups'][0]['total']=9
assert errors('總分進步')
assert errors('總分退步') == []
assert check(dict(findings=[dict(title='下次練習改善膝蓋彎曲',cite=cite)]),strokes,b,runs=[]) == []
assert check(dict(findings=[dict(title='建議先改善膝蓋彎曲',cite=cite)]),strokes,b,runs=[]) == []
within = [dict(s,drill='feed' if i<10 else 'rally',knee=128 if i<10 else 128+i%10*2) for i,s in enumerate(strokes)]
finding = dict(title='這場自拋比對打更穩',cite=[dict(kind='FH',drill='feed',field='knee',stat='median',value=128),dict(kind='FH',drill='rally',field='knee',stat='median',value=137)])
current = dict(b,groups=score.score_session(within,False))
assert check(dict(findings=[finding]),within,current,runs=[]) == []
assert check(dict(findings=[dict(finding,title='比前場更穩')]),within,current,runs=[])
# 同日場次依 (date, session) 取基準，與正式走勢一致。
same_a,same_b = copy.deepcopy([a,b])
same_a['date']=same_b['date']
assert check(dict(findings=[dict(title='總分退步',cite=cite)]),strokes,same_b,runs=[same_a,same_b]) == []
# 技術、力量與未壓前分數可與受上限影響的總分朝不同方向。
left,right = copy.deepcopy([a,b])
for r,total,form,power,uncapped in [(left,7,9,9,9),(right,8.5,8,8,8.5)]:
    r['groups'][0].update(total=total,form=form,power=power,uncapped=uncapped)
    r['groups'][0]['uncertainty'].update({k:{'sem':0.1,'ci':[1,10]} for k in ('total','form','power','uncapped')})
def group_claim(title,metric):
    c=[dict(kind='FH',metric=metric,value=right['groups'][0][metric])]
    return check(dict(findings=[dict(title=title,cite=c)]),strokes,right,runs=[left,right])
assert group_claim('技術分進步','form')
assert group_claim('技術分退步','form') == []
assert group_claim('這個分數進步','form')
assert group_claim('力量分進步','power')
assert group_claim('力量分退步','power') == []
left['groups'][0].update(total=9,uncapped=9.1)
right['groups'][0].update(total=6.5,uncapped=9.8)
assert group_claim('未壓前總分進步','uncapped') == []
# 合成分數的計分集合變更不能冒充技術進步；力量與未壓前總分同樣核對。
changed_left,changed_right=[copy.deepcopy(left),copy.deepcopy(right)]
changed_left['groups'][0]['metrics']['prep']['score']=None
changed_left['groups'][0]['form_metrics']=['knee']
changed_left['groups'][0]['form']=4
changed_right['groups'][0]['form']=7
assert check(dict(findings=[dict(title='技術分進步',cite=[dict(kind='FH',metric='form',value=7)])]),strokes,changed_right,runs=[changed_left,changed_right])
for metric in ('power','uncapped'):
    changed_left,changed_right=[copy.deepcopy(left),copy.deepcopy(right)]
    changed_left['groups'][0][metric]=4
    changed_right['groups'][0][metric]=7
    changed_left['groups'][0]['metrics']['wrist_speed']=dict(score=4,cons=None)
    changed_right['groups'][0]['metrics']['wrist_speed']=dict(score=4,cons=None)
    changed_right['groups'][0]['metrics']['leg_load']=dict(score=10,cons=None)
    if metric=='uncapped':
        changed_left['groups'][0]['metrics']['prep']['score']=None
        changed_left['groups'][0]['form_metrics']=['knee']
    assert check(dict(findings=[dict(title='這個分數進步',cite=[dict(kind='FH',metric=metric,value=7)])]),strokes,changed_right,runs=[changed_left,changed_right])
# 技術集合不受力量項目增減影響；未壓前總分仍要求一致性集合相同。
changed_left,changed_right=[copy.deepcopy(left),copy.deepcopy(right)]
changed_left['groups'][0]['metrics']['wrist_speed']=dict(score=None,cons=None)
changed_right['groups'][0]['metrics']['wrist_speed']=dict(score=4,cons=None)
assert check(dict(findings=[dict(title='技術分退步',cite=[dict(kind='FH',metric='form',value=8)])]),strokes,changed_right,runs=[changed_left,changed_right]) == []
changed_left['groups'][0]['metrics']['contact_h']['cons']=None
assert check(dict(findings=[dict(title='未壓前總分進步',cite=[dict(kind='FH',metric='uncapped',value=9.8)])]),strokes,changed_right,runs=[changed_left,changed_right])
# 不具名宣稱只取同球員、拍種的引用；無效引用須回報而非拋例外。
assert check(dict(findings=[dict(title='這個分數退步',cite=[dict(kind='FH',metric=1,value=8)])]),strokes,right,runs=[left,right])
print('場內區間、差值門檻與建議核對測試通過')
