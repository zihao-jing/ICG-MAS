"""CI half-widths for the E1 anchor (N=30) beside N=80, same simulator and seed. No model outcomes."""
import json
from pathlib import Path
import numpy as np
from scripts.simulate_e1_interval_width import simulate
P=Path('rebuttal/pilots');OUT=P/'20261108_review7'
def main(sims=200):
 d=json.loads((P/'20261108_review3/e1_stratified_design.json').read_text());base={r['instance_id']:r for r in d['rows']}
 anchor=json.loads((OUT/'e1_anchor_locked_manifest.json').read_text());rng=np.random.default_rng(42);result=[]
 designs={'80':[dict(base[i],weight=s['weight']) for s in d['designs']['80']['strata'].values() for i in s['ids']],
          '30_anchor':[dict(base[i],weight=s['weight'],stratum=h) for h,s in anchor['strata'].items() for i in s['ids']]}
 frame=[r for r in base.values() if not r['is_dev']];p=sum(r['proxy_present'] for r in frame)/sum(r['proxy_facts'] for r in frame);wrong=[r for r in frame if not r['correct']];lost=sum(r['lexical_cr']<1 for r in wrong)/len(wrong)
 for label,rows in designs.items():
  for r in rows:r['fact_presence_p']=p;r['trace_lost_p']=lost
  for metric in ['presence','fidelity']:
   for fp in ([.85,.95] if metric=='fidelity' else [.95]):
    for k in [.70,.75,.80]:
     for acc in [.85,.90]:
      vals=[simulate(rows,metric,k,acc,rng,fidelity_p=fp,include_ac1=(metric=='fidelity')) for _ in range(sims)]
      cols=range(3 if metric=='fidelity' else 2)
      m=[float(np.mean([v[j] for v in vals if v[j] is not None])) for j in cols]
      result.append({'design':label,'metric':metric,'faithful_fraction_assumption':fp if metric=='fidelity' else None,'true_kappa':k,'true_accuracy':acc,'kappa_half_width':m[0],'accuracy_half_width':m[1],'ac1_half_width':m[2] if metric=='fidelity' else None})
  print(label,'done',flush=True)
 (OUT/'e1_anchor_ci_widths.json').write_text(json.dumps({'simulations':sims,'bootstrap_draws':2000,'ICC':.25,'seed':42,'rows':result},indent=1)+'\n')
if __name__=='__main__':main()
