"""Lock the E1 N=80 held-out draw. Lexical tau=0.5 strata only; no matcher output, no model calls.

Re-derives the stratified draw into a NEW folder (existing results are never overwritten),
checks it against the earlier candidate design, and writes the locked manifest with counts,
SHA order, inclusion probabilities, weights and the ID list.
"""
import json
from pathlib import Path
import scripts.prepare_e1_interval_design as D
from src.audit.pilot_common import digest,freeze
P=Path('rebuttal/pilots');OUT=P/'20261108_review6'
def main():
 D.OUT=OUT/'e1_redraw';D.main()
 new=json.loads((D.OUT/'e1_stratified_design.json').read_text())['designs']['80']
 old=json.loads((P/'20261108_review4/e1_n80_design.json').read_text())['designs']['80']
 assert new['size']==80
 same=all(new['strata'][k]['ids']==old['strata'][k]['ids'] for k in old['strata']) and set(new['strata'])==set(old['strata'])
 assert same,'redraw differs from the earlier candidate design'
 strata={k:{'population':v['population'],'n':v['target'],'inclusion_probability':v['pi'],'weight':v['weight'],'ids':v['ids']} for k,v in sorted(new['strata'].items())}
 assert sum(v['n'] for v in strata.values())==80
 assert sum(v['n'] for k,v in strata.items() if k.startswith('MQ'))==60
 ids=[i for v in strata.values() for i in v['ids']];assert len(ids)==len(set(ids))==80
 lock={'status':'locked 2026-11-08 (authors confirmed N=80)','size':80,
  'strata_rule':'benchmark x cached Qwen k=3 lexical coverage at strict tau=0.5 (zero, partial, complete); no correctness or matcher output',
  'order':'ascending SHA256 canonical JSON ["E1-lexical-v3",42,stratum,instance_id], ID tie-break; first n_h taken',
  'allocation':'60 MQ + 20 SB; equal round-robin within nonempty strata, capped at stratum population',
  'dev_instances_excluded':20,'redraw_identical_to_earlier_candidate':same,'strata':strata,'id_list_sha256':digest(sorted(ids))}
 freeze(OUT/'e1_n80_locked_manifest.json',lock)
 print(json.dumps({k:(v['population'],v['n']) for k,v in strata.items()}),digest(lock))
if __name__=='__main__':main()
