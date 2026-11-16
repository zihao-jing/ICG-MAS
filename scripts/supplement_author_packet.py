"""Add only verified, correct, nonreserved GPT k1 bases; preserve prior sheets."""
import json,csv
from pathlib import Path
from collections import Counter
from src.audit.pilot_common import digest,freeze
from scripts.prepare_author_packet import cached_mq,export_rows
P=Path('rebuttal/pilots');O=Path('rebuttal/annotation/author_packet_20261108');R=P/'20261108_review5'
def load(p):return json.loads(p.read_text())
def main():
 R.mkdir(exist_ok=True);source=P/'20261108_gpt4omini_k1_rebuild';manifest=load(source/'board_manifest.json');recovered={r['trace_id']:r for f in (source/'recovered').glob('*.json') for r in [load(f)]}
 assert len(recovered)==152,'Wait for the existing worker; never launch another'
 for r in manifest:
  a=recovered[r['trace_id']];assert a['board_sha256']==r['board_sha256']==digest(a['trace']['checkpoints']['board']);assert a['prompt_sha256']==r['prompt_sha256']
 cfg=load(P/'configs/E2-A.json');reserved=set(cfg['pilot_ids']+cfg['calibration_ids'])
 new=sorted([r for r in recovered.values() if r['dataset']=='musique' and r['correct'] and r['instance_id'] not in reserved],key=lambda r:(digest([42,r['trace_id']]),r['trace_id']))
 old=[json.loads(s) for s in (O/'E2A_screening.jsonl').read_text().splitlines()];classrows=[json.loads(s) for s in (O/'E2C_class_confirmation_pool.jsonl').read_text().splitlines()]
 # Reproduce the original rotation frame, including incorrect MQ bases.
 allids=sorted({r['instance_id'] for r in cached_mq()}|{r['trace']['instance_id'] for r in classrows})
 def pair(i):return ['A','B'] if allids.index(i)%2==0 else ['C','D']
 for r in old+classrows:assert r['assigned_annotator'] in pair(r['trace']['instance_id'])
 combined=load(P/'20261108_review4/author_packet_manifest.json')['E2A_candidates']+[{k:r[k] for k in ['trace_id','instance_id','source_run','board_sha256','prompt_sha256']}|{'model_family':'gpt','k':1} for r in new]
 combined.sort(key=lambda r:(digest([42,r['trace_id']]),r['trace_id']));ranks={r['trace_id']:i+1 for i,r in enumerate(combined)}
 rows=[]
 for r in new:
  for person in pair(r['instance_id']):rows.append({'task':'E2-A base screening supplement','item_id':r['trace_id'],'candidate_rank':ranks[r['trace_id']],'candidate_agent_ids':[u['agent_id'] for u in r['trace']['source_contexts']],'k':1,'assigned_annotator':person,'annotator_id':'','trace':r['trace'],'answers':dict(old[0]['answers'])})
 assert all(all(v=='' for v in r['answers'].values()) for r in rows)
 export_rows(O/'E2A_screening_supplement_wave1.jsonl',rows)
 with (O/'E2A_screening_supplement_wave1_index.csv').open('w') as f:
  w=csv.writer(f);w.writerow(['item_id','assigned_annotator','jsonl_row','combined_candidate_rank']);w.writerows([r['item_id'],r['assigned_annotator'],i+1,r['candidate_rank']] for i,r in enumerate(rows))
 # Global rank index applies to old and supplementary sheets without modifying old rows.
 with (O/'E2A_combined_candidate_order.csv').open('w') as f:
  w=csv.writer(f);w.writerow(['item_id','combined_candidate_rank']);w.writerows((r['trace_id'],ranks[r['trace_id']]) for r in combined)
 freeze(R/'E2A_combined_manifest.json',{'rule':'SHA256 canonical [42,trace_id], then trace_id; first 50 author-eligible targets/type','candidates':combined,'reserved_excluded':sorted(reserved)})
 counts=Counter(r['model_family'] for r in combined);assign=Counter(r['assigned_annotator'] for r in rows);hours=load(O/'hours_by_annotator.json')
 for a in 'ABCD':
  hours[a]['E2A_supplement_hours_estimate']=assign[a]*7/60;hours[a]['E2A_screening_combined_hours_estimate']=sum(r['assigned_annotator']==a for r in old+rows)*7/60
 (O/'hours_by_annotator.json').write_text(json.dumps(hours,indent=2)+'\n')
 evidence=sum(len(r['candidate_agent_ids']) for r in old+rows)//2
 summary={'base_counts_per_model':dict(counts),'aggregation_targets_per_model':dict(counts),'total_bases':len(combined),'aggregation_targets':len(combined),'evidence_targets_per_type':evidence,'supplement_bases':len(new),'supplement_assignments':dict(assign),'hours':hours,'aggregation_shortfall_before_screening':max(0,50-len(combined)),'correct_GPT_reserved_excluded':sum(r['dataset']=='musique' and r['correct'] and r['instance_id'] in reserved for r in recovered.values())}
 freeze(R/'supplement_summary.json',summary)
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
