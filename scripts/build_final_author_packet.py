"""Final author packet: E1 anchor (30 x 3 models x 2 authors), E1 dev (20 x 2 authors), E2 wave-1 spot-check (12 x 1 author).

Blind export only: model identity, judge/matcher/lexical output and fault verdicts are never in a sheet. Items are identified by a
trace hash; the hash -> (instance, model) map is private (rebuttal/pilots/20261108_review8/, not in the packet).
Wave-2 spot-check sheets cannot exist before injections; they are generated after the stage-1 gate, never fabricated.
"""
import csv,json
from pathlib import Path
from src.audit.critical_fact_validation import build_trace_packages
from src.audit.pilot_common import blind_view,digest,freeze
from scripts.prepare_batch1_e1_sheets import RUNS
from scripts.prepare_author_packet import export_rows
P=Path('rebuttal/pilots');O=Path('rebuttal/annotation/author_packet_20261108');R=P/'20261108_review8'
E1_ANSWERS=['critical_facts_json','sufficient_support_sets_json','carriers_json','binary_call','rationale','uncertain_reason','minutes_spent']
SPOT_ANSWERS=['defect_free','target_fact_text','fact_in_every_sufficient_set','no_carrier_outside_target_agent','feasible_for_this_fault_type','uncertain_reason','source_citations','minutes_spent']
def packages(ids):
 out={}
 for model,runs in RUNS.items():
  for index,run in enumerate(runs):
   for p in build_trace_packages(dataset='musique' if index==2 else 'silobench',run_dir=Path('results')/run,protocol='score_ranked_relay',source_id=run,n_agents=None if index==2 else (5 if index==0 else 10)):
    if p['instance_id'] in ids:
     p['answer_text']=p['baseline_prediction'];out[(model,p['instance_id'])]=p
 return out
def main():
 O.mkdir(exist_ok=True);R.mkdir(exist_ok=True)
 anchor=json.loads((P/'20261108_review7/e1_anchor_locked_manifest.json').read_text());aid=[i for v in anchor['strata'].values() for i in v['ids']]
 dev=json.loads((P/'20261108_preflight/id_manifest.json').read_text())['e1_dev']
 old=[json.loads(x) for x in Path('rebuttal/annotation/E1/evaluation_sheet.jsonl').read_text().splitlines()];devpair={r['trace']['instance_id']:r['assigned_pair'] for r in old if r['split']=='dev'}
 pk=packages(set(aid)|set(dev));private={}
 order=sorted(aid,key=lambda i:(digest(['E1-anchor-pair-v1',42,i]),i));pair={i:(['A','B'] if n%2==0 else ['C','D']) for n,i in enumerate(order)}
 rows=[]
 for i in order:
  for model in RUNS:
   t=pk[(model,i)];v=blind_view(t);h=digest(v);private[h]={'instance_id':i,'model':model}
   for who in pair[i]:rows.append({'task':'E1 anchor','item_id':h,'k':3,'assigned_annotator':who,'annotator_id':'','trace':v,'answers':{k:'' for k in E1_ANSWERS}})
 export_rows(O/'E1_anchor.jsonl',rows);n_anchor=len(rows)
 drows=[]
 for i in sorted(dev):
  t=pk[('qwen235b',i)];v=blind_view(t);h=digest(v);private[h]={'instance_id':i,'model':'qwen235b','split':'dev'}
  for who in devpair[i]:drows.append({'task':'E1 dev','item_id':h,'k':3,'assigned_annotator':who,'annotator_id':'','trace':v,'answers':{k:'' for k in E1_ANSWERS}})
 export_rows(O/'E1_dev.jsonl',drows)
 spot=json.loads((R/'e2_spotcheck_wave1_manifest.json').read_text());base={}
 for f in ['E2A_screening.jsonl','E2A_screening_supplement_wave1.jsonl']:
  for s in (O/f).read_text().splitlines():
   r=json.loads(s);base.setdefault(r['item_id'],r['trace'])
 srows=[{'task':'E2 wave-1 spot-check','item_id':digest(['spot',it['fault_type'],it['item_key']]),'spotcheck_fault_type':it['fault_type'].replace('_',' '),'target_agent_id':it['target_agent'],'assigned_annotator':it['author'],'annotator_id':'','k':1,'trace':base[it['trace_id']],'answers':{k:'' for k in SPOT_ANSWERS}} for it in spot['wave1_items']]
 for r,it in zip(srows,spot['wave1_items']):private[r['item_id']]={'item_key':it['item_key'],'fault_type':it['fault_type']}
 export_rows(O/'E2_spotcheck_wave1.jsonl',srows)
 freeze(R/'packet_private_map.json',private)
 counts={a:{'anchor_rows':sum(r['assigned_annotator']==a for r in rows),'dev_rows':sum(r['assigned_annotator']==a for r in drows),'spot_wave1':sum(r['assigned_annotator']==a for r in srows)} for a in 'ABCD'}
 anchor_instances={a:sum(pair[i].count(a) for i in aid) for a in 'ABCD'}
 print(json.dumps({'anchor_rows':n_anchor,'dev_rows':len(drows),'spot_rows':len(srows),'per_author':counts,'anchor_instances_per_author':anchor_instances}))
if __name__=='__main__':main()
