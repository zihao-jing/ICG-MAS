"""N80-only AC1 precision supplement, no inference calls."""
import json
from pathlib import Path
import numpy as np
from scripts.simulate_e1_interval_width import simulate
P=Path('rebuttal/pilots/20261108_review4')
def main():
 d=json.loads((P/'e1_n80_design.json').read_text());base={r['instance_id']:r for r in d['rows']};rows=[dict(base[i],weight=s['weight']) for h,s in d['designs']['80']['strata'].items() for i in s['ids']];rng=np.random.default_rng(42);out=[]
 for prevalence in [.85,.95]:
  for k in [.7,.75,.8]:
   for accuracy in [.85,.9]:
    values=[simulate(rows,'fidelity',k,accuracy,rng,fidelity_p=prevalence,include_ac1=True) for _ in range(200)]
    out.append({'faithful_fraction':prevalence,'true_kappa':k,'true_accuracy':accuracy,'kappa_half_width':float(np.mean([v[0] for v in values if v[0] is not None])),'accuracy_half_width':float(np.mean([v[1] for v in values])),'ac1_half_width':float(np.mean([v[2] for v in values]))})
 (P/'e1_n80_ac1_width.json').write_text(json.dumps({'N':80,'ICC':.25,'panels':200,'bootstrap_draws':2000,'categories':['absent','faithful','partial','distorted'],'rows':out},indent=2)+'\n');print('complete',flush=True)
if __name__=='__main__':main()
