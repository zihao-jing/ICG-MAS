"""Check Gemini's wave-2 pilot answers: impossible answers, and wrong_in_two_reruns against the recorded rerun outputs. Reads pilot files only."""
import json,glob,re
from pathlib import Path
EVIDENCE=('extraction_omission','selection_omission','distortion')
F=['exactly_one_critical_defect','other_critical_facts_unchanged','wrong_in_two_reruns','one_visible_step_changed_if_aggregation']
def correct(text,gold):
    ans=re.sub(r'\s+',' ',text).split('USED_EVIDENCE')[0].replace('ANSWER:','').strip().lower()
    return str(gold).lower() in ans
def main():
    P=[json.loads(f.read_text()) for f in sorted(Path('rebuttal/pilots/20261108_judge_pilot2/parsed').glob('*.json'))]
    raw={}
    for f in Path('rebuttal/pilots/20261108_e2_a_technical/raw').glob('*.json'):
        d=json.loads(f.read_text());raw[d['instance_id']]=d
    act={a['instance_id']:a for a in json.loads(Path('rebuttal/pilots/20261108_technical_inputs/actions.json').read_text())}
    rows=[]
    for p in P:
        if p['task']!='E2_wave2_post_injection' or p['model']!='google/gemini-3.6-flash':continue
        iid,typ=p['item'].split(':');o=p['parsed'];reruns=raw[iid]['injected_outputs'];both_wrong=all(not correct(x,act[iid]['gold_answer']) for x in reruns)
        impossible=typ in EVIDENCE and o.get('one_visible_step_changed_if_aggregation')=='yes'
        rows.append({'item':iid,'injected_fault_type':typ,'gold':act[iid]['gold_answer'],'gemini':{k:o.get(k) for k in F},'recorded_reruns_both_wrong':both_wrong,
          'wrong_in_two_reruns_matches_record':(o.get('wrong_in_two_reruns')=='yes')==both_wrong,'impossible_answer':impossible})
    out={'items':rows,'any_impossible_answer':any(r['impossible_answer'] for r in rows),'wrong_in_two_reruns_matches':sum(r['wrong_in_two_reruns_matches_record'] for r in rows),'n':len(rows),
         'answers_no_on_wave2':any(v=='no' for r in rows for v in r['gemini'].values()),'note':'Only wrong_in_two_reruns and the aggregation-step field can be checked without a human; the other fields cannot. n = 3.'}
    Path('rebuttal/pilots/20261108_review10/gemini_wave2_check.json').write_text(json.dumps(out,indent=1));print(json.dumps(out,indent=1))
if __name__=='__main__':main()
