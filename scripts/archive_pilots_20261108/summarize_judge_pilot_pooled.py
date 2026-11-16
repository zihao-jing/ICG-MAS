"""Pooled summary of both judge pilots (reserved items only): validity, cost, Gemini-Mistral agreement, self-contradiction, eligibility-rule disagreement."""
import json,math
from collections import defaultdict
from pathlib import Path
DIRS=[Path('rebuttal/pilots/20261108_judge_pilot'),Path('rebuttal/pilots/20261108_judge_pilot2')];GEM='google/gemini-3.6-flash';MIS='mistralai/mistral-small-2603'
def load():
    P=[];calls=[]
    for d in DIRS:
        P+=[json.loads(f.read_text()) for f in sorted((d/'parsed').glob('*.json'))]
        calls+=[r for r in map(json.loads,(d/'calls.jsonl').read_text().splitlines()) if r['event']=='result']
    return P,calls
def target_pass(c):
    return c.get('in_every_sufficient_set')=='yes' and c.get('carrier_outside_agent')=='no' and bool(c.get('feasible_fault_types'))
def contradictions(p):
    o=p['parsed'];t=p['task'];out=[]
    if o is None:return out
    if t=='E2_wave1_base_screening':
        if o.get('eligible')=='yes' and o.get('defect_free')!='yes':out.append('eligible=yes while defect_free!=yes')
        if o.get('defect_free')=='yes' and o.get('any_partial_or_distorted_carrier')=='yes':out.append('defect_free=yes while a partial/distorted carrier is reported')
    if t=='E2_partB_natural_failure':
        n=len(o.get('defects') or [])
        if o.get('class')=='single' and n!=1:out.append(f'class=single with {n} defects')
        if o.get('class')=='multiple' and n<2:out.append(f'class=multiple with {n} defects')
    if t=='E2_wave2_post_injection':
        if o.get('exactly_one_critical_defect')=='yes' and o.get('other_critical_facts_unchanged')=='no':out.append('exactly one defect=yes while other facts changed')
    if t=='E1_fact_labelling':
        try:
            sets=o.get('sufficient_support_sets') or [];first=set(sets[0]) if sets else set()
            if o.get('binary_call')=='reached_but_unused' and any(c.get('checkpoint')=='board' and c.get('fact_id') in first and c.get('fidelity') in ('absent','distorted') for c in o.get('carriers') or []):out.append('reached_but_unused while a board carrier is absent/distorted')
        except Exception:pass
    return out
def cp(k,n,a=.05):
    from math import comb
    def tail(p,lo):return sum(comb(n,i)*p**i*(1-p)**(n-i) for i in range(lo,n+1))
    lo,hi=0.0,1.0
    if k>0:
        l,h=0,1
        for _ in range(60):
            m=(l+h)/2
            if tail(m,k)<a/2:l=m
            else:h=m
        lo=h
    if k<n:
        l,h=0,1
        for _ in range(60):
            m=(l+h)/2
            if sum(comb(n,i)*m**i*(1-m)**(n-i) for i in range(0,k+1))>a/2:l=m
            else:h=m
        hi=l
    return round(lo,3),round(hi,3)
