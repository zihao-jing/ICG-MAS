"""Dry-run builder for the judge pilots (reserved items only). Makes NO API calls and has no execute option.

Writes the exact request messages, their hashes and token/cost estimates so the pilot can be approved before it runs.
"""
import json
from pathlib import Path
from src.audit.pilot_common import digest,blind_view,render_trace
P=Path('rebuttal/pilots');J=Path('rebuttal/judge');OUT=J/'pilot'
GEMINI_IN,GEMINI_OUT=0.00000075,0.00000375   # USD/token, OpenRouter snapshot 2026-11-08
from src.audit.judge_render import trace_text
def main():
 prompts=json.loads((J/'judge_prompts_v3.json').read_text());actions=json.loads((P/'20261108_technical_inputs/actions.json').read_text())
 raw={}
 for f in sorted((P/'20261108_e2_a_technical/raw').glob('*.json')):
  d=json.loads(f.read_text());raw[d['instance_id']]=d
 tasks={}
 def add(task,items):
  p=prompts['prompts'][task];reqs=[]
  for key,text in items:
   m=[{'role':'system','content':p['system']},{'role':'user','content':p['user_template'].format(trace=text)}]
   reqs.append({'item':key,'messages_sha256':digest(m),'est_input_tokens':sum(len(x['content']) for x in m)//4,'messages':m})
  tasks[task]={'judge_model':p['judge_model'],'n':len(reqs),'requests':reqs}
 add('E1_fact_labelling',[(a['instance_id'],trace_text(a)) for a in actions])
 add('E2_wave1_base_screening',[(a['instance_id'],trace_text(a)) for a in actions])
 group=lambda a:a['diagnosis'].get('group') if isinstance(a['diagnosis'],dict) else a['diagnosis']
 add('E2_partB_natural_failure',[(a['instance_id'],trace_text(a)) for a in actions if group(a)!='correct_control'])
 by={a['instance_id']:a for a in actions}
 w2=[]
 for i,d in raw.items():
  if i in by:w2.append((i+':'+d['injection_type'],'BEFORE\n'+trace_text(by[i])+'\n\nAFTER (declared edit: '+d['injection_type'].replace('_',' ')+' of this fact: "'+next((f['text'] for f in by[i]['facts']['facts'] if f['fact_id']==d['fact_id']),d['fact_id'])+'")\n'+trace_text(dict(by[i],**{k:d['edited_trace'][k] for k in ('checkpoints','answer_text') if k in d['edited_trace']}))+'\n\nRERUN ANSWERS AFTER EDIT\n'+'\n---\n'.join(d['injected_outputs'])))
 add('E2_wave2_post_injection',w2)
 OUT.mkdir(parents=True,exist_ok=True);plan={};cfg=json.loads((P/'configs/Judge-pilot-v3.json').read_text())['tasks']
 for t_,v in tasks.items():
  (OUT/(t_+'_requests.json')).write_text(json.dumps(v,indent=1,ensure_ascii=False)+'\n')
  tok=sum(r['est_input_tokens'] for r in v['requests']);n=v['n'];out_tok=6000*n
  g=tok*GEMINI_IN+out_tok*GEMINI_OUT
  plan[t_]={'judge_model':cfg[t_]['judge'],'calls':n,'measured_input_tokens_total':tok,'measured_input_tokens_per_call':round(tok/n),'assumed_output_tokens_per_call':6000,'judge_cost_usd':round(g,4),'output_tokens_measured':False}
 plan['totals']={'calls_judge':sum(v['calls'] for k,v in plan.items() if k!='totals'),'cost_usd_planned':round(sum(v['judge_cost_usd'] for k,v in plan.items() if k!='totals'),4),'measured_cost_usd':None,'note':'Planned cost uses measured input tokens on the real reserved requests and an assumed 6,000 output tokens per call; no call has run, so measured cost is none.'}
 (OUT/'pilot_plan_v3.json').write_text(json.dumps(plan,indent=1)+'\n');print(json.dumps(plan,indent=1))
if __name__=='__main__':main()
