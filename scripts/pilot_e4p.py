"""Config-driven E4-P pilot. Execution requires a hashed, frozen action manifest."""
import argparse,json
from pathlib import Path
from src.audit.pilot_common import CallLedger,digest,freeze
from src.audit.semantic_matcher import parse_json
from src.protocols.relay import (_EXTRACTION_SYSTEM,_SCORING_SYSTEM,_build_extraction_prompt,_build_scoring_prompt,_parse_units,_topk_select)
from src.protocols.base import parse_score_json
from scripts.run_single_middle_swap import replacement_board
from scripts.run_frozen_repair import original_prompt
from scripts.pilot_e1 import messages

def validate_action_manifest(cfg):
    path=Path(cfg['action_manifest'])
    provisional=cfg.get('label_status')=='pilot_provisional' and cfg.get('allow_full_run') is False
    if not (cfg.get('matcher_frozen') or provisional) or not cfg.get('manifest_sha256') or not path.is_file():raise ValueError('Missing matcher and frozen pilot ID/action manifest; no paid execution')
    if digest(path.read_bytes())!=cfg['manifest_sha256']:raise ValueError('Action manifest hash mismatch')
    rows=json.loads(path.read_text())
    selected=set(cfg.get('sample',{}).get('ids',cfg['pilot_ids']))
    limit=cfg.get('sample',{}).get('limit',cfg['sample_size'])
    if not selected<=set(cfg['pilot_ids']) or len(selected)>limit:raise ValueError('Configured sample escapes pilot reservation')
    if any(r['instance_id'] not in selected for r in rows):raise ValueError('Manifest contains nonpilot IDs')
    if not rows:raise ValueError('Empty action manifest')
    for r in rows:
        if digest(r['board_units'])!=r['board_sha256']:raise ValueError('Changed frozen board')
        if r['k']!=1:raise ValueError('E4-P requires k=1')
    return rows

def run_case(row,cfg,ledger):
    outcomes=[];model=row['model'];key=row['trace_id']
    for condition in cfg['conditions']:
        board=row['board_units']
        if condition=='R-agg+':
            cached=row.get('e4_terminal')
            if cached is None and cfg.get('e4_calls'):
                entries=[json.loads(x) for x in Path(cfg['e4_calls']).read_text().splitlines()]
                cached=next((x for x in entries if x.get('event')=='result' and x.get('key')==key+'/R-agg+/answer'),None)
            system,user=original_prompt(row,board)
            if not cached or cached.get('model_id')!=cfg['strong_model'] or cached.get('prompt_sha256')!=digest(messages(system,user)) or cached.get('seed')!=42 or cached.get('temperature')!=0 or not cached.get('success'):
                raise ValueError('Missing identical E4 terminal outcome; do not make a duplicate comparator call')
            outcomes.append({'trace_id':key,'condition':condition,'answer':cached['content'],'reused_call_id':cached['call_id'],'board_sha256':digest(board)})
            continue
        if condition.startswith('G-ext'):
            a=row['target_agent'] if condition=='G-ext@t' else row['hash_agent']
            context=next(s['text'] for s in row['source_contexts'] if s['agent_id']==a)
            raw=ledger.call(key+'/'+condition+'/extract',cfg['strong_model'],messages(_EXTRACTION_SYSTEM,_build_extraction_prompt(context,row['question'],cfg['max_units'])))
            units=_parse_units(raw,cfg['max_units'])
            if not units:raise ValueError('Empty placement extraction')
            scores=[]
            for j,u in enumerate(units):
                raw=ledger.call(key+'/'+condition+f'/score/{j}',model,messages(_SCORING_SYSTEM,_build_scoring_prompt(row['question'],u)),max_tokens=512)
                parse_json(raw);scores.append(parse_score_json(raw))
            selected=_topk_select(units,scores,1)
            board=replacement_board(row,a,selected)
        elif condition=='G-sel@t':
            a=row['target_agent'];pool=[u for u in row['pool_units'] if u['agent_id']==a]
            if not pool:raise ValueError('Target pool empty; needs preregistered no-op handling')
            raw=ledger.call(key+'/'+condition+'/select',cfg['strong_model'],messages('Select exactly one supplied evidence unit ID for the question. Return JSON {"unit_id":"..."}; never rewrite evidence.',json.dumps({'question':row['question'],'pool':pool})))
            uid=parse_json(raw)['unit_id'];selected=[u['text'] for u in pool if u['unit_id']==uid]
            if len(selected)!=1:raise ValueError('Selection is not a cached unit')
            board=replacement_board(row,a,selected)
        elif condition!='R-agg+':raise ValueError('Unapproved condition')
        if len(board)!=len(row['board_units']):raise ValueError('Placement changed board size')
        system,user=original_prompt(row,board)
        answer=ledger.call(key+'/'+condition+'/answer',cfg['strong_model'] if condition=='R-agg+' else model,messages(system,user),max_tokens=cfg['max_tokens'])
        outcomes.append({'trace_id':key,'condition':condition,'answer':answer,'board_sha256':digest(board)})
    return outcomes

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--config',default='rebuttal/pilots/configs/E4-P.json');ap.add_argument('--execute',action='store_true');ap.add_argument('--max-calls',type=int);args=ap.parse_args()
    cfg=json.loads(Path(args.config).read_text())
    try:rows=validate_action_manifest(cfg)
    except ValueError as exc:
        print(json.dumps({'status':'blocked','reason':str(exc),'dispatchable_calls':0,'planned_upper_bound_per_case':12}))
        if args.execute:raise
        return
    bound=len(rows)*12 # terminal comparator reused from E4 with exact provenance
    print(json.dumps({'items':len(rows),'maximum_calls':bound}))
    if not args.execute:return
    ledger=CallLedger(cfg['output'],cfg,cfg['prereg'],args.max_calls)
    try:
        for row in rows:freeze(Path(cfg['output'])/'raw'/f"{digest(row['trace_id'])}.json",run_case(row,cfg,ledger))
    finally:ledger.close()
if __name__=='__main__':main()
