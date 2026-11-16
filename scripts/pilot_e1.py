"""E1 reserved-pool trace generation and semantic smoke pilot, never a full run."""
import argparse,json
from pathlib import Path
from src.audit.pilot_common import CallLedger,freeze,digest,MODELS
from src.audit.semantic_matcher import FACT_SYSTEM,CARRIER_SYSTEM,parse_json,validate_facts,validate_carriers
from src.eval.data_loader import load_musique,shards_from_musique
from src.protocols.base import format_shard_context,parse_score_json
from src.protocols.relay import (_EXTRACTION_SYSTEM,_SCORING_SYSTEM,_AGGREGATION_SYSTEM,_build_extraction_prompt,
    _build_scoring_prompt,_build_evidence_board_prompt,_parse_units,_topk_select)

def messages(system,user):return [{'role':'system','content':system},{'role':'user','content':user}]

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--config',default='rebuttal/pilots/configs/E1.json')
    ap.add_argument('--execute',action='store_true');ap.add_argument('--max-calls',type=int);ap.add_argument('--calibration',action='store_true');args=ap.parse_args()
    cfg=json.loads(Path(args.config).read_text());pool=json.loads(Path(cfg['id_manifest']).read_text())
    ids=cfg['calibration_ids'] if args.calibration else cfg['pilot_ids']
    if set(ids)&set(pool['full_evaluation_ids']) or len(ids)>10:raise ValueError('Pilot isolation violated')
    instances={r['id']:r for r in load_musique()};models=cfg['source_trace_models']
    # Extraction + <=3 score calls per shard; k=1/k=3 answers; 2 matcher calls per trace/k.
    bound=sum(4*len(shards_from_musique(instances[i]))+2+(0 if args.calibration else 4) for i in ids)*len(models)
    print(json.dumps({'experiment':'E1','pool':'calibration' if args.calibration else 'pilot','items':len(ids),'trace_models':len(models),'maximum_calls':bound,'paid':args.execute}),flush=True)
    if not args.execute:return
    output=Path(cfg['output']+('_calibration' if args.calibration else ''))
    ledger=CallLedger(output,cfg,cfg['prereg'],args.max_calls)
    try:
        for iid in ids:
            inst=instances[iid];shards=shards_from_musique(inst)
            contexts=[{'unit_id':f'source:a{a}','agent_id':a,'text':format_shard_context(s)} for a,s in enumerate(shards)]
            supports=[{'unit_id':f'gold:a{a}','agent_id':a,'text':p['paragraph_text']} for a,s in enumerate(shards) for p in s.paragraphs if p.get('is_supporting')]
            for model in models:
                key=f'{iid}/{model}';units=[];scores=[]
                for a,s in enumerate(shards):
                    text=ledger.call(key+f'/extract/{a}',model,messages(_EXTRACTION_SYSTEM,_build_extraction_prompt(contexts[a]['text'],inst['question'],3)))
                    u=_parse_units(text,3)
                    if not u:raise ValueError('Empty extraction')
                    units.append(u);sc=[]
                    for j,unit in enumerate(u):
                        raw=ledger.call(key+f'/score/{a}/{j}',model,messages(_SCORING_SYSTEM,_build_scoring_prompt(inst['question'],unit)),max_tokens=512)
                        obj=parse_json(raw)
                        if not all(isinstance(obj.get(k),(int,float)) and 0<=obj[k]<=1 for k in ('relevance','uniqueness','local_importance','overall')):raise ValueError('Invalid score output')
                        sc.append(parse_score_json(raw))
                    scores.append(sc)
                extraction=[{'unit_id':f'pool:a{a}:u{j}','agent_id':a,'text':u} for a,us in enumerate(units) for j,u in enumerate(us)]
                for k in (1,3):
                    boardlists=[_topk_select(u,s,k) for u,s in zip(units,scores)]
                    board=[{'unit_id':f'pool:a{a}:u{units[a].index(u)}','agent_id':a,'text':u} for a,us in enumerate(boardlists) for u in us]
                    answer=ledger.call(key+f'/aggregate/k{k}',model,messages(_AGGREGATION_SYSTEM,_build_evidence_board_prompt(boardlists,inst['question'])),max_tokens=4096)
                    trace={'instance_id':iid,'model':model,'dataset':'musique','question':inst['question'],'gold_answer':inst['answer'],
                        'source_contexts':contexts,'source_supports':supports,'answer_text':answer,'k':k,'scores':scores,
                        'checkpoints':{'extraction':extraction,'transmission':board,'board':board}}
                    out=output/'traces'/(digest([iid,model,k])+'.json');freeze(out,trace)
                    if args.calibration:continue
                    try:
                        fact_input={'question':inst['question'],'gold_supports':supports}
                        raw=ledger.call(key+f'/facts/k{k}',cfg['judge_model'],messages(FACT_SYSTEM,json.dumps(fact_input)),max_tokens=4096)
                        facts=validate_facts(parse_json(raw),[s['unit_id'] for s in supports])
                        match_input={'question':inst['question'],'facts':facts,'source_contexts':contexts,'extraction':extraction,'board':board}
                        raw=ledger.call(key+f'/carriers/k{k}',cfg['judge_model'],messages(CARRIER_SYSTEM,json.dumps(match_input)),max_tokens=4096)
                        carriers=validate_carriers(parse_json(raw),facts,trace)
                        # Raw technical outputs only. No failure-group summaries or accuracy before human labels.
                        freeze(output/'matcher'/(digest([iid,model,k])+'.json'),{'facts':facts,'carriers':carriers})
                    except (ValueError,KeyError,TypeError) as exc:
                        freeze(output/'parse_issues'/(digest([iid,model,k])+'.json'),
                            {'instance_id':iid,'model':model,'k':k,'error':type(exc).__name__+': '+str(exc),
                             'action':'retain raw call; do not retry or impute labels'})
                        print(json.dumps({'parse_issue':iid,'model':model,'k':k,'error':str(exc)}),flush=True)
            print(json.dumps({'completed_instance':iid}),flush=True)
    finally:ledger.close()
if __name__=='__main__':main()
