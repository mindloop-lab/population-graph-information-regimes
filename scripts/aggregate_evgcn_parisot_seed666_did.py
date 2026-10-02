#!/usr/bin/env python3
import json
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score
BASE=Path(__file__).resolve().parents[1]; OUT=BASE/'results/architecture_interaction_seed666'
def load_dir(path,prefix):
 d={}
 for fold in range(5):
  for ts in (11,22,33):
   q=json.loads((path/f'{prefix}_{fold}_{ts}.json').read_text())
   for r in q['rows']:
    x=d.setdefault(r['subject_id'],{'label':r['label'],'site':r.get('site','')})
    for k in ('p_r0','p_r1','p_r2'):
     if k in r: x.setdefault(k,[]).append(float(r[k]))
 return {s:{**x,**{k:float(np.mean(v)) for k,v in x.items() if isinstance(v,list)}} for s,x in d.items()}
def auc(y,p): return roc_auc_score(y,p)
def boot(y,ev,pa,sites,kind,B=10000,seed=260919):
 rng=np.random.default_rng(seed); vals=[]; groups=sorted(set(sites)); gix=[np.flatnonzero(sites==g) for g in groups]
 for _ in range(B):
  if kind=='subject': ix=rng.integers(0,len(y),len(y))
  else: ix=np.concatenate([gix[j] for j in rng.integers(0,len(gix),len(gix))])
  if len(np.unique(y[ix]))<2: continue
  vals.append((auc(y[ix],ev[0][ix])-auc(y[ix],ev[1][ix]))-(auc(y[ix],pa[0][ix])-auc(y[ix],pa[1][ix])))
 return {'point':float((auc(y,ev[0])-auc(y,ev[1]))-(auc(y,pa[0])-auc(y,pa[1]))),'ci95':[float(np.quantile(vals,.025)),float(np.quantile(vals,.975))],'reps':len(vals)}
def main():
 ev0=load_dir(BASE/'results/evgcn_p0_seed666','ev_p0_666'); ev12=load_dir(BASE/'results/evgcn_seed666','ev_666'); pa0=load_dir(BASE/'results/parisot_p0_seed666','pa_666'); pa12=load_dir(BASE/'results/parisot_seed666','pa_666'); ids=sorted(set(ev0)&set(ev12)&set(pa0)&set(pa12)); assert len(ids)==871,(len(ids),len(ev0),len(ev12),len(pa0),len(pa12)); y=np.array([ev0[s]['label'] for s in ids]); sites=np.array([ev0[s]['site'] for s in ids]); E0=np.array([ev0[s]['p_r0'] for s in ids]); E1=np.array([ev12[s]['p_r1'] for s in ids]); E2=np.array([ev12[s]['p_r2'] for s in ids]); P0=np.array([pa0[s]['p_r0'] for s in ids]); P1=np.array([pa12[s]['p_r1'] for s in ids]); P2=np.array([pa12[s]['p_r2'] for s in ids]);
 out={'n_subjects':len(ids),'sites':len(set(sites)),'models':{
  'evgcn':{'P0':float(auc(y,E0)),'P1':float(auc(y,E1)),'P2':float(auc(y,E2)),'CIS_P1_P2':float(np.mean(np.abs(E1-E2))),'flip_P1_P2':float(np.mean((E1>=.5)!=(E2>=.5)))},
  'parisot':{'P0':float(auc(y,P0)),'P1':float(auc(y,P1)),'P2':float(auc(y,P2)),'CIS_P1_P2':float(np.mean(np.abs(P1-P2))),'flip_P1_P2':float(np.mean((P1>=.5)!=(P2>=.5)))}
 }}
 out['interaction']={'train_P0_minus_P1':{'subject':boot(y,(E0,E1),(P0,P1),sites,'subject',seed=260919),'site':boot(y,(E0,E1),(P0,P1),sites,'site',seed=260920)},'query_P1_minus_P2':{'subject':boot(y,(E1,E2),(P1,P2),sites,'subject',seed=260921),'site':boot(y,(E1,E2),(P1,P2),sites,'site',seed=260922)}}
 OUT.mkdir(parents=True,exist_ok=True); (OUT/'summary.json').write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2))
if __name__=='__main__': main()
