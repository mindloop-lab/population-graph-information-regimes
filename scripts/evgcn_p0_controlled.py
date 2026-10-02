#!/usr/bin/env python3
import argparse,csv,hashlib,json,sys,time
from collections import defaultdict
from pathlib import Path
import numpy as np,torch
from scipy.io import loadmat
from sklearn.feature_selection import SelectKBest,f_classif
from sklearn.metrics import roc_auc_score,roc_curve
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit.models.ev_gcn_adapter import ControlledEVGCN
def vec(root,sid):
 m=np.asarray(loadmat(root/'subjects'/sid/f'{sid}_cc200_correlation.mat')['correlation'],dtype=np.float32); return m[np.triu_indices(m.shape[0],1)]
def roles(split,ss,fold):
 by=defaultdict(list); lab={}
 for r in csv.DictReader(split.open(newline='',encoding='utf-8')):
  if int(r['split_seed'])==ss and int(r['outer_fold'])==fold: by[r['role']].append(r['subject_id']); lab[r['subject_id']]=int(r['label'])
 return {k:sorted(v) for k,v in by.items()},lab
def threshold(y,p):
 f,t,x=roc_curve(y,p); z=[(float(b-a),-abs(float(c)-.5),-float(c)) for a,b,c in zip(f,t,x) if np.isfinite(c)]; return -max(z)[2] if z else .5
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--data-root',type=Path,required=True); ap.add_argument('--split-registry',type=Path,required=True); ap.add_argument('--upstream',type=Path,required=True); ap.add_argument('--split-seed',type=int,required=True); ap.add_argument('--fold',type=int,required=True); ap.add_argument('--train-seed',type=int,required=True); ap.add_argument('--device',default='cuda:1'); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--checkpoint',type=Path,required=True); a=ap.parse_args(); t0=time.time(); dev=torch.device(a.device if torch.cuda.is_available() else 'cpu'); by,lab=roles(a.split_registry,a.split_seed,a.fold); F,V,Q=by['fit'],by['validation'],by['query']; ids=sorted(set(F)|set(V)|set(Q)); idx={s:i for i,s in enumerate(ids)}; man={r['SUB_ID']:r for r in csv.DictReader((a.data_root/'metadata/cohort_manifest.csv').open(newline='',encoding='utf-8-sig'))}; X=np.stack([vec(a.data_root,s) for s in ids]).astype(np.float64); y=np.array([lab[s] for s in ids]); fi=[idx[s] for s in F]; vi=[idx[s] for s in V]; qi=[idx[s] for s in Q]
 sel=SelectKBest(f_classif,k=min(2000,X.shape[1])).fit(X[fi],y[fi]); Xs=sel.transform(X); rs=Xs.sum(1); Xn=Xs*np.where(np.isfinite(1./rs),1./rs,0.)[:,None]; site_names=np.array([man[s]['SITE_ID'].strip() for s in ids]); site_code={s:i for i,s in enumerate(sorted(set(site_names)))}; sites=np.array([site_code[s] for s in site_names]); sex=np.array([int(float(man[s]['SEX'])) for s in ids]); age=np.array([float(man[s]['AGE_AT_SCAN']) for s in ids]); ph=np.column_stack([sites,sex,age]).astype(np.float64)
 Xc=Xn-Xn.mean(1,keepdims=True); Xcn=Xc/np.linalg.norm(Xc,axis=1,keepdims=True); D=np.clip(1.-Xcn@Xcn.T,0.,2.); cache={}
 def graph(nodes):
  d=D[np.ix_(nodes,nodes)]; n=len(nodes); ui,uj=cache.setdefault(n,np.triu_indices(n,1)); ni=ph[nodes]; phen=(ni[ui,1]==ni[uj,1]).astype(np.int8)+(ni[ui,0]==ni[uj,0]).astype(np.int8); sig=float(np.mean(d)); keep=np.exp(-(d[ui,uj]**2)/(2*sig**2))*phen>1.1; ei,ej=ui[keep],uj[keep]; ei=np.vstack([np.concatenate([ei,ej]),np.concatenate([ej,ei])]); ea=np.concatenate([np.concatenate([ni[ei[0,:len(ei[0])//2]],ni[ei[1,:len(ei[1])//2]]],axis=1) if False else np.zeros((0,6))],axis=0) if False else None
  e1=np.concatenate([ni[ui[keep]],ni[uj[keep]]],axis=1); e2=np.concatenate([ni[uj[keep]],ni[ui[keep]]],axis=1); ea=np.concatenate([e1,e2],axis=0).astype(np.float32); ea=(ea-ea.mean(0))/(ea.std(0)+1e-12); return torch.as_tensor(ei,dtype=torch.long,device=dev),torch.as_tensor(ea,dtype=torch.float32,device=dev)
 torch.manual_seed(a.train_seed); np.random.seed(a.train_seed); model=ControlledEVGCN(a.upstream,input_dim=Xn.shape[1],num_classes=2,dropout=.2,edgenet_input_dim=6,edge_dropout=0.,hgc=16,lg=4).to(dev); opt=torch.optim.Adam(model.parameters(),lr=.01,weight_decay=5e-5); train_nodes=fi+qi; fpos={v:i for i,v in enumerate(train_nodes)}; ftrain=torch.as_tensor([fpos[i] for i in fi],device=dev); xtrain=torch.as_tensor(Xn[train_nodes],dtype=torch.float32,device=dev); ytrain=torch.as_tensor(y[train_nodes],dtype=torch.long,device=dev); tei,tea=graph(train_nodes)
 def forward(nodes):
  ei,ea=graph(nodes); return model(torch.as_tensor(Xn[nodes],dtype=torch.float32,device=dev),ei,ea)
 best=-np.inf; state=None; stale=0; epdone=0
 for ep in range(1,301):
  model.train(); opt.zero_grad(set_to_none=True); lo,_=model(xtrain,tei,tea); loss=torch.nn.functional.cross_entropy(lo[ftrain],ytrain[ftrain]); loss.backward(); opt.step(); epdone=ep
  if ep==1 or ep%5==0 or ep==300:
   model.eval();
   with torch.no_grad(): vp=[float(forward(fi+[v])[-1].softmax(-1)[1].cpu()) for v in vi]
   auc=roc_auc_score(y[vi],vp)
   if auc>best+1e-9: best=auc; state={k:t.detach().cpu().clone() for k,t in model.state_dict().items()}; stale=0
   else: stale+=1
   if stale>=20: break
 model.load_state_dict(state); model.eval();
 with torch.no_grad(): logits,_=forward(train_nodes); p=[float(logits[fpos[i]].softmax(-1)[1].cpu()) for i in qi]
 rows=[{'model':'evgcn','regime':'P0-A0','split_seed':a.split_seed,'subject_id':s,'label':lab[s],'site':man[s]['SITE_ID'].strip(),'p_r0':round(v,8)} for s,v in zip(Q,p)]; a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps({'status':'PASS','regime':'P0-A0','split_seed':a.split_seed,'fold':a.fold,'train_seed':a.train_seed,'n_fit':len(F),'n_validation':len(V),'n_query':len(Q),'epochs':epdone,'best_val_auc':float(best),'device':str(dev),'elapsed_seconds':round(time.time()-t0,1),'rows':rows},indent=2)+'\n'); a.checkpoint.parent.mkdir(parents=True,exist_ok=True); torch.save({'model_state_dict':{k:t.detach().cpu() for k,t in model.state_dict().items()}},a.checkpoint); print(json.dumps({'fold':a.fold,'train_seed':a.train_seed,'device':str(dev),'epochs':epdone,'best_val_auc':float(best),'elapsed_seconds':round(time.time()-t0,1)}),flush=True)
if __name__=='__main__': main()
