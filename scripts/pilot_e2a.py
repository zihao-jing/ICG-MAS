"""End-to-end injection/keep/baseline technical path; provisional, not efficacy data."""
import argparse,json,re
from pathlib import Path
from src.audit.pilot_common import CallLedger,freeze,digest
from src.audit.matcher_v2 import structured_call,obj,CARRIER_PROMPT,carrier_schema
from src.audit.semantic_matcher import validate_carriers
from src.audit.official_adapters import run_baselines
from src.audit.fault_injection import inject_evidence,provisional_single_defect
from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer
from scripts.run_frozen_repair import original_prompt
from scripts.pilot_e1 import messages
from scripts.pilot_e4p import validate_action_manifest

def score(raw,row):return answer_f1(extract_answer(raw),{'answer':row['gold_answer'],'answer_aliases':row.get('answer_aliases',[])})
def choose_injection(row,kind):
 facts=row['facts'];carriers=row['carriers'];board=row['checkpoints']['board'];pool=row['checkpoints']['extraction'];byid={u['unit_id']:u for u in pool}
 common=set.intersection(*map(set,facts['support_sets']));choices=[]
 for r in carriers['facts']:
  ids={i for c in r['extraction'] for i in c['unit_ids']};agents={byid[i]['agent_id'] for i in ids}
  if r['fact_id'] in common and len(agents)==1 and ids&{u['unit_id'] for u in board}:
   a=next(iter(agents));remaining=[u for u in pool if u['agent_id']==a and u['unit_id'] not in ids]
   if remaining:choices.append((r['fact_id'],a,sorted(ids),True))
 if choices:return sorted(choices)[0]
 # Still exercise editing mechanics on a fixed unit, but explicitly ineligible.
 for u in board:
  if any(v['agent_id']==u['agent_id'] and v['unit_id']!=u['unit_id'] for v in pool):return (None,u['agent_id'],[u['unit_id']],False)
 return (None,None,[],False)

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',default='rebuttal/pilots/configs/E2-A-technical.json');p.add_argument('--execute',action='store_true');p.add_argument('--max-calls',type=int);a=p.parse_args()
 c=json.loads(Path(a.config).read_text());rows=validate_action_manifest(c)
 if c.get('label_status')!='pilot_provisional':raise ValueError('Technical only')
 bounds=[2+2+3+3+4*(3+(2*r['n_agents']+2)) for r in rows] # clean2, edited2, rewrite3, carrier3; 4 backbone/gold combinations
 print(json.dumps({'items':len(rows),'maximum_calls':sum(bounds),'paid':a.execute}),flush=True)
 if not a.execute:return
 ledger=CallLedger(c['output'],c,c['prereg'],a.max_calls)
 try:
  for i,row in enumerate(rows):
   key=row['trace_id'];kind=c['injection_schedule'][i];system,user=original_prompt(row,row['board_units'])
   clean=[ledger.call(key+f'/clean/{j}',row['model'],messages(system,user),max_tokens=4096) for j in range(2)]
   fact,agent,carrierids,necessity=choose_injection(row,kind)
   faithful=all(x['fidelity']=='faithful' for r in row['carriers']['facts'] for cp in ['extraction','board'] for x in r[cp])
   complete=any(all(any(x['fidelity']=='faithful' for x in next(r for r in row['carriers']['facts'] if r['fact_id']==fid)[cp]) for fid in support for cp in ['extraction','board']) for support in row['facts']['support_sets'])
   eligible=all(score(x,row)>=1 for x in clean) and faithful and complete and necessity
   output={'instance_id':row['instance_id'],'label_status':'pilot_provisional','human_eligible':False,'provisional_eligible':eligible,'injection_type':kind,'fact_id':fact,'clean_outputs':clean}
   if kind=='aggregation':
    schema=obj({'answer_text':{'type':'string'}})
    rewrite=structured_call(ledger,key+'/rewrite',c['judge_model'],
      'Rewrite exactly the single visible RATIONALE step to misuse one stated board fact, and make ANSWER follow that wrong step. Preserve USED_EVIDENCE and all other text. Return JSON with answer_text only. Do not invent hidden reasoning.',
      {'question':row['question'],'board':row['board_units'],'answer_text':row['answer_text']},schema,lambda x:None)
    edited=json.loads(json.dumps(row));edited['answer_text']=rewrite['value']['answer_text'] if rewrite['status']=='ok' else ''
    outcomes=[edited['answer_text']];output['rewrite']=rewrite
    kept=eligible and bool(edited['answer_text']) and score(edited['answer_text'],row)<1
    output['single_step_check']='provisional only; human confirmation required'
   elif agent is None:
    output.update(status='failed',reason='No noncarrier replacement available',provisional_keep=False)
    freeze(Path(c['output'])/'raw'/(key+'.json'),output);continue
   else:
    replacement=None
    if kind=='distortion':
     original=next(u['text'] for u in row['board_units'] if u['agent_id']==agent)
     schema=obj({'text':{'type':'string'}})
     rewrite=structured_call(ledger,key+'/distort',c['judge_model'],
       'Change exactly one key entity, number, date, relation or negation in the supplied evidence unit. Keep all other details. Return JSON text only. This is a synthetic error-injection experiment.',
       {'unit':original,'question':row['question']},schema,lambda x:None)
     replacement=rewrite['value']['text'] if rewrite['status']=='ok' else None;output['rewrite']=rewrite
     if replacement is None:
      output.update(status='failed',provisional_keep=False);freeze(Path(c['output'])/'raw'/(key+'.json'),output);continue
    edited=inject_evidence(row,kind,agent,carrierids,replacement_text=replacement)
    system,user=original_prompt(row,edited['checkpoints']['board'])
    outcomes=[ledger.call(key+f'/edited/{j}',row['model'],messages(system,user),max_tokens=4096) for j in range(2)]
    edited['answer_text']=outcomes[0]
    payload={'question':row['question'],'facts':row['facts'],'source_contexts':row['source_contexts'],'extraction':edited['checkpoints']['extraction'],'board':edited['checkpoints']['board']}
    post=structured_call(ledger,key+'/postcheck',c['judge_model'],CARRIER_PROMPT,payload,carrier_schema(row['facts'],edited),lambda x:validate_carriers(x,row['facts'],edited))
    output['postcheck']=post
    single=post['status']=='ok' and provisional_single_defect(post['value'],fact,kind)
    output['provisional_single_defect']=single
    kept=eligible and all(score(x,row)<1 for x in outcomes) and single
    # Human single-defect confirmation is absent: never present provisional_keep as card-qualified keep.
   output.update(status='ok',injected_outputs=outcomes,provisional_keep=kept,card_qualified_keep=False,
       edited_trace=edited,baseline_path_on_unkept=not kept)
   output['baselines']=[]
   for gold in [False,True]:output['baselines']+=run_baselines(ledger,key,edited,c['backbones'],step_by_step=True,gold=gold)
   freeze(Path(c['output'])/'raw'/(key+'.json'),output)
   print(json.dumps({'completed_item':row['instance_id']}),flush=True)
 finally:ledger.close()
if __name__=='__main__':main()
