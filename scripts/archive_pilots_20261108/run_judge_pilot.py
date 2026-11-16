"""Judge pilots on RESERVED items only (rebuttal/judge/pilot/*_requests.json). One call per (task, item, model); no retries.

Gemini 3.6 Flash: E1 labelling, E2 wave-1 screening, Part B. Mistral-S: same E2 items. Failed calls are logged, never dropped.
Run: python -m scripts.run_judge_pilot --execute --max-calls 30   (resumable; never start a second worker)
"""
import argparse,json,re
from pathlib import Path
from src.audit.pilot_common import CallLedger,digest
J=Path('rebuttal/judge/pilot');OUT=Path('rebuttal/pilots/20261108_judge_pilot')
PLAN2=[('E2_partB_natural_failure','google/gemini-3.6-flash'),('E2_partB_natural_failure','mistralai/mistral-small-2603'),('E2_wave2_post_injection','google/gemini-3.6-flash'),('E2_wave2_post_injection','mistralai/mistral-small-2603')];GEM='google/gemini-3.6-flash';MIS='mistralai/mistral-small-2603'
PLAN=[('E1_fact_labelling',GEM),('E2_wave1_base_screening',GEM),('E2_wave1_base_screening',MIS),('E2_partB_natural_failure',GEM),('E2_partB_natural_failure',MIS)]
REQUIRED={'E1_fact_labelling':['critical_facts','sufficient_support_sets','carriers','binary_call','rationale'],
 'E2_wave1_base_screening':['defect_free','critical_facts','sufficient_support_sets','any_partial_or_distorted_carrier','target_checks','eligible','rationale'],
 'E2_partB_natural_failure':['defects','class','reference_defects','rationale'],
 'E2_wave2_post_injection':['exactly_one_critical_defect','other_critical_facts_unchanged','wrong_in_two_reruns','one_visible_step_changed_if_aggregation']}
def parse(text,task):
    s=text.strip()
    s=re.sub(r'^```(?:json)?\s*|\s*```$','',s)
    i,j=s.find('{'),s.rfind('}')
    if i<0 or j<i:return None,['no JSON object']
    try:o=json.loads(s[i:j+1])
    except Exception as e:return None,['invalid JSON: '+str(e)[:80]]
    miss=[k for k in REQUIRED[task] if k not in o]
    return o,(['missing keys: '+','.join(miss)] if miss else [])
def main():
    a=argparse.ArgumentParser();a.add_argument('--execute',action='store_true');a.add_argument('--max-calls',type=int,required=True);a.add_argument('--set',default='pilot');a=a.parse_args()
    global J,OUT,PLAN
    if a.set=='pilot2':J=Path('rebuttal/judge/pilot2');OUT=Path('rebuttal/pilots/20261108_judge_pilot2');PLAN=PLAN2
    cfg=json.loads(Path('rebuttal/pilots/configs/Judge-pilot-v2.json').read_text())
    config={'pricing':'rebuttal/pilots/20261108_review9/pricing.json','prompts_sha256':cfg['prompts_sha256'],'plan':PLAN,'max_tokens':10000,'temperature':0}
    work=[]
    for task,model in PLAN:
        for r in json.loads((J/(task+'_requests.json')).read_text())['requests']:work.append((task,model,r))
    print(json.dumps({'calls':len(work),'execute':a.execute}),flush=True)
    if not a.execute:return
    ledger=CallLedger(OUT,config,'rebuttal/pilots/prereg/Judge-labelling-v2.md',a.max_calls);(OUT/'parsed').mkdir(exist_ok=True)
    try:
        for task,model,r in work:
            key=f"{task}|{r['item']}|{model}";rec={'task':task,'item':r['item'],'model':model,'messages_sha256':r['messages_sha256']}
            try:
                raw=ledger.call(key,model,r['messages'],max_tokens=10000,temperature=0)
                o,err=parse(raw,task);rec.update(valid=not err,errors=err,parsed=o,raw=raw)
            except Exception as e:
                rec.update(valid=False,errors=['call failed: '+type(e).__name__+': '+str(e)[:160]],parsed=None,raw='')
            (OUT/'parsed'/(digest(key)+'.json')).write_text(json.dumps(rec,ensure_ascii=False,indent=1))
            print(key,'valid' if rec['valid'] else rec['errors'],flush=True)
    finally:ledger.close()
if __name__=='__main__':main()
