#!/usr/bin/env python3
import json
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score, accuracy_score, balanced_accuracy_score, f1_score

REPO=Path(__file__).resolve().parents[1]
P0=REPO/'results/parisot_p0'; P12=REPO/'results/parisot'; OUT=REPO/'results/parisot_p0'
def load_regime(ss):
    d={}
    for fold in range(5):
        for ts in (11,22,33):
            p0=json.loads((P0/f'pa_{ss}_{fold}_{ts}.json').read_text())
            p12=json.loads((P12/f'pa_{ss}_{fold}_{ts}.json').read_text())
            for a,b in zip(p0['rows'],p12['rows']):
                sid=a['subject_id']; d.setdefault(sid,{'label':a['label'],'site':a['site'],'p0':[],'p1':[],'p2':[]})
                d[sid]['p0'].append(a['p_r0']); d[sid]['p1'].append(b['p_r1']); d[sid]['p2'].append(b['p_r2'])
    rows=[]
    for sid,x in sorted(d.items()):
        rows.append({'subject_id':sid,**x,'p0':float(np.mean(x['p0'])),'p1':float(np.mean(x['p1'])),'p2':float(np.mean(x['p2']))})
    return rows
def metrics(rows,key):
 y=np.array([r['label'] for r in rows]); p=np.array([r[key] for r in rows]); pr=(p>=.5).astype(int)
 return {'auc':float(roc_auc_score(y,p)),'acc':float(accuracy_score(y,pr)),'ba':float(balanced_accuracy_score(y,pr)),'f1':float(f1_score(y,pr))}
def bootstrap(rows,a,b,B=5000,seed=260918):
 y=np.array([r['label'] for r in rows]); x=np.array([r[a] for r in rows]); z=np.array([r[b] for r in rows]); rng=np.random.default_rng(seed); vals=[]
 for _ in range(B):
  ix=rng.integers(0,len(y),len(y))
  if len(np.unique(y[ix]))<2: continue
  vals.append(roc_auc_score(y[ix],x[ix])-roc_auc_score(y[ix],z[ix]))
 return {'point':float(roc_auc_score(y,x)-roc_auc_score(y,z)),'ci95':[float(np.quantile(vals,.025)),float(np.quantile(vals,.975))],'reps':len(vals)}
def main():
 result={'model':'parisot','protocol':'P0-A0/P1-R1-C/P2-R2-Q','split_seeds':{}}
 allrows=[]
 for ss in (1024,2024,2025):
  rows=load_regime(ss); allrows.extend(rows)
  result['split_seeds'][str(ss)]={'n':len(rows),'P0':metrics(rows,'p0'),'P1':metrics(rows,'p1'),'P2':metrics(rows,'p2'),'P0-P1':bootstrap(rows,'p0','p1',seed=ss),'P1-P2':bootstrap(rows,'p1','p2',seed=ss+1),'P0-P2':bootstrap(rows,'p0','p2',seed=ss+2),'CIS_P1_P2_mean':float(np.mean([abs(r['p1']-r['p2']) for r in rows])),'CIS_P1_P2_flip':float(np.mean([(r['p1']>=.5)!=(r['p2']>=.5) for r in rows]))}
 result['all_split_rows']=len(allrows); result['split_mean']={k:float(np.mean([result['split_seeds'][str(ss)][k]['auc'] for ss in (1024,2024,2025)])) for k in ('P0','P1','P2')}
 (OUT/'parisot_regime_summary.json').write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
if __name__=='__main__': main()
