"""Pilot of the constructed same-volume control (E4-v5 A2) on RESERVED Silo-Bench items (n = 20; no evaluation uses n = 20).

Part 1 (offline, no calls): feasibility grid of A2 as written over all 26 reserved tasks x stand-in repair sizes.
Part 2: pre-specified pairs P1-P3 (first 3 instances by SHA, repair stand-in 2 units / 50 tokens) and mechanism pairs M1-M3
(first 3 feasible grid cells by SHA; feasible by construction, labelled as mechanism checks) with the Qwen check and redraws.
Part 3: an exploratory variant (unit = whole records joined) is measured for FEASIBILITY ONLY; it is not A2 and is never run with calls.
Run: python -m scripts.pilot_constructed_control --execute --max-calls 20
"""
import argparse,json,re
from pathlib import Path
from src.audit.base_tokenizers import count_added_tokens
from src.audit.constructed_control import split_segments,select_segments,build_control,qwen_check_messages,parse_check,sha_order
from src.audit.pilot_common import CallLedger,digest
from src.eval.silo_bench_loader import load_silobench
OUT=Path('rebuttal/pilots/20261108_control_pilot');MODEL='qwen/qwen3-235b-a22b-2507';SIZES=[(1,25),(1,50),(2,50),(3,50),(3,80)];STAND_IN=(2,50)
count=lambda s:count_added_tokens(MODEL,s)
def shards(inst):
    import json as j
    raw=j.loads(Path('data/silo-bench/benchmarks/'+inst['id']+'.json').read_text());return {int(a['agent_id']):a['input_shard'] for a in raw['agent_configs']}
def exploratory_joined(segs,case_id,arm,units,tokens):
    """NOT A2. Unit = consecutive SHA-ordered whole records joined until the unit reaches its share of the token target (+-10% overall)."""
    toks=[count(s) for s in segs];order=sha_order(len(segs),case_id,arm);lo,hi=.9*tokens,1.1*tokens;per=tokens/units;units_text=[];pos=0;total=0
    for u in range(units):
        cur=[];ct=0
        while pos<len(order) and (ct<per*0.9 or not cur):
            if total+ct+toks[order[pos]]>hi:break
            cur.append(order[pos]);ct+=toks[order[pos]];pos+=1
            if ct>=per*0.9:break
        if not cur:return None
        units_text.append(' '.join(segs[i] for i in cur));total+=ct
    return units_text if lo<=total<=hi else None
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--max-calls',type=int,required=True);a=ap.parse_args()
    inst=sorted(load_silobench(n_agents_filter=20),key=lambda i:i['id']);assert len(inst)==26 and all(i['id'].endswith('_n20') for i in inst)
    sh={i['id']:shards(i) for i in inst};grid=[]
    for i in inst:
        segs=split_segments(sh[i['id']][1]);avg=sum(count(s) for s in segs)/len(segs)
        for u,t in SIZES:
            sel=select_segments(segs,i['id'],'V-ext',u,t,count);ex=exploratory_joined(segs,i['id'],'V-ext',u,t)
            grid.append({'instance':i['id'],'units':u,'tokens':t,'n_segments':len(segs),'mean_segment_tokens':round(avg,1),'a2_feasible':sel is not None,'exploratory_joined_feasible':ex is not None})
    summary={'sizes':SIZES,'by_size':{f'{u}u/{t}t':{'a2_feasible':sum(g['a2_feasible'] for g in grid if (g['units'],g['tokens'])==(u,t)),'exploratory_joined_feasible':sum(g['exploratory_joined_feasible'] for g in grid if (g['units'],g['tokens'])==(u,t)),'of':26} for u,t in SIZES},
             'segment_tokens_by_task':{i['id']:next(g['mean_segment_tokens'] for g in grid if g['instance']==i['id']) for i in inst}}
    P=sorted(inst,key=lambda i:(digest(['E4-pilot-v1',42,i['id']]),i['id']))[:3]
    pairs=[{'pair':f'P{n+1}','kind':'pre-specified','instance':i['id'],'units':STAND_IN[0],'tokens':STAND_IN[1]} for n,i in enumerate(P)]
    feas=sorted([g for g in grid if g['a2_feasible']],key=lambda g:(digest(['E4-pilot-mech',42,g['instance'],g['units'],g['tokens']]),g['instance']))[:3]
    pairs+=[{'pair':f'M{n+1}','kind':'mechanism check (feasible by construction)','instance':g['instance'],'units':g['units'],'tokens':g['tokens']} for n,g in enumerate(feas)]
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'feasibility_grid.json').write_text(json.dumps({'summary':summary,'grid':grid},indent=1))
    print(json.dumps({'pairs':len(pairs),'summary':summary['by_size'],'execute':a.execute}),flush=True)
    if not a.execute:return
    ledger=CallLedger(OUT,{'pricing':'rebuttal/pilots/20261108_review9/pricing.json','pairs':pairs,'model':MODEL},'rebuttal/pilots/prereg/E4-v5.md',a.max_calls);results=[]
    try:
        for p in pairs:
            shard=sh[p['instance']];donor,target=str(shard[1]),str(shard[0])
            def check(text,p=p,n=[0]):
                n[0]+=1
                try:raw=ledger.call(f"{p['pair']}|check{n[0]}",MODEL,qwen_check_messages(text,target,donor),max_tokens=200,temperature=0)
                except Exception as e:return None
                (OUT/'raw').mkdir(exist_ok=True);(OUT/'raw'/f"{p['pair']}_check{n[0]}.txt").write_text(raw)
                return parse_check(raw)
            r=build_control(donor,target,p['instance'],'V-ext',p['units'],p['tokens'],count,check)
            r.update(p,donor_agent=1,donor_is_fallback=True,target_agent=0,needed_fact_is='the target agent shard');results.append(r)
            print(p['pair'],'built' if r['built'] else r['label'],'redraws',r['redraws'],flush=True)
    finally:ledger.close()
    (OUT/'pilot_results.json').write_text(json.dumps(results,indent=1,ensure_ascii=False))
if __name__=='__main__':main()
