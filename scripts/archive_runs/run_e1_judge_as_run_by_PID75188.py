"""E1 judge run (Judge-labelling-v5, frozen version E1-judge-v1) on the 80 held-out IDs x 3 base models = 240 traces. SEALED.

Outputs go to rebuttal/results/batch1/E1_judge_sealed/. This script prints and logs ONLY call counts, format validity, failed calls,
refusals, tokens and cost: never a label value or distribution. Nobody opens the sealed folder until the lead confirms the anchor labels are in.
Run: python -m scripts.run_e1_judge            (dry run: counts only)
     python -m scripts.run_e1_judge --execute --max-calls 260
"""
import argparse,hashlib,json,re,sys
from pathlib import Path
from src.audit.pilot_common import CallLedger,digest
from src.audit.judge_render import trace_text
SEALED=Path('rebuttal/results/batch1/E1_judge_sealed');SUMMARY=Path('rebuttal/results/batch1/E1_judge_run_summary.json')
VERSION=Path('rebuttal/judge/E1-judge-v1.json');PREREG='rebuttal/pilots/prereg/Judge-labelling-v5.md';LOCK=Path('rebuttal/pilots/20261108_review6/e1_n80_locked_manifest.json')
REFUSAL=re.compile(r"^\s*(i'?m sorry|i cannot|i can'?t|i am unable|i'm unable)",re.I)
def heldout_ids():
    lock=json.loads(LOCK.read_text());ids=[i for v in lock['strata'].values() for i in v['ids']];assert len(ids)==len(set(ids))==80
    return ids
def build_items(packages,ids,version):
    items=[]
    for i in ids:
        for m in ('qwen235b','gpt4omini','gemma31b'):
            t=packages[(m,i)];msgs=[{'role':'system','content':version['system']},{'role':'user','content':version['user_template'].format(trace=trace_text(t))}]
            items.append({'key':digest(['E1-judge',42,i,m]),'instance':i,'model':m,'messages':msgs})
    return sorted(items,key=lambda r:(digest(['E1-judge',42,r['instance'],r['model']]),r['instance']))
def parse(text,required):
    s=re.sub(r'^```(?:json)?\s*|\s*```$','',(text or '').strip());a,b=s.find('{'),s.rfind('}')
    if a<0 or b<a:return None,False
    try:o=json.loads(s[a:b+1])
    except Exception:return None,False
    return o,all(k in o for k in required)
def run(items,version,ledger_dir,sealed,max_calls,transport=None,out=print):
    """Returns a counts-only summary. Label content is written only inside `sealed` (and the ledger in `ledger_dir`)."""
    sealed=Path(sealed);(sealed/'outputs').mkdir(parents=True,exist_ok=True)
    cfg={'version':version['name'],'version_sha256':version['e1_judge_v1_sha256'],'pricing':'rebuttal/pilots/20261108_review10/pricing.json','n':len(items),'max_tokens':version['generation']['max_tokens']}
    ledger=CallLedger(ledger_dir,cfg,PREREG,max_calls,transport=transport)
    c={'calls':0,'valid':0,'format_invalid':0,'failed_calls':0,'refusals':0,'prompt_tokens':0,'completion_tokens':0,'cost_usd':0.0}
    try:
        for n,it in enumerate(items,1):
            ok='failed'
            try:
                raw=ledger.call(it['key'],version['model'],it['messages'],max_tokens=version['generation']['max_tokens'],temperature=0)
                o,valid=parse(raw,version['required_keys']);refusal=bool(REFUSAL.match(raw or '')) or not (raw or '').strip()
                (sealed/'outputs'/(it['key']+'.json')).write_text(json.dumps({'instance_id':it['instance'],'model':it['model'],'valid':valid,'parsed':o,'raw':raw},ensure_ascii=False))
                c['valid']+=valid;c['format_invalid']+=(not valid);c['refusals']+=refusal;ok='valid' if valid else 'format_invalid'
            except Exception:c['failed_calls']+=1
            c['calls']+=1;r=list(ledger.done.values())[-1] if ledger.done else None   # latest result row
            if r and r.get('key')==it['key']:
                u=r.get('tokens') or {};c['prompt_tokens']+=u.get('prompt_tokens',0);c['completion_tokens']+=u.get('completion_tokens',0);c['cost_usd']+=r.get('cost_usd') or 0
            out(f"{n}/{len(items)} {ok}")   # counts only
    finally:ledger.close()
    c['cost_usd']=round(c['cost_usd'],4);return c
def write_manifest(sealed):
    sealed=Path(sealed);lines=[f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(sealed)}" for p in sorted(sealed.rglob('*')) if p.is_file() and p.name!='MANIFEST.sha256']
    m=sealed/'MANIFEST.sha256';m.write_text('\n'.join(lines)+'\n');return hashlib.sha256(m.read_bytes()).hexdigest(),len(lines)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--max-calls',type=int,required=True);a=ap.parse_args()
    version=json.loads(VERSION.read_text());ids=heldout_ids()
    from scripts.build_final_author_packet import packages
    pk=packages(set(ids));items=build_items(pk,ids,version)
    print(json.dumps({'version':version['name'],'instances':len(ids),'traces':len(items),'execute':a.execute}),flush=True)
    if len(items)!=240:print('ERROR: expected 240 traces',flush=True);sys.exit(1)
    if not a.execute:return
    c=run(items,version,SEALED,SEALED,a.max_calls,out=lambda s:print(s,flush=True))
    mh,nf=write_manifest(SEALED);c.update(sealed_manifest_sha256=mh,sealed_files=nf,version_sha256=version['e1_judge_v1_sha256']);SUMMARY.write_text(json.dumps(c,indent=1))
    print(json.dumps(c),flush=True)
if __name__=='__main__':main()
