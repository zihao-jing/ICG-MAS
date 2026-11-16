"""Weighted, stratified cluster-bootstrap CI-width planning. No model outcomes."""
import json,argparse
from pathlib import Path
import numpy as np
P=Path('rebuttal/pilots/20261108_review3')
def simulate(rows,metric,kappa,accuracy,rng,draws=2000,fidelity_p=.95,include_ac1=False):
 # Generate paired categorical labels with fixed marginal and target kappa.
 # ICC .25: each cluster is shared with probability .25, otherwise iid within instance.
 panel=[];strata=[];weights=[]
 groups={h:[r for r in rows if r['stratum']==h] for h in sorted({r['stratum'] for r in rows})}
 # pooled within-benchmark lexical split, avoiding deterministic classes inside strata.
 for r in rows:
  if metric=='trace':n=0 if r['correct'] else 3;p=r['trace_lost_p'];probs=[1-p,p]
  elif metric=='presence':n=3*r['proxy_facts'];p=r['fact_presence_p'];probs=[1-p,p]
  else:n=3*r['proxy_present'];probs=[fidelity_p,(1-fidelity_p)*.9,(1-fidelity_p)*.1]
  c=len(probs)
  local=([float(r['lexical_cr']==1),float(r['lexical_cr']<1)] if metric=='trace' else [1-r['lexical_cr'],r['lexical_cr']] if metric=='presence' else probs)
  joint=(1-kappa)*np.outer(local,probs)+kappa*np.diag(local);shared=rng.random()<.25
  categories=np.repeat(rng.choice(c*c,p=joint.flatten()),n) if shared else rng.choice(c*c,size=n,p=joint.flatten())
  counts=np.bincount(categories,minlength=c*c).astype(float);correct=(int(rng.random()<accuracy)*n if shared else rng.binomial(n,accuracy))
  panel.append(np.r_[counts,correct,n]);strata.append(r['stratum']);weights.append(r['weight'])
 panel=np.array(panel)*np.array(weights)[:,None];boot=np.zeros((draws,len(rows)))
 for h in groups:
  idx=np.where(np.array(strata)==h)[0];boot[:,idx]=rng.multinomial(len(idx),np.repeat(1/len(idx),len(idx)),size=draws)
 total=boot@panel;c=2 if metric!='fidelity' else 3;mat=total[:,:c*c].reshape(-1,c,c);den=mat.sum((1,2));safe=np.where(den>0,den,np.nan)
 po=np.trace(mat,axis1=1,axis2=2)/safe;pe=(mat.sum(1)*mat.sum(2)).sum(1)/safe**2
 with np.errstate(invalid='ignore',divide='ignore'):kap=(po-pe)/(1-pe);acc=total[:,-2]/np.where(total[:,-1]>0,total[:,-1],np.nan)
 def half(v):
  v=v[np.isfinite(v)];return float((np.quantile(v,.975)-np.quantile(v,.025))/2) if len(v) else None
 if include_ac1:
  marginal=(mat.sum(1)+mat.sum(2))/(2*safe[:,None]);chance=(marginal*(1-marginal)).sum(1)/3 # four fixed fidelity categories; absent has mass zero here
  ac1=(po-chance)/(1-chance)
  return half(kap),half(acc),half(ac1)
 return half(kap),half(acc)
def main():
 p=argparse.ArgumentParser();p.add_argument('--simulations',type=int,default=200);a=p.parse_args();d=json.loads((P/'e1_stratified_design.json').read_text());rng=np.random.default_rng(42);base={r['instance_id']:r for r in d['rows']};result=[]
 for label in ['original60','60','80','100']:
  rows=[]
  if label=='original60':
   for i in d['old_held_out_ids']:rows.append(dict(base[i],weight=1,stratum=base[i]['benchmark']+'/original'))
  else:
   for h,s in d['designs'][label]['strata'].items():rows.extend(dict(base[i],weight=s['weight']) for i in s['ids'])
  frame=[r for r in base.values() if not r['is_dev']];p=sum(r['proxy_present'] for r in frame)/sum(r['proxy_facts'] for r in frame);wrong=[r for r in frame if not r['correct']];lost=sum(r['lexical_cr']<1 for r in wrong)/len(wrong)
  for r in rows:r['fact_presence_p']=p;r['trace_lost_p']=lost
  for metric in ['presence','fidelity','trace']:
   for fidelity_p in ([.85,.95] if metric=='fidelity' else [.95]):
    for k in [.70,.75,.80]:
     for acc in [.85,.90]:
      vals=[simulate(rows,metric,k,acc,rng,fidelity_p=fidelity_p) for _ in range(a.simulations)]
      valid=[[v[j] for v in vals if v[j] is not None] for j in [0,1]]
      result.append({'design':label,'metric':metric,'true_kappa':k,'true_accuracy':acc,'faithful_fraction_assumption':fidelity_p if metric=='fidelity' else None,'mean_kappa_half_width':float(np.mean(valid[0])) if valid[0] else None,'mean_accuracy_half_width':float(np.mean(valid[1])) if valid[1] else None,'undefined_kappa_fraction':1-len(valid[0])/a.simulations})
  (P/'e1_interval_width_partial.json').write_text(json.dumps(result,indent=2)+'\n');print(label,'complete',flush=True)
 hours={str(n):{'held_out_label_hours':n*(.75*7+.25*20)*3*2/60,'fact_spec_and_adjudication':n*.55,'total_held_out_hours':n*1.575,'extra_vs_60':(n-60)*1.575,'per_annotator':n*1.575/4} for n in [60,80,100]}
 out={'simulations':a.simulations,'bootstrap_draws':2000,'ICC':.25,'seed':42,'assumptions':'3 base traces per instance; one atomic-fact proxy per gold support unit, board checkpoint only (conservative workload). Presence split and trace lost split from Qwen tau=.5 caches with instance-specific lexical marginals and population-weighted second-rater marginals, no matcher. Fidelity conditional on present cannot be identified by lexical labels: faithful .85/.95 sensitivity, remaining mass90%partial10%distorted. Original60 row unweighted design reference. No human labels simulated for use as data. Stratified bootstrap without finite-population correction is conservative. Undefined kappa draws omitted, fraction reported.','hours':hours,'results':result}
 (P/'e1_interval_width.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
