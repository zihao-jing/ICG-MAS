"""Reserved donor-selection clarification pilot; keeps ±10%, never pads/truncates units."""
import argparse,json,re
from pathlib import Path
from itertools import combinations
from src.audit.pilot_common import CallLedger,digest,freeze
from src.audit.base_tokenizers import volume_match,added_token_count
from src.audit.alignment import _jaccard_sim
from src.protocols.relay import _EXTRACTION_SYSTEM,_build_extraction_prompt,_parse_units
from scripts.pilot_e1 import messages
from scripts.pilot_e4p import validate_action_manifest
from scripts.run_frozen_repair import original_prompt
P=Path('rebuttal/pilots');O=P/'20261108_e4_donor_v2'
def candidates(row,arm):
 boardagents={u['agent_id'] for u in row['board_units']};other=boardagents-{row['target_agent']}
 support={int(s.rsplit('a',1)[1]) for f in row['facts']['facts'] for s in f['source_ids']}
 eligible=other-support or other
 return sorted(eligible,key=lambda a:(digest([42,row['instance_id'],arm,a]),a))
def next_units(row,a):
 pool=[u for u in row['pool_units'] if u['agent_id']==a];ids={u['unit_id'] for u in row['board_units']}
 return [u for _,u in sorted(zip(row['scores'][a],pool),key=lambda x:-x[0].get('overall',x[0].get('composite',0))) if u['unit_id'] not in ids][:2]
def swap(row,a):
 unit=next(u for u in row['board_units'] if u['agent_id']==a);text=next(s['text'] for s in row['source_contexts'] if s['agent_id']==a)
 spans=[s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+',text) if s.strip()]
 # Keep the original deterministic verbatim-source-span rule, only choose donor.
 span=sorted(spans,key=lambda s:(-_jaccard_sim(s,unit['text']),s))[0]
 return [dict(unit,text=span)]
def choose_closest(model,repair,candidates_):
 if not candidates_:raise ValueError('No eligible donor')
 a=added_token_count(model,repair)
 return min(candidates_,key=lambda c:(len(c['units'])!=len(repair),abs(added_token_count(model,c['units'])-a),c['sha']))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--max-calls',type=int);args=ap.parse_args();cfg=json.loads((P/'configs/E4-donor-v2.json').read_text());rows=validate_action_manifest(cfg);bound=sum(len(candidates(r,'V-ext'))+3 for r in rows)
 print(json.dumps({'items':len(rows),'upper_calls':bound,'paid':args.execute}),flush=True)
 if not args.execute:return
 ledger=CallLedger(cfg['output'],cfg,cfg['prereg'],args.max_calls);oldcalls=[json.loads(x) for x in (P/'20261108_e4_technical/calls.jsonl').read_text().splitlines()]
 try:
  for r in rows:
   old=json.loads((P/'20261108_e4_technical/raw'/(digest(r['trace_id'])+'.json')).read_text());arms={x['arm']:x for x in old};output=[]
   for arm,repairarm in [('V-ext','R-ext'),('V-sel','R-sel'),('V-dist','R-dist')]:
    options=[];repair=arms[repairarm]['token_units']
    for a in candidates(r,arm):
     if arm=='V-ext':
      if a==r['donor_agent']:units=arms[arm]['token_units']
      else:
       context=next(s['text'] for s in r['source_contexts'] if s['agent_id']==a)
       raw=ledger.call(r['trace_id']+f'/{arm}/{a}/extract',r['model'],messages(_EXTRACTION_SYSTEM,_build_extraction_prompt(context,r['question'],3)))
       units=[{'agent_id':a,'unit_id':f'V-ext:{j}','text':text} for j,text in enumerate(_parse_units(raw,3)[:len(repair)])]
     elif arm=='V-sel':units=next_units(r,a)[:len(repair)]
     else:units=swap(r,a)
     options.append({'agent':a,'units':units,'sha':digest([42,r['instance_id'],arm,a]),'tokens':added_token_count(r['model'],units)})
    selected=choose_closest(r['model'],repair,options);matched=volume_match(r['model'],repair,selected['units']);previous=arms[arm]['control_match']
    # Freeze selection before its aggregation answer. Token count is not an outcome label.
    manifest={'trace_id':r['trace_id'],'arm':arm,'candidates':options,'selected':selected,'match':matched,'previous_match':previous,'label_status':'pilot_provisional'}
    freeze(O/'manifests'/(digest([r['trace_id'],arm])+'.json'),manifest)
    if selected['agent']==r['donor_agent'] and selected['units']==arms[arm]['token_units']:answer=arms[arm]['answer'];reused=True
    else:
     board=[dict(u) for u in r['board_units']]
     if arm=='V-dist':
      for u in board:
       if u['agent_id']==selected['agent']:u['text']=selected['units'][0]['text']
     else:board+=selected['units']
     system,user=original_prompt(r,board);answer=ledger.call(r['trace_id']+'/'+arm+'/answer',r['model'],messages(system,user),max_tokens=4096);reused=False
    output.append(dict(manifest,answer=answer,reused_previous_answer=reused))
   freeze(O/'raw'/(digest(r['trace_id'])+'.json'),output);print(json.dumps({'completed_item':r['instance_id']}),flush=True)
 finally:ledger.close()
if __name__=='__main__':main()
