"""Reserved technical E6 proxy paths for E2-A; no variant selection or final labels."""
import argparse,json
from pathlib import Path
from collections import Counter
from src.audit.pilot_common import CallLedger,freeze,digest
from src.audit.matcher_v2 import structured_call,fact_schema,carrier_schema,CARRIER_PROMPT
from src.audit.semantic_matcher import validate_facts,validate_carriers
from src.protocols.full_sharing import _FULL_SYSTEM,_build_full_prompt_context
from src.protocols.base import extract_answer
from scripts.pilot_e1 import messages

PROXY_PROMPT='Using only the question and all supplied source shards, list atomic facts needed to answer the question (P-q), or facts supporting the supplied majority answer (P-a). Do not use outside knowledge. Return the supplied facts/support_sets schema. source_ids refer to shard unit_ids. If the majority answer is unsupported, do not invent supporting facts.'
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--max-calls',type=int);a=p.parse_args()
 c=json.loads(Path('rebuttal/pilots/configs/E2-A-proxy.json').read_text());rows=json.loads(Path(c['action_manifest']).read_text())
 print(json.dumps({'items':len(rows),'maximum_calls':75,'paid':a.execute}),flush=True)
 if not a.execute:return
 ledger=CallLedger(c['output'],c,c['prereg'],a.max_calls)
 try:
  for row in rows:
   path=Path(c['injections'])/'raw'/(row['trace_id']+'.json')
   if not path.exists():print(json.dumps({'waiting_for_injection':row['instance_id']}),flush=True);continue
   edited=json.loads(path.read_text()).get('edited_trace')
   if not edited:continue
   sources=[dict(s,unit_id='shard-'+str(s['agent_id'])) for s in row['source_contexts']];ids=[s['unit_id'] for s in sources]
   full='\n\n'.join(s['text'] for s in sources)
   samples=[ledger.call(row['trace_id']+f'/full/{i}',row['model'],messages(_FULL_SYSTEM,_build_full_prompt_context(full,row['question'])),temperature=.7,max_tokens=4096) for i in range(3)]
   votes=Counter(extract_answer(x).strip().lower() for x in samples);majority=sorted(votes,key=lambda v:(-votes[v],v))[0]
   out={'instance_id':row['instance_id'],'label_status':'pilot_provisional','samples':samples,'majority_answer':majority,'variants':{}}
   for variant in ['P-q','P-a']:
    payload={'variant':variant,'question':row['question'],'shards':sources}
    if variant=='P-a':payload['majority_answer']=majority
    f=structured_call(ledger,row['trace_id']+'/'+variant+'/facts',c['judge_model'],PROXY_PROMPT,payload,fact_schema(ids),lambda x:validate_facts(x,ids))
    result={'facts':f}
    if f['status']=='ok':
     facts=f['value'];payload={'question':row['question'],'facts':facts,'source_contexts':sources,'extraction':edited['checkpoints']['extraction'],'board':edited['checkpoints']['board']}
     result['carriers']=structured_call(ledger,row['trace_id']+'/'+variant+'/carriers',c['judge_model'],CARRIER_PROMPT,payload,carrier_schema(facts,edited),lambda x:validate_carriers(x,facts,edited))
    out['variants'][variant]=result
   freeze(Path(c['output'])/'raw'/(digest(row['trace_id'])+'.json'),out)
   print(json.dumps({'completed_item':row['instance_id']}),flush=True)
 finally:ledger.close()
if __name__=='__main__':main()
