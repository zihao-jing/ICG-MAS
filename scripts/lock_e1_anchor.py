"""Draw the E1 author anchor (about 30 of the locked 80 instances). No model calls, no matcher or judge output.

Rule (pre-registered in E1-v6): allocate 30 across the six locked strata in proportion to n_h (largest remainder,
ties by ascending stratum name); within each stratum take the FIRST n_a IDs of the locked SHA order. Anchor
weight w_i = N_h / n_a (inverse overall inclusion probability n_a / N_h).
"""
import json
from pathlib import Path
from src.audit.pilot_common import digest,freeze
P=Path('rebuttal/pilots');OUT=P/'20261108_review7'
def allocate(sizes,n):
 total=sum(sizes.values());exact={k:v*n/total for k,v in sizes.items()};a={k:int(x) for k,x in exact.items()}
 for k in sorted(sizes,key=lambda k:(-(exact[k]-a[k]),k))[:n-sum(a.values())]:a[k]+=1
 return a
def main():
 lock=json.loads((P/'20261108_review6/e1_n80_locked_manifest.json').read_text())
 alloc=allocate({k:v['n'] for k,v in lock['strata'].items()},30)
 strata={k:{'N_h':v['population'],'n_h_locked':v['n'],'n_anchor':alloc[k],'inclusion_probability_overall':alloc[k]/v['population'],'weight':v['population']/alloc[k],'ids':v['ids'][:alloc[k]]} for k,v in sorted(lock['strata'].items())}
 ids=[i for v in strata.values() for i in v['ids']];assert len(ids)==len(set(ids))==30 and set(ids)<={i for v in lock['strata'].values() for i in v['ids']}
 out={'status':'locked anchor draw (planning default until authors confirm)','size':30,'parent':'rebuttal/pilots/20261108_review6/e1_n80_locked_manifest.json',
  'rule':'30 split in proportion to locked n_h, largest remainder, ties by ascending stratum name; first n_anchor IDs of each stratum in locked SHA order','strata':strata,'id_list_sha256':digest(sorted(ids))}
 freeze(OUT/'e1_anchor_locked_manifest.json',out)
 print({k:(v['n_anchor'],round(v['weight'],4)) for k,v in strata.items()})
if __name__=='__main__':main()
