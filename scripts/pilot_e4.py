"""E4 matrix on preregistered targets and source-span swaps; human gates mandatory."""
import argparse,json
from pathlib import Path
from src.audit.pilot_common import CallLedger,digest,freeze
from src.audit.semantic_matcher import CARRIER_SYSTEM,parse_json,validate_carriers
from src.audit.base_tokenizers import volume_match
from src.audit.matcher_v2 import CARRIER_PROMPT,carrier_schema,structured_call
from src.audit.repair_study import _strong_repair_analysis_request,_strong_repair_final_request
from src.protocols.relay import _EXTRACTION_SYSTEM,_build_extraction_prompt,_parse_units
from scripts.run_frozen_repair import original_prompt
from scripts.pilot_e1 import messages
from scripts.pilot_e4p import validate_action_manifest

ARMS=['Rerun','R-ext','V-ext','R-sel','V-sel','R-dist','V-dist','R-agg','generic_retry','R-agg+']

def run_case(row,cfg,ledger):
    out=[];new_units={};model=row['model'];key=row['trace_id'];original=row['board_units']
    for arm in ARMS:
        board=[dict(u) for u in original];added=[];token_units=[];no_op=False
        if arm in ('R-ext','V-ext'):
            agent=row['target_agent'] if arm=='R-ext' else row['donor_agent']
            context=next(s['text'] for s in row['source_contexts'] if s['agent_id']==agent)
            raw=ledger.call(key+'/'+arm+'/extract',model,messages(_EXTRACTION_SYSTEM,_build_extraction_prompt(context,row['question'],3)))
            texts=_parse_units(raw,3)
            if arm=='V-ext':texts=texts[:len(new_units['R-ext'])]
            added=[{'unit_id':f'{arm}:{j}','agent_id':agent,'text':s} for j,s in enumerate(texts)]
            board+=added;new_units[arm]=added
        elif arm in ('R-sel','V-sel'):
            ids=row['target_next_unit_ids'] if arm=='R-sel' else row['donor_next_unit_ids'][:len(new_units['R-sel'])]
            agent=row['target_agent'] if arm=='R-sel' else row['donor_agent']
            no_op=not any(u['agent_id']==agent for u in original)
            if not no_op:
                added=[next(u for u in row['pool_units'] if u['unit_id']==i) for i in ids[:2]];board+=added
            new_units[arm]=added
        elif arm in ('R-dist','V-dist'):
            swap=row['target_swap'] if arm=='R-dist' else row['donor_swap']
            agent=row['target_agent'] if arm=='R-dist' else row['donor_agent']
            no_op=not any(u['agent_id']==agent for u in original)
            if not no_op:
                context=next(s['text'] for s in row['source_contexts'] if s['agent_id']==agent)
                provisional=cfg.get('label_status')=='pilot_provisional' and swap.get('label_status')=='pilot_provisional'
                if not (swap.get('author_checked') or provisional) or swap['text'] not in context:raise ValueError('Unverified or nonverbatim distortion swap')
                matches=[u for u in board if u['unit_id']==swap['unit_id']]
                if len(matches)!=1:raise ValueError('Missing swap unit')
                matches[0]['text']=swap['text']
                token_units=[dict(matches[0])]
        if no_op:
            answer=out[0]['answer']
        elif arm in ('R-agg','generic_retry'):
            req=_strong_repair_analysis_request(row,board,audited=arm=='R-agg',model=model,max_tokens=2048,condition=arm)
            work=ledger.call(key+'/'+arm+'/ledger',model,messages(req.system_query,req.user_query))
            req=_strong_repair_final_request(row,board,work,audited=arm=='R-agg',model=model,max_tokens=4096,condition=arm)
            answer=ledger.call(key+'/'+arm+'/answer',model,messages(req.system_query,req.user_query),max_tokens=4096)
        else:
            sys,user=original_prompt(row,board)
            answer=ledger.call(key+'/'+arm+'/answer',cfg['strong_model'] if arm=='R-agg+' else model,messages(sys,user),max_tokens=4096)
        fidelity=None
        if arm in ('R-ext','V-ext','R-dist','V-dist') and not no_op:
            match_input={'question':row['question'],'facts':row['facts'],'source_contexts':row['source_contexts'],'extraction':row['pool_units'],'board':board}
            t={'checkpoints':{'extraction':row['pool_units'],'board':board}}
            fidelity=structured_call(ledger,key+'/'+arm+'/fidelity',cfg['judge_model'],CARRIER_PROMPT,match_input,
                carrier_schema(row['facts'],t),lambda x:validate_carriers(x,row['facts'],t))
        out.append({'trace_id':key,'arm':arm,'answer':answer,'board_sha256':digest(board),'no_op':no_op,
                    'added_units':added,'token_units':token_units or added,'fidelity':fidelity,'label_status':'pilot_provisional'})
    by_arm={r['arm']:r for r in out}
    for repair,control in [('R-ext','V-ext'),('R-sel','V-sel'),('R-dist','V-dist')]:
        r,c=by_arm[repair],by_arm[control]
        match=volume_match(model,r['token_units'],c['token_units'])
        match['matched']=match['matched'] and r['no_op']==c['no_op']
        r['control_match']=c['control_match']=match
    return out

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--config',default='rebuttal/pilots/configs/E4.json');ap.add_argument('--execute',action='store_true');ap.add_argument('--max-calls',type=int);args=ap.parse_args()
    cfg=json.loads(Path(args.config).read_text())
    try:rows=validate_action_manifest(cfg)
    except ValueError as exc:
        print(json.dumps({'status':'blocked','reason':str(exc),'dispatchable_calls':0,'core_calls_per_case':14,'postrepair_matcher_calls':'pending manifest'}))
        if args.execute:raise
        return
    print(json.dumps({'items':len(rows),'maximum_calls':26*len(rows),'token_matching':'exact base tokenizer'}))
    if not args.execute:return
    ledger=CallLedger(cfg['output'],cfg,cfg['prereg'],args.max_calls)
    try:
        for row in rows:
            freeze(Path(cfg['output'])/'raw'/f"{digest(row['trace_id'])}.json",run_case(row,cfg,ledger))
            print(json.dumps({'completed_item':row['instance_id']}),flush=True)
    finally:ledger.close()
if __name__=='__main__':main()
