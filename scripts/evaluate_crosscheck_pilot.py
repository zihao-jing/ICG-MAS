"""Apply the Judge-labelling-v4 decision rule to the GPT-4o-mini pilot; agreement with Gemini on the same items."""
import json
from pathlib import Path
OUT=Path('rebuttal/pilots/20261108_crosscheck_pilot');GEM='google/gemini-3.6-flash'
EVIDENCE=('extraction_omission','selection_omission','distortion')
def contradictions(task,o):
    out=[]
    if task=='E2_wave1_base_screening':
        if o.get('eligible')=='yes' and o.get('defect_free')!='yes':out.append('eligible=yes while defect_free!=yes')
        if o.get('defect_free')=='yes' and o.get('any_partial_or_distorted_carrier')=='yes':out.append('defect_free=yes while a partial/distorted carrier is reported')
    if task=='E2_partB_natural_failure':
        n=len(o.get('defects') or [])
        if o.get('class')=='single' and n!=1:out.append(f'class=single with {n} defects')
        if o.get('class')=='multiple' and n<2:out.append(f'class=multiple with {n} defects')
    if task=='E2_wave2_post_injection':
        if o.get('exactly_one_critical_defect')=='yes' and o.get('other_critical_facts_unchanged')=='no':out.append('exactly one defect=yes while other facts changed')
    return out
def main():
    G=[json.loads(f.read_text()) for d in ('rebuttal/pilots/20261108_judge_pilot','rebuttal/pilots/20261108_judge_pilot2') for f in sorted(Path(d,'parsed').glob('*.json'))]
    gem={(p['task'],p['item']):p for p in G if p['model']==GEM and p['valid']}
    P=[json.loads(f.read_text()) for f in sorted((OUT/'parsed').glob('*.json'))]
    calls=[r for r in map(json.loads,(OUT/'calls.jsonl').read_text().splitlines()) if r['event']=='result']
    valid=all(p['valid'] for p in P) and len(P)==5
    w2=[p for p in P if p['task']=='E2_wave2_post_injection' and p['valid']];fields=['exactly_one_critical_defect','other_critical_facts_unchanged','wrong_in_two_reruns','one_visible_step_changed_if_aggregation']
    no_once=any(p['parsed'].get(f)=='no' for p in w2 for f in fields)
    impossible=[p['item'] for p in w2 if p['item'].split(':')[1] in EVIDENCE and p['parsed'].get('one_visible_step_changed_if_aggregation')=='yes']
    contr=[{'item':p['item'],'what':contradictions(p['task'],p['parsed'])} for p in P if p['valid'] and contradictions(p['task'],p['parsed'])]
    cond={'1_every_output_format_valid':valid,'2_answers_no_at_least_once_on_wave2':no_once,'3_no_impossible_answer':not impossible,'4_no_self_contradiction':not contr}
    f={'E2_wave1_base_screening':'defect_free','E2_wave2_post_injection':'exactly_one_critical_defect','E2_partB_natural_failure':'class'};pairs=[]
    for p in P:
        if p['valid'] and (p['task'],p['item']) in gem:pairs.append((p['task'],p['item'],str(p['parsed'].get(f[p['task']])),str(gem[(p['task'],p['item'])]['parsed'].get(f[p['task']]))))
    k=sum(a==b for _,_,a,b in pairs)
    out={'conditions':cond,'discriminates':all(cond.values()),'impossible_answers':impossible,'self_contradictions':contr,'calls':len(calls),'failed_calls':sum(not r['success'] for r in calls),'cost_usd':round(sum(r.get('cost_usd') or 0 for r in calls),5),
      'tokens':{'prompt':sum((r['tokens'] or {}).get('prompt_tokens',0) for r in calls),'completion':sum((r['tokens'] or {}).get('completion_tokens',0) for r in calls)},
      'agreement_with_gemini':{'n':len(pairs),'agree':k,'pairs':pairs},
      'wave2_answers':[{ 'item':p['item'],**{x:p['parsed'].get(x) for x in fields}} for p in w2],'outcome':'proposed to the lead as a cross-check (not switched on)' if all(cond.values()) else 'E2 has no cross-check; credibility rests on the 20 author spot-checks and the judge-quality rates'}
    (OUT/'crosscheck_pilot_result.json').write_text(json.dumps(out,indent=1,ensure_ascii=False));print(json.dumps(out,indent=1,ensure_ascii=False))
if __name__=='__main__':main()
