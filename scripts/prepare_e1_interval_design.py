"""Draft lexical-only stratified designs; no model calls or annotation export."""
import json
from pathlib import Path
from collections import defaultdict
from src.audit.critical_fact_validation import build_trace_packages
from src.audit.pilot_common import digest,freeze
from scripts.exp_rebuttal_threshold import best_similarity
P=Path('rebuttal/pilots');OUT=P/'20261108_review3'
def allocate(groups,n):
 counts={k:0 for k in groups}
 while sum(counts.values())<n:
  for k in sorted(groups):
   if sum(counts.values())==n:break
   if counts[k]<len(groups[k]):counts[k]+=1
 return counts

def main():
 old=json.loads((P/'20261108_preflight/id_manifest.json').read_text());dev=set(old['e1_dev']);rows=[]
 for bench,run,na in [('MQ','run_qwen235b_musique',None),('SB','run_qwen235b_n5',5),('SB','run_qwen235b_n10',10)]:
  ts=build_trace_packages(dataset='musique' if bench=='MQ' else 'silobench',run_dir='results/'+run,protocol='score_ranked_relay',source_id=run,n_agents=na)
  for t in ts:
   ids=t['instance_id'];gold=t['source_supports'];units=[u['text'] for u in t['checkpoints']['board']]
   presence=[best_similarity(g['text'],units)>.5 for g in gold];cr=sum(presence)/len(presence)
   rows.append({'instance_id':ids,'benchmark':bench,'stratum':bench+'/'+('zero' if cr==0 else 'complete' if cr==1 else 'partial'),'tau':.5,'lexical_cr':cr,'proxy_facts':len(presence),'proxy_present':sum(presence),'is_dev':ids in dev,'correct':t['answer_correct']})
 groups=defaultdict(list)
 for r in rows:
  if not r['is_dev']:groups[r['stratum']].append(r['instance_id'])
 groups={k:sorted(v,key=lambda i:(digest(['E1-lexical-v3',42,k,i]),i)) for k,v in sorted(groups.items())}
 designs={}
 for n in [60,80,100]:
  counts={}
  for b,nb in [('MQ',3*n//4),('SB',n//4)]:counts.update(allocate({k:v for k,v in groups.items() if k.startswith(b)},nb))
  designs[str(n)]={'size':n,'strata':{k:{'population':len(v),'target':counts[k],'pi':counts[k]/len(v),'weight':len(v)/counts[k],'ids':v[:counts[k]]} for k,v in groups.items()}}
 out={'status':'planned, pending author confirmation; NOT active draw','population_excludes':'20 fixed dev IDs; pilots/calibration outside final population','order':'ascending SHA256 canonical JSON ["E1-lexical-v3",42,stratum,instance_id], ID tie-break','strata':'benchmark × Qwen cached k=3 lexical coverage at strict similarity >0.5: zero, partial (0<CR<1), complete; no correctness or matcher output used','allocation':'75% MQ/25% SB; round-robin equal allocation among nonempty lexical strata, cap at population','weights':'pi_h=n_h/N_h; w_i=1/pi_h=N_h/n_h; every model/fact of an instance inherits w_i','rows':rows,'ordered_strata':groups,'designs':designs,'old_held_out_ids':old['e1_held_out']}
 freeze(OUT/'e1_stratified_design.json',out)
 print({k:len(v) for k,v in groups.items()})
if __name__=='__main__':main()
