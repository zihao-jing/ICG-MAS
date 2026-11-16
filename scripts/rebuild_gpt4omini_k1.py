"""Approved day-0 aggregation-only rebuild; source boards bound to every answer."""
import argparse,json
from pathlib import Path
from src.audit.critical_fact_validation import build_trace_packages,reconstruct_states_and_scores,get_transmitted_units,load_jsonl
from src.audit.pilot_common import CallLedger,digest,freeze,blind_view
from src.protocols.relay import _AGGREGATION_SYSTEM,_build_evidence_board_prompt
from src.protocols.base import extract_answer
from src.eval.data_loader import load_musique
from src.eval.evaluate import answer_f1
from src.eval.silo_bench_loader import silobench_exact_match
CONFIG='rebuttal/pilots/configs/GPT-k1-rebuild.json'
def prepare():
 rows=[]
 for dataset,run,na in [('musique','run_musique_gpt4omini',None),('silobench','run_gpt4omini_n5',5),('silobench','run_gpt4omini_n10',10)]:
  states,scores=reconstruct_states_and_scores(load_jsonl(Path('results')/run/'api_responses.jsonl'))
  for t in build_trace_packages(dataset=dataset,run_dir='results/'+run,protocol='score_ranked_relay',source_id=run,n_agents=na):
   n=na or len(t['source_contexts']);u=get_transmitted_units(t['instance_id'],'score_ranked_relay',states,scores,n,k=1)
   board=[{'unit_id':f'k1:a{a}:u{j}','agent_id':a,'text':text} for a,texts in sorted(u.items()) for j,text in enumerate(texts)]
   t['checkpoints']['transmission']=board;t['checkpoints']['board']=board;t['answer_text']=''
   messages=[{'role':'system','content':_AGGREGATION_SYSTEM},{'role':'user','content':_build_evidence_board_prompt([u.get(a,[]) for a in range(n)],t['question'])}]
   rows.append({'trace_id':digest([run,t['instance_id'],1]),'instance_id':t['instance_id'],'dataset':dataset,'source_run':run,'board_sha256':digest(board),'prompt_sha256':digest(messages),'messages':messages,'trace':blind_view(t)})
 return sorted(rows,key=lambda r:digest([42,r['trace_id']]))
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--max-calls',type=int);a=p.parse_args()
 c=json.loads(Path(CONFIG).read_text());rows=prepare();assert len(rows)==152
 out=Path(c['output']);freeze(out/'board_manifest.json',rows)
 print(json.dumps({'calls':len(rows),'model':c['model'],'paid':a.execute}),flush=True)
 if not a.execute:return
 instances={r['id']:r for r in load_musique()};ledger=CallLedger(out,c,c['prereg'],a.max_calls)
 try:
  for r in rows:
   assert digest(r['trace']['checkpoints']['board'])==r['board_sha256'] and digest(r['messages'])==r['prompt_sha256']
   answer=ledger.call(r['trace_id'],c['model'],r['messages'],max_tokens=1024)
   pred=extract_answer(answer);correct=answer_f1(pred,instances[r['instance_id']])>=1 if r['dataset']=='musique' else silobench_exact_match(pred,{'answer':r['trace']['gold_answer']})
   t=dict(r['trace'],answer_text=answer)
   freeze(out/'recovered'/f"{r['trace_id']}.json",{k:v for k,v in dict(r,trace=t,answer=answer,correct=correct,model=c['model']).items() if k!='messages'})
   print(json.dumps({'trace_id':r['trace_id'],'board_sha256':r['board_sha256'],'recovered':True}),flush=True)
 finally:ledger.close()
if __name__=='__main__':main()
