"""E4-P seed-43 SOURCE TRACES ONLY (label-independent steps). One model per process; one ledger per model.

Qualifying steps (each reads no E1 label, matcher output or group):
  1 generate seed-43 Silo-Bench n=10 data with the repository generator (seed 43 applied after imports)  - generator + seed only
  2 per-agent extraction with the relay extraction prompt            - reads the agent's shard and the question
  3 per-unit scoring with the relay scoring prompt                   - reads the unit text and the question
  4 top-k (k=1) selection and board construction                     - deterministic from the scores
  5 baseline k=1 aggregation answer                                  - reads the question and the board
  6 store an exact-match correctness flag against the benchmark gold - benchmark gold, not an E1 label; NO filtering is applied
NOT run here (they read labels or groups): matcher, group assignment, target/donor choice, any repair or placement arm, R-agg+.
Run: --prepare ; --model qwen|gpt|gemma [--execute --max-calls N]
"""
import argparse,datetime,json,random,sys
from pathlib import Path
from src.audit.pilot_common import CallLedger,digest,freeze,ranked
from src.protocols.base import format_shard_context,parse_score_json,extract_answer
from src.protocols.relay import (_EXTRACTION_SYSTEM,_SCORING_SYSTEM,_build_extraction_prompt,_build_scoring_prompt,_parse_units,_topk_select)
from src.eval.silo_bench_loader import load_silobench,shards_from_silobench,silobench_exact_match
from scripts.pilot_e1 import messages
from scripts.run_frozen_repair import original_prompt
ROOT=Path('rebuttal/results/batch1/E4P_seed43');DATA=ROOT/'data';PREREG='rebuttal/pilots/prereg/E4-P-full-seed43.md'
def utc():return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
MODELS={'qwen':'qwen/qwen3-235b-a22b-2507','gpt':'openai/gpt-4o-mini','gemma':'google/gemma-4-31b-it'}
def prepare():
    sys.path.insert(0,str(Path('data/silo-bench/benchmark_generator').resolve()))
    from main import BenchmarkGenerator,generate_paradigm_i_cases,generate_paradigm_ii_cases,generate_paradigm_iii_cases
    random.seed(43);g=BenchmarkGenerator(num_agents=10,output_dir=str(DATA));cases=[]
    for f in [generate_paradigm_i_cases,generate_paradigm_ii_cases,generate_paradigm_iii_cases]:cases+=f(10,g._create_case_structure)
    usable=[x for x in cases if not x['metadata']['is_segmented']]
    for x in usable:
        for k in list(x.get('metadata',{})):
            if 'time' in k or 'date' in k:del x['metadata'][k]
        freeze(DATA/(x['case_id']+'_n10.json'),x)
    return len(usable)
def build_trace(ledger,inst,model):
    shards=shards_from_silobench(inst);units=[];scores=[]
    contexts=[{'unit_id':f'source:a{i}','agent_id':i,'text':format_shard_context(s)} for i,s in enumerate(shards)]
    for i,s in enumerate(shards):
        raw=ledger.call(f'extract/{i}',model,messages(_EXTRACTION_SYSTEM,_build_extraction_prompt(contexts[i]['text'],inst['question'],3)))
        us=_parse_units(raw,3);units.append(us);ss=[]
        for j,u in enumerate(us):ss.append(parse_score_json(ledger.call(f'score/{i}/{j}',model,messages(_SCORING_SYSTEM,_build_scoring_prompt(inst['question'],u)),max_tokens=512)))
        scores.append(ss)
    pool=[{'unit_id':f'pool:a{i}:u{j}','agent_id':i,'text':u} for i,us in enumerate(units) for j,u in enumerate(us)]
    board=[next(p for p in pool if p['agent_id']==i and p['text']==u) for i,us in enumerate(units) for u in _topk_select(us,scores[i],1)]
    t={'instance_id':inst['id'],'trace_id':digest([inst['id'],model]),'model':model,'dataset':'silobench','k':1,'n_agents':10,'question':inst['question'],'gold_answer':inst['answer'],
       'source_contexts':contexts,'source_supports':[dict(x,unit_id=x['unit_id'].replace('source','gold')) for x in contexts],
       'checkpoints':{'extraction':pool,'transmission':board,'board':board},'scores':scores,'pool_units':pool,'board_units':board}
    sy,us=original_prompt(t,board);t['answer_text']=ledger.call('baseline',model,messages(sy,us),max_tokens=4096)
    t['answer_matches_gold']=bool(silobench_exact_match(extract_answer(t['answer_text']),{'answer':t['gold_answer']}))   # stored only; never used to filter
    return t
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--model',choices=list(MODELS));ap.add_argument('--execute',action='store_true');ap.add_argument('--max-calls',type=int)
    ap.add_argument('--retry-missing',action='store_true',help='retry ONLY traces with no file yet (lead-approved retry of connection failures), fresh ledger under <model>/retry/');a=ap.parse_args()
    if a.prepare:print(json.dumps({'usable_tasks':prepare()}),flush=True);return
    model=MODELS[a.model];insts=sorted(load_silobench(path=str(DATA),n_agents_filter=10),key=lambda x:x['id']);out=ROOT/a.model;(out/'traces').mkdir(parents=True,exist_ok=True)
    if a.retry_missing:
        insts=[x for x in insts if not (out/'traces'/(digest([x['id']+'::seed43',model])+'.json')).exists()]   # missing = no trace file yet
        led=out/'retry'
    else:led=out
    print(json.dumps({'model':model,'tasks':len(insts),'max_calls_upper_bound':len(insts)*41,'retry':a.retry_missing,'execute':a.execute,'start_utc':utc()}),flush=True)
    if not a.execute:return
    cfg={'experiment':'E4-P seed43 sources'+(' retry' if a.retry_missing else ''),'model':model,'dataset_seed':43,'k':1,'n_agents':10,'tasks':[x['id'] for x in insts],'pricing':'rebuttal/pilots/20261108_review10/pricing.json'}
    ledger=CallLedger(led,cfg,PREREG,a.max_calls);done=failed=0
    try:
        for n,inst in enumerate(insts,1):
            inst=dict(inst);inst['id']=inst['id']+'::seed43'
            try:
                t=build_trace(ledger,inst,model);freeze(out/'traces'/(t['trace_id']+'.json'),t);done+=1;print(f'{n}/{len(insts)} ok {utc()}',flush=True)
            except Exception as e:
                failed+=1;print(f'{n}/{len(insts)} FAILED {type(e).__name__} {utc()}',flush=True)   # failed traces are logged, never replaced
                if 'cap reached' in str(e):break
    finally:ledger.close()
    res=[r for r in ledger.done.values()]
    summ={'traces_done':done,'traces_failed':failed,'calls':len(ledger.started),'failed_calls':sum(not r['success'] for r in res),'cost_usd':round(sum(r.get('cost_usd') or 0 for r in res),4),'end_utc':utc()}
    (led/'summary.json').write_text(json.dumps(summ,indent=1));print(json.dumps(summ),flush=True)
if __name__=='__main__':main()
