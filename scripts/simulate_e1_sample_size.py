"""Pre-freeze design simulation from cached k=3 eligible-count proxies; no API calls."""
import argparse,json
from pathlib import Path
from collections import defaultdict
import numpy as np

def cached_design():
 m=json.loads(Path('rebuttal/pilots/20261108_preflight/id_manifest.json').read_text());held=set(m['e1_held_out']);rows=[]
 runs={'MQ':['run_qwen235b_musique','run_musique_gpt4omini','run_musique_gemma31b'],
       'SB':['run_qwen235b_n5','run_qwen235b_n10','run_gpt4omini_n5','run_gpt4omini_n10','run_gemma31b_n5','run_gemma31b_n10']}
 partial=set();dist=json.loads(Path('results/distortion_audit_relay/distortion_results.json').read_text())
 for r in dist['records']:
  if r['protocol']=='score_ranked_relay' and r['label']=='PARTIAL':partial.add(r['inst_id'])
 for bench,names in runs.items():
  for name in names:
   rs=json.loads(Path('results',name,'audit_metrics.json').read_text())['audit_records']['score_ranked_relay']
   for r in rs:
    if r['inst_id'] in held:
     rows.append({'instance_id':r['inst_id'],'benchmark':bench,'model':name,'wrong':not r['correct'],
        'lost_proxy':r['crit_recall']<1,'known_partial_proxy':('qwen235b' in name and r['inst_id'] in partial)})
 return rows

def design(rows,bench,exclude_known_partial=True):
 rs=[r for r in rows if bench=='pooled' or r['benchmark']==bench];ids=sorted({r['instance_id'] for r in rs})
 eligible=[r for r in rs if r['wrong'] and not(exclude_known_partial and r['known_partial_proxy'])]
 counts=[sum(r['instance_id']==i for r in eligible) for i in ids]
 p=sum(r['lost_proxy'] for r in eligible)/len(eligible) if eligible else 0
 return ids,counts,p,{'instances':len(ids),'all_traces':len(rs),'wrong_before_exclusions':sum(r['wrong'] for r in rs),
    'known_partial_trace_proxy':sum(r['wrong'] and r['known_partial_proxy'] for r in rs),'eligible_proxy':len(eligible),'lost_proxy':sum(r['lost_proxy'] for r in eligible),'unused_proxy':sum(not r['lost_proxy'] for r in eligible)}

def trial(n,counts,p,kappa,accuracy,icc,rng,draws=2000):
 # Both annotators have marginal p; joint table has the specified population κ.
 probabilities=[(1-p)**2+kappa*p*(1-p),p*(1-p)*(1-kappa),p*(1-p)*(1-kappa),p*p+kappa*p*(1-p)]
 panel=np.zeros((n,6),dtype=float)
 for i in range(n):
  c=int(counts[i%len(counts)]);shared=rng.random()<icc
  categories=np.repeat(rng.choice(4,p=probabilities),c) if shared else rng.choice(4,size=c,p=probabilities)
  for x in categories:panel[i,x]+=1
  correct=int(rng.random()<accuracy)*c if shared else rng.binomial(c,accuracy)
  panel[i,4]=correct;panel[i,5]=c
 # Exactly the prereg cluster bootstrap: sample n instances with replacement and
 # retain every eligible model row. Multinomial weights are algebraically equivalent.
 weights=rng.multinomial(n,np.repeat(1/n,n),size=draws);total=weights@panel
 den=total[:,:4].sum(1);safe=np.where(den>0,den,np.nan)
 pa=(total[:,2]+total[:,3])/safe;pb=(total[:,1]+total[:,3])/safe
 pe=pa*pb+(1-pa)*(1-pb);po=(total[:,0]+total[:,3])/safe
 with np.errstate(divide='ignore',invalid='ignore'):
  k=(po-pe)/(1-pe);acc=total[:,4]/np.where(total[:,5]>0,total[:,5],np.nan)
 kv=k[np.isfinite(k)];av=acc[np.isfinite(acc)]
 return (bool(len(kv)>0 and np.quantile(kv,.025)>=.6),bool(len(av)>0 and np.quantile(av,.025)>=.8))

