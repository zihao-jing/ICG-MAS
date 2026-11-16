"""Pre-register the E2 wave-1 spot-check draw (12 items, 3 per fault type). Verdict-blind: no judge, matcher or outcome input.

Item pool: evidence types (extraction omission, selection omission, distortion) = every (base trace, candidate agent);
aggregation = every base trace. Order: ascending SHA-256 of canonical JSON ["E2-spot-v2", 42, fault_type, item_key],
item_key as tie-break; first 3 per type. One author per ITEM by position in the combined SHA order modulo 4 (A,B,C,D).
"""
import json
from pathlib import Path
from src.audit.pilot_common import digest,freeze
P=Path('rebuttal/pilots');O=Path('rebuttal/annotation/author_packet_20261108');OUT=P/'20261108_review8'
TYPES=['extraction_omission','selection_omission','distortion','aggregation']
def pool():
 base={}
 for f in ['E2A_screening.jsonl','E2A_screening_supplement_wave1.jsonl']:
  for s in (O/f).read_text().splitlines():
   r=json.loads(s);base.setdefault(r['item_id'],r['candidate_agent_ids'])
 return base
def main():
 base=pool();assert len(base)==68
 items=[]
 for t in TYPES:
  keys=[(f'{i}:{a}',i,a) for i,ags in sorted(base.items()) for a in ags] if t!='aggregation' else [(i,i,None) for i in sorted(base)]
  keys.sort(key=lambda k:(digest(['E2-spot-v2',42,t,k[0]]),k[0]))
  items+=[{'fault_type':t,'item_key':k[0],'trace_id':k[1],'target_agent':k[2],'pool_size':len(keys)} for k in keys[:3]]
 order=sorted(items,key=lambda r:(digest(['E2-spot-v2',42,'order',r['fault_type'],r['item_key']]),r['item_key']))
 for n,r in enumerate(order):r['author']='ABCD'[n%4];r['position']=n+1
 out={'rule':__doc__.strip(),'wave1_items':order,'items_sha256':digest(order),'wave2_rule':'8 items (2 per fault type): among injections made on wave-1 spot items that the gate passed (judge and author both defect-free), first 2 per fault type by ascending SHA-256 of ["E2-spot-v2", 42, "wave2", fault_type, item_key]; fewer than 2 passed in a type -> take all, report shortfall, no redistribution; author = position in combined wave-2 SHA order modulo 4.'}
 freeze(OUT/'e2_spotcheck_wave1_manifest.json',out)
 print(out['items_sha256']);[print(r['position'],r['author'],r['fault_type'],r['item_key'][:12],r['target_agent']) for r in order]
if __name__=='__main__':main()