def main():
    P,calls=load();by=defaultdict(lambda:{'calls':0,'failed':0,'valid':0,'cost':0.0,'pt':0,'ct':0})
    for r in calls:
        task=r['key'].split('|')[0];b=by[(task,r['model_id'])];b['calls']+=1;b['failed']+=not r['success'];b['cost']+=r.get('cost_usd') or 0
        u=r.get('tokens') or {};b['pt']+=u.get('prompt_tokens',0);b['ct']+=u.get('completion_tokens',0)
    for p in P:by[(p['task'],p['model'])]['valid']+=bool(p['valid'])
    table=[{'task':k[0],'model':k[1],'calls':v['calls'],'schema_valid':v['valid'],'failed_calls':v['failed'],'cost_usd':round(v['cost'],4),'cost_per_item':round(v['cost']/v['calls'],5),'mean_prompt_tokens':round(v['pt']/v['calls']),'mean_completion_tokens':round(v['ct']/v['calls'])} for k,v in sorted(by.items())]
    # self-contradiction
    sc=defaultdict(lambda:{'outputs':0,'contradictory':0,'examples':[]})
    for p in P:
        if not p['valid']:continue
        s=sc[(p['task'],p['model'])];s['outputs']+=1;c=contradictions(p)
        if c:s['contradictory']+=1;s['examples'].append({'item':p['item'],'what':c})
    selfc=[{'task':k[0],'model':k[1],**{a:b for a,b in v.items()}} for k,v in sorted(sc.items())]
    # eligibility
    elig=[]
    for p in P:
        if p['task']!='E2_wave1_base_screening' or not p['valid']:continue
        o=p['parsed'];tc=o.get('target_checks') or [];df=o.get('defect_free')=='yes'
        every=df and bool(tc) and all(target_pass(c) for c in tc);anyr=df and any(target_pass(c) for c in tc)
        elig.append({'model':p['model'],'item':p['item'],'judge_eligible':o.get('eligible'),'rule_every':every,'rule_any':anyr,'disagree_every':(o.get('eligible')=='yes')!=every,'disagree_any':(o.get('eligible')=='yes')!=anyr})
    eg={m:{'n':sum(e['model']==m for e in elig),'disagree_vs_rule_every':sum(e['disagree_every'] for e in elig if e['model']==m),'disagree_vs_rule_any':sum(e['disagree_any'] for e in elig if e['model']==m)} for m in (GEM,MIS)}
    # agreement
    fields=[('E2_wave1_base_screening','defect_free'),('E2_partB_natural_failure','class'),('E2_wave2_post_injection','exactly_one_critical_defect')]
    per={};tot=0;agree=0;pe_sum=0
    for task,f in fields:
        a={p['item']:p for p in P if p['task']==task and p['model']==GEM and p['valid']};b={p['item']:p for p in P if p['task']==task and p['model']==MIS and p['valid']};common=sorted(set(a)&set(b))
        x=[str(a[i]['parsed'].get(f)) for i in common];y=[str(b[i]['parsed'].get(f)) for i in common];n=len(common);k=sum(i==j for i,j in zip(x,y))
        cats=set(x)|set(y);pe=sum((x.count(c)/n)*(y.count(c)/n) for c in cats) if n else 0
        per[f'{task}:{f}']={'n':n,'agree':k,'percent':round(100*k/n,1) if n else None,'ci95':cp(k,n) if n else None,'chance_expected_percent':round(100*pe,1),'pairs':list(zip(common,x,y))}
        tot+=n;agree+=k;pe_sum+=pe*n
    pooled={'n':tot,'agree':agree,'percent':round(100*agree/tot,1),'ci95':cp(agree,tot),'chance_expected_percent':round(100*pe_sum/tot,1),'kappa':round((agree/tot-pe_sum/tot)/(1-pe_sum/tot),3) if pe_sum/tot<1 else None}
    out={'per_task_model':table,'self_contradiction':selfc,'eligible_field_vs_rule':{'by_model':eg,'items':elig},'gemini_mistral_agreement':{'per_field':per,'pooled':pooled},'total_calls':len(calls),'failed_calls':sum(not r['success'] for r in calls),'total_cost_usd':round(sum(r.get('cost_usd') or 0 for r in calls),4)}
    Path('rebuttal/pilots/20261108_review9/judge_pilot_pooled.json').write_text(json.dumps(out,indent=1,ensure_ascii=False))
    print(json.dumps({k:out[k] for k in ('per_task_model','self_contradiction')},indent=0,ensure_ascii=False)[:3500]);print(json.dumps({'eligible':eg,'pooled':pooled,'per_field':{k:{x:v[x] for x in('n','agree','percent','ci95','chance_expected_percent')} for k,v in per.items()},'calls':out['total_calls'],'failed':out['failed_calls'],'cost':out['total_cost_usd']},indent=1))
if __name__=='__main__':main()
