"""One optional extra-seed SB10 technical placement case. Full switch remains off."""
import argparse,json,random,sys
from pathlib import Path
from src.audit.pilot_common import CallLedger,digest,freeze,ranked
from src.audit.matcher_v2 import match_trace
from src.audit.pilot_selection import placement_hash_agent
from src.protocols.base import format_shard_context,parse_score_json
from src.protocols.relay import (_EXTRACTION_SYSTEM,_SCORING_SYSTEM,_build_extraction_prompt,_build_scoring_prompt,_parse_units,_topk_select)
from src.eval.silo_bench_loader import load_silobench,shards_from_silobench
from scripts.pilot_e1 import messages
from scripts.run_frozen_repair import original_prompt
from scripts.pilot_e4p import run_case

ROOT=Path('rebuttal/pilots/20261108_e4_p_seed43')
def prepare():
 sys.path.insert(0,str(Path('data/silo-bench/benchmark_generator').resolve()))
 from main import BenchmarkGenerator,generate_paradigm_i_cases,generate_paradigm_ii_cases,generate_paradigm_iii_cases
 # Imports set42; seed43 is applied AFTER imports and before any generation.
 random.seed(43);g=BenchmarkGenerator(num_agents=10,output_dir=str(ROOT/'data'))
 cases=[]
 for f in [generate_paradigm_i_cases,generate_paradigm_ii_cases,generate_paradigm_iii_cases]:cases+=f(10,g._create_case_structure)
 usable=[x for x in cases if not x['metadata']['is_segmented']]
 for x in usable:
  # Remove nondeterministic generated_at metadata before immutable serialization.
  for k in list(x.get('metadata',{})):
   if 'time' in k or 'date' in k:del x['metadata'][k]
  freeze(ROOT/'data'/(x['case_id']+'_n10.json'),x)
 ids=ranked([x['case_id']+'_n10' for x in usable]);chosen=ids[:1]
 base=json.loads(Path('rebuttal/pilots/configs/E4-P.json').read_text())
 c=base|{'output':str(ROOT),'prereg':'rebuttal/pilots/prereg/E4-P-seed43.md','extra_seed_pilot':True,'dataset_seed':43,'sample':{'ids':chosen,'limit':1},'label_status':'pilot_provisional'}
 freeze('rebuttal/pilots/configs/E4-P-seed43.json',c)
 Path(c['prereg']).write_text(f'''# E4-P extra-seed technical pilot
One reserved fresh SB10 case: {chosen}, generated with repository generator and data seed43 AFTER module imports. Data hashes fixed in data files; k1, Qwen base, Qwen provisional matcher, Gemini placements. ID gains ::seed43::pilot; no final-evaluation ID is reused. Full option(a) remains off; this one-case technical pilot is explicitly authorised as cheap extra-seed testing. Outcomes will be discarded and any future full seed43 run makes fresh calls. Cluster by underlying task across seeds, not independent task replication. Max60attempts including new pools, baseline,6matcher attempts,12placement calls and terminal1. No group outcome summaries. Optional(b) dropped. No human labels generated.\n''')
 print('Prepared extra-seed case',chosen)

def main():
 p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--execute',action='store_true');p.add_argument('--max-calls',type=int);a=p.parse_args()
 if a.prepare:prepare();return
 c=json.loads(Path('rebuttal/pilots/configs/E4-P-seed43.json').read_text());print(json.dumps({'items':1,'maximum_calls':60,'paid':a.execute}),flush=True)
 if not a.execute:return
 inst=next(x for x in load_silobench(path=str(ROOT/'data'),n_agents_filter=10) if x['id']==c['sample']['ids'][0]);inst['id']+='::seed43::pilot'
 model=c['judge_model'];ledger=CallLedger(ROOT,c,c['prereg'],a.max_calls)
 try:
  shards=shards_from_silobench(inst);units=[];scores=[]
  contexts=[{'unit_id':f'source:a{i}','agent_id':i,'text':format_shard_context(s)} for i,s in enumerate(shards)]
  for i,s in enumerate(shards):
   raw=ledger.call(f'extract/{i}',model,messages(_EXTRACTION_SYSTEM,_build_extraction_prompt(contexts[i]['text'],inst['question'],3)))
   us=_parse_units(raw,3);units.append(us);ss=[]
   for j,u in enumerate(us):ss.append(parse_score_json(ledger.call(f'score/{i}/{j}',model,messages(_SCORING_SYSTEM,_build_scoring_prompt(inst['question'],u)),max_tokens=512)))
   scores.append(ss)
  pool=[{'unit_id':f'pool:a{i}:u{j}','agent_id':i,'text':u} for i,us in enumerate(units) for j,u in enumerate(us)]
  board=[next(p for p in pool if p['agent_id']==i and p['text']==u) for i,us in enumerate(units) for u in _topk_select(us,scores[i],1)]
  t={'instance_id':inst['id'],'trace_id':digest(inst['id']),'model':model,'source_id':model,'dataset':'silobench','k':1,'n_agents':10,
     'question':inst['question'],'gold_answer':inst['answer'],'source_contexts':contexts,'source_supports':[dict(x,unit_id=x['unit_id'].replace('source','gold')) for x in contexts],
     'checkpoints':{'extraction':pool,'transmission':board,'board':board},'scores':scores,'pool_units':pool,'board_units':board}
  sy,us=original_prompt(t,board);t['answer_text']=ledger.call('baseline',model,messages(sy,us),max_tokens=4096)
  m=match_trace(ledger,'matcher',t,c['judge_model']);freeze(ROOT/'matcher.json',m)
  # Target determined from provisional missing carriers, with support-holder fallback.
  target=0
  if m['status']=='ok':
   fm={x['fact_id']:x for x in m['facts']['facts']}
   missing=next((x for x in m['carriers']['facts'] if not x['extraction'] or not x['board']),None)
   f=fm[missing['fact_id']] if missing else m['facts']['facts'][0];target=int(f['source_ids'][0].rsplit('a',1)[1])
  else:raise ValueError('Extra-seed provisional matcher failed; do not invent target')
  t.update(target_agent=target,hash_agent=placement_hash_agent(model,inst['id'],10),label_status='pilot_provisional')
  # Pin placement manifest BEFORE any Gemini placement/terminal outcomes.
  freeze(ROOT/'action_manifest.json',t)
  terminal=ledger.call(t['trace_id']+'/R-agg+/answer',c['strong_model'],messages(sy,us),max_tokens=4096)
  t['e4_terminal']=next(x for x in ledger.done.values() if x['key']==t['trace_id']+'/R-agg+/answer')
  freeze(ROOT/'raw.json',run_case(t,c,ledger));print(json.dumps({'completed_item':inst['id']}),flush=True)
 finally:ledger.close()
if __name__=='__main__':main()
