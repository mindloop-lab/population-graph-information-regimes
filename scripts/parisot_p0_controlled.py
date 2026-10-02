#!/usr/bin/env python3
"""Parisot P0/A0 corrected-transductive cell on the locked 871-subject data."""
from __future__ import annotations
import argparse,csv,hashlib,json,sys,time
from collections import defaultdict
from pathlib import Path
import numpy as np, torch
from scipy.io import loadmat
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import eigsh
from sklearn.feature_selection import SelectKBest,f_classif
from sklearn.metrics import roc_auc_score,roc_curve
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from audit.models.parisot_adapter import ParisotDeepGCN
def vec(root,sid):
 m=np.asarray(loadmat(root/'subjects'/sid/(f'{sid}_cc200_correlation.mat'))['correlation'],dtype=np.float32); return m[np.triu_indices(m.shape[0],1)]
def roles(split,ss,fold):
 by=defaultdict(list); lab={}
 for r in csv.DictReader(split.open(newline='',encoding='utf-8')):
  if int(r['split_seed'])==ss and int(r['outer_fold'])==fold: by[r['role']].append(r['subject_id']); lab[r['subject_id']]=int(r['label'])
 return {k:sorted(v) for k,v in by.items()},lab
def norm(a):
 d=a.sum(1); di=np.where(d>0,d**-.5,0.); return (a*di[:,None])*di[None,:]
def thr(y,p):
 f,t,x=roc_curve(y,p); z=[(float(b-a),-abs(float(c)-.5),-float(c)) for a,b,c in zip(f,t,x) if np.isfinite(c)]; return -max(z)[2] if z else .5
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--data-root',type=Path,required=True); ap.add_argument('--split-registry',type=Path,required=True); ap.add_argument('--split-seed',type=int,required=True); ap.add_argument('--fold',type=int,required=True); ap.add_argument('--train-seed',type=int,required=True); ap.add_argument('--device',default='cuda:1'); ap.add_argument('--features',type=int,default=2000); ap.add_argument('--max-epochs',type=int,default=200); ap.add_argument('--val-every',type=int,default=10); ap.add_argument('--patience',type=int,default=12); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--checkpoint',type=Path,required=True); args=ap.parse_args()
 t0=time.time(); dev=torch.device(args.device if torch.cuda.is_available() else 'cpu'); by,lab=roles(args.split_registry,args.split_seed,args.fold); F,V,Q=by['fit'],by['validation'],by['query']; all_ids=sorted(set(F)|set(V)|set(Q)); idx={s:i for i,s in enumerate(all_ids)}; man={r['SUB_ID']:r for r in csv.DictReader((args.data_root/'metadata/cohort_manifest.csv').open(newline='',encoding='utf-8-sig'))}; X=np.stack([vec(args.data_root,s) for s in all_ids]).astype(np.float64); y=np.array([lab[s] for s in all_ids]); fi=[idx[s] for s in F]; qi=[idx[s] for s in Q]; vi=[idx[s] for s in V]
 sel=SelectKBest(f_classif,k=min(args.features,X.shape[1])).fit(X[fi],y[fi]); Xs=sel.transform(X); rs=Xs.sum(1); Xn=Xs*np.where(np.isfinite(1./rs),1./rs,0.)[:,None]; sex=np.array([int(float(man[s]['SEX'])) for s in all_ids]); sites=np.array([man[s]['SITE_ID'].strip() for s in all_ids]); pa=(sex[:,None]==sex[None,:]).astype(float)+(sites[:,None]==sites[None,:]).astype(float); xc=Xn-Xn.mean(1,keepdims=True); xn=xc/np.linalg.norm(xc,axis=1,keepdims=True); D=np.clip(1.-xn@xn.T,0.,2.); sigma=float(np.mean(D)); adj=pa*np.exp(-(D**2)/(2*sigma**2)); an=norm(adj); lmax=float(eigsh(csr_matrix(np.eye(len(all_ids))-an),1,which='LM')[0][0])
 def supports(nodes):
  a=norm(adj[np.ix_(nodes,nodes)]); s=(2./lmax)*(np.eye(len(nodes))-a)-np.eye(len(nodes)); ts=[np.eye(len(nodes)),s]
  for _ in range(2,4): ts.append(2.*(s@ts[-1])-ts[-2])
  return [torch.as_tensor(z,dtype=torch.float32,device=dev) for z in ts]
 torch.manual_seed(args.train_seed); np.random.seed(args.train_seed); model=ParisotDeepGCN(Xn.shape[1],16,2,2,4).to(dev); opt=torch.optim.Adam(model.parameters(),lr=.005,weight_decay=5e-4); train_nodes=fi+qi; sup_train=supports(train_nodes); xtrain=torch.as_tensor(Xn[train_nodes],dtype=torch.float32,device=dev); ytrain=torch.as_tensor(y[train_nodes],dtype=torch.long,device=dev); fpos={v:i for i,v in enumerate(train_nodes)}; ftrain=torch.as_tensor([fpos[i] for i in fi],dtype=torch.long,device=dev)
 def forward(nodes): return model(torch.as_tensor(Xn[nodes],dtype=torch.float32,device=dev),supports(nodes))
 best=-np.inf; state=None; stale=0; epdone=0
 for ep in range(1,args.max_epochs+1):
  model.train(); opt.zero_grad(set_to_none=True); lo=model(xtrain,sup_train); loss=torch.nn.functional.cross_entropy(lo[ftrain],ytrain[ftrain]); loss.backward(); opt.step(); epdone=ep
  if ep==1 or ep%args.val_every==0 or ep==args.max_epochs:
   model.eval();
   with torch.no_grad(): vp=[float(forward(fi+[idx[v]])[-1].softmax(-1)[1].cpu()) for v in V]
   auc=roc_auc_score(y[vi],vp)
   if auc>best+1e-9: best=auc; state={k:t.detach().cpu().clone() for k,t in model.state_dict().items()}; stale=0
   else: stale+=1
   if stale>=args.patience: break
 model.load_state_dict(state); model.eval();
 with torch.no_grad(): p=[float(forward(train_nodes)[fpos[i]].softmax(-1)[1].cpu()) for i in qi]
 threshold=thr(y[qi],p) if len(set(y[qi]))>1 else .5; rows=[{'model':'parisot','regime':'P0-A0','split_seed':args.split_seed,'subject_id':s,'label':lab[s],'p_r0':round(float(v),8),'site':man[s]['SITE_ID'].strip()} for s,v in zip(Q,p)]
 args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(json.dumps({'status':'PASS','regime':'P0-A0','split_seed':args.split_seed,'fold':args.fold,'train_seed':args.train_seed,'n_fit':len(F),'n_validation':len(V),'n_query':len(Q),'epochs':epdone,'best_val_auc':float(best),'threshold':threshold,'sigma':sigma,'device':str(dev),'elapsed_seconds':round(time.time()-t0,1),'rows':rows},indent=2)+'\n'); args.checkpoint.parent.mkdir(parents=True,exist_ok=True); torch.save({'model_state_dict':{k:t.detach().cpu() for k,t in model.state_dict().items()},'threshold':threshold},args.checkpoint); print(json.dumps({'split_seed':args.split_seed,'fold':args.fold,'train_seed':args.train_seed,'device':str(dev),'epochs':epdone,'best_val_auc':float(best),'elapsed_seconds':round(time.time()-t0,1)}),flush=True)
if __name__=='__main__': main()
