"""Summarise the judge pilot from the ledger and parsed outputs. Reads only pilot files."""
import json
from collections import defaultdict
from pathlib import Path
OUT=Path('rebuttal/pilots/20261108_judge_pilot')
FULL={'E1_fact_labelling':240,'E2_wave1_base_screening':68,'E2_partB_natural_failure':126}   # planned full-run calls per task and model
def kappa(a,b):
    cats=sorted(set(a)|set(b))
    if len(a)<2:return None
    po=sum(x==y for x,y in zip(a,b))/len(a);pe=sum((a.count(c)/len(a))*(b.count(c)/len(b)) for c in cats)
    return None if pe==1 else (po-pe)/(1-pe)
def main():
    rows=[json.loads(l) for l in (OUT/'calls.jsonl').read_text().splitlines()];res=[r for r in rows if r['event']=='result']
    parsed=[json.loads(f.read_text()) for f in sorted((OUT/'parsed').glob('*.json'))]
    by=defaultdict(lambda:{'calls':0,'failed_calls':0,'valid':0,'prompt_tokens':0,'completion_tokens':0,'cost_usd':0.0,'seconds':0.0,'truncated':0})
    key2task={}
    for p in parsed:key2task[(p['task'],p['item'],p['model'])]=p
    for r in res:
        task=r['key'].split('|')[0];k=(task,r['model_id']);b=by[k];b['calls']+=1;b['failed_calls']+=not r['success'];b['seconds']+=r.get('seconds',0)
        u=r.get('tokens') or {};b['prompt_tokens']+=u.get('prompt_tokens',0);b['completion_tokens']+=u.get('completion_tokens',0);b['cost_usd']+=r.get('cost_usd') or 0
        b['truncated']+=(r.get('finish_reason')=='length')
    for p in parsed:by[(p['task'],p['model'])]['valid']+=bool(p['valid'])
    table=[]
    for (task,model),b in sorted(by.items()):
        n=b['calls'];per=b['cost_usd']/n if n else 0
        table.append(dict(task=task,model=model,**{k:(round(v,5) if isinstance(v,float) else v) for k,v in b.items()},schema_valid_rate=round(b['valid']/n,3) if n else None,
            cost_per_item=round(per,5),mean_prompt_tokens=round(b['prompt_tokens']/n) if n else None,mean_completion_tokens=round(b['completion_tokens']/n) if n else None,
            extrapolated_full_calls=FULL[task],extrapolated_full_cost_usd=round(per*FULL[task],3)))
    agree={}
    g=lambda task,model:{p['item']:p for p in parsed if p['task']==task and p['model']==model and p['valid']}
    for task,field in [('E2_wave1_base_screening','defect_free'),('E2_wave1_base_screening','eligible'),('E2_partB_natural_failure','class')]:
        a,b=g(task,'google/gemini-3.6-flash'),g(task,'mistralai/mistral-small-2603');common=sorted(set(a)&set(b))
        x=[str(a[i]['parsed'][field]) for i in common];y=[str(b[i]['parsed'][field]) for i in common]
        agree[f'{task}:{field}']={'n_common_valid':len(common),'agree':sum(i==j for i,j in zip(x,y)),'percent':round(100*sum(i==j for i,j in zip(x,y))/len(common),1) if common else None,'kappa':kappa(x,y),'pairs':list(zip(common,x,y))}
    out={'per_task_model':table,'gemini_mistral_agreement':agree,'note':'Items are reserved pilot items only. n is 3-5, so agreement figures are descriptive, not estimates.'}
    (OUT/'pilot_summary.json').write_text(json.dumps(out,indent=1,ensure_ascii=False));print(json.dumps(out,indent=1,ensure_ascii=False)[:5000])
if __name__=='__main__':main()
