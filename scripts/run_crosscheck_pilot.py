"""Cross-check candidate pilot (Judge-labelling-v4): openai/gpt-4o-mini on 5 reserved items it did not generate, frozen prompts, one call each, no retry.
Run: python -m scripts.run_crosscheck_pilot --execute --max-calls 8"""
import argparse,json,re
from pathlib import Path
from src.audit.pilot_common import CallLedger,digest
MODEL='openai/gpt-4o-mini';OUT=Path('rebuttal/pilots/20261108_crosscheck_pilot')
ITEMS=[('E2_wave1_base_screening','rebuttal/judge/pilot','2hop__466700_214359'),('E2_wave1_base_screening','rebuttal/judge/pilot','2hop__809096_491515'),
       ('E2_wave2_post_injection','rebuttal/judge/pilot2','2hop__466700_214359:extraction_omission'),('E2_wave2_post_injection','rebuttal/judge/pilot2','2hop__809096_491515:distortion'),
       ('E2_partB_natural_failure','rebuttal/judge/pilot','2hop__24661_81961')]
REQUIRED={'E2_wave1_base_screening':['defect_free','critical_facts','sufficient_support_sets','any_partial_or_distorted_carrier','target_checks','eligible','rationale'],
 'E2_partB_natural_failure':['defects','class','reference_defects','rationale'],
 'E2_wave2_post_injection':['exactly_one_critical_defect','other_critical_facts_unchanged','wrong_in_two_reruns','one_visible_step_changed_if_aggregation']}
def parse(text,task):
    s=re.sub(r'^```(?:json)?\s*|\s*```$','',(text or '').strip());i,j=s.find('{'),s.rfind('}')
    if i<0 or j<i:return None,['no JSON object']
    try:o=json.loads(s[i:j+1])
    except Exception as e:return None,['invalid JSON: '+str(e)[:80]]
    miss=[k for k in REQUIRED[task] if k not in o];return o,(['missing keys: '+','.join(miss)] if miss else [])
def main():
    a=argparse.ArgumentParser();a.add_argument('--execute',action='store_true');a.add_argument('--max-calls',type=int,required=True);a=a.parse_args()
    work=[]
    for task,d,item in ITEMS:
        r=next(x for x in json.loads((Path(d)/(task+'_requests.json')).read_text())['requests'] if x['item']==item);work.append((task,item,r))
    print(json.dumps({'calls':len(work),'execute':a.execute}),flush=True)
    if not a.execute:return
    cfg={'pricing':'rebuttal/pilots/20261108_review10/pricing.json','model':MODEL,'items':[(t,i) for t,_,i in ITEMS],'max_tokens':4096,'temperature':0,'prompts_sha256':'e89cd06cd6bbe12740959be072422ff2df42304726aa00ce5b0420377a6c5098'}
    ledger=CallLedger(OUT,cfg,'rebuttal/pilots/prereg/Judge-labelling-v4.md',a.max_calls);(OUT/'parsed').mkdir(exist_ok=True)
    try:
        for task,item,r in work:
            key=f'{task}|{item}|{MODEL}';rec={'task':task,'item':item,'model':MODEL}
            try:
                raw=ledger.call(key,MODEL,r['messages'],max_tokens=4096,temperature=0);o,err=parse(raw,task);rec.update(valid=not err,errors=err,parsed=o,raw=raw)
            except Exception as e:rec.update(valid=False,errors=['call failed: '+type(e).__name__+': '+str(e)[:160]],parsed=None,raw='')
            (OUT/'parsed'/(digest(key)+'.json')).write_text(json.dumps(rec,ensure_ascii=False,indent=1));print(key,'valid' if rec['valid'] else rec['errors'],flush=True)
    finally:ledger.close()
if __name__=='__main__':main()