def main():
 p=argparse.ArgumentParser();p.add_argument('--simulations',type=int,default=300);a=p.parse_args();rng=np.random.default_rng(42)
 rows=cached_design();out={'seed':42,'simulations_per_cell':a.simulations,'bootstrap_draws':2000,'assumptions':
 'Cached k3 lexical labels are count/prevalence PROXIES, not human labels. Exclude Qwen SB traces with any cached PARTIAL as conservative proxy; other partial/uncertain unknown. True class prevalence varied separately; ICC mixture0.25 primary,0/0.5 sensitivity. No eligibility or human labels manufactured.', 'designs':{},'power':[],'required_instances':[]}
 for bench in ['MQ','SB','pooled']:
  ids,counts,p0,summary=design(rows,bench);out['designs'][bench]=summary|{'lost_fraction':p0}
  for k in [.70,.75,.80]:
   for acc in [.85,.90]:
    vals=[trial(len(ids),counts,p0,k,acc,.25,rng) for _ in range(a.simulations)]
    out['power'].append({'benchmark':bench,'instances':len(ids),'p_lost':p0,'human_kappa':k,'accuracy':acc,'icc':.25,
       'prob_kappa_lower_clears':float(np.mean([v[0] for v in vals])),'prob_accuracy_lower_clears':float(np.mean([v[1] for v in vals])),'prob_both_clear':float(np.mean([v[0] and v[1] for v in vals]))})
  # MQ all-one-class proxy is not identifiable; add plausible semantic splits.
  prevalences=[p0] if p0>0 else [.05,.10,.20]
  for prevalence in prevalences:
   for acc in [.85,.90]:
    needed=None;last=None
    for n in [len(ids),80,120,180,240,360,480,720]:
     if n<len(ids):continue
     vals=[trial(n,counts,prevalence,.75,acc,.25,rng) for _ in range(max(100,a.simulations//2))]
     pk=float(np.mean([v[0] for v in vals]));pa=float(np.mean([v[1] for v in vals]));joint=float(np.mean([v[0] and v[1] for v in vals]));last={'n':n,'kappa_power':pk,'accuracy_power':pa,'joint_power':joint}
     if joint>=.8:needed=n;break
    extra=max(0,(needed or last['n'])-len(ids))
    # Original per-trace times, three model traces, double annotation; excludes extra fact/adjudication overhead.
    h_per_instance=(7 if bench=='MQ' else 20 if bench=='SB' else (45*7+15*20)/60)*3*2/60
    out['required_instances'].append({'benchmark':bench,'p_lost':prevalence,'kappa':.75,'accuracy':acc,'needed_grid_instances':needed,
       'last_grid':last,'extra_label_hours_lower_bound':extra*h_per_instance,'extra_total_annotation_hours':extra*(h_per_instance+.4+.15),'basis':'6 trace-passes/instance plus2x12min fact specification and12/80h adjudication per added instance; joint power>=80% coarse grid'})
  for icc in [0,.5]:
   vals=[trial(len(ids),counts,p0,.75,.90,icc,rng) for _ in range(a.simulations)]
   out['power'].append({'benchmark':bench,'instances':len(ids),'p_lost':p0,'human_kappa':.75,'accuracy':.90,'icc':icc,
     'prob_kappa_lower_clears':float(np.mean([v[0] for v in vals])),'prob_accuracy_lower_clears':float(np.mean([v[1] for v in vals])),'prob_both_clear':float(np.mean([v[0] and v[1] for v in vals]))})
  Path('rebuttal/pilots/20261108_preflight/e1_power_partial.json').write_text(json.dumps(out,indent=2)+'\n');print(bench,summary,flush=True)
 out['cached_rows']=rows
 Path('rebuttal/pilots/20261108_preflight/e1_power.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
