"""Second judge-pilot set (reserved items only): +2 Part B items from wrong calibration traces, and 3 wave-2 before/after pairs.
Wave-2 pairs: the technical-pilot injections on reserved bases, first 3 by ascending SHA-256 of ["E2-pilot2-wave2", 42, instance_id]. No calls."""
import json
from pathlib import Path
from src.audit.pilot_common import digest
from scripts.prepare_judge_pilot import trace_text
P=Path('rebuttal/pilots');J=Path('rebuttal/judge');OUT=J/'pilot2'
CAL=[('qwen/qwen3-235b-a22b-2507','2hop__532383_768138'),('google/gemma-4-31b-it','2hop__532383_768138')]
def main():
    prompts=json.loads((J/'judge_prompts_v3.json').read_text())['prompts'];actions={a['instance_id']:a for a in json.loads((P/'20261108_technical_inputs/actions.json').read_text())}
    raw={}
    for f in sorted((P/'20261108_e2_a_technical/raw').glob('*.json')):
        d=json.loads(f.read_text());raw[d['instance_id']]=d
    def req(task,key,text):
        m=[{'role':'system','content':prompts[task]['system']},{'role':'user','content':prompts[task]['user_template'].format(trace=text)}]
        return {'item':key,'messages_sha256':digest(m),'est_input_tokens':sum(len(x['content']) for x in m)//4,'messages':m}
    pb=[]
    for model,iid in CAL:
        for f in sorted((P/'20261108_e1_calibration/traces').glob('*.json')):
            t=json.loads(f.read_text())
            if t['k']==1 and t['model']==model and t['instance_id']==iid:pb.append(req('E2_partB_natural_failure',f'cal:{iid}:{model.split("/")[0]}',trace_text(t)))
    ids=sorted(raw,key=lambda i:(digest(['E2-pilot2-wave2',42,i]),i))[:3];w2=[]
    for i in ids:
        d=raw[i];a=actions[i];fact=next((f['text'] for f in a['facts']['facts'] if f['fact_id']==d['fact_id']),d['fact_id'])
        after=dict(a,**{k:d['edited_trace'][k] for k in ('checkpoints','answer_text') if k in d['edited_trace']})
        w2.append(req('E2_wave2_post_injection',f"{i}:{d['injection_type']}",'BEFORE\n'+trace_text(a)+'\n\nAFTER (declared edit: '+d['injection_type'].replace('_',' ')+' of this fact: "'+fact+'")\n'+trace_text(after)+'\n\nRERUN ANSWERS AFTER EDIT\n'+'\n---\n'.join(d['injected_outputs'])))
    OUT.mkdir(exist_ok=True)
    for task,rs in [('E2_partB_natural_failure',pb),('E2_wave2_post_injection',w2)]:
        (OUT/(task+'_requests.json')).write_text(json.dumps({'judge_model':'google/gemini-3.6-flash','n':len(rs),'requests':rs},indent=1,ensure_ascii=False)+'\n')
    print({'partB':[r['item'] for r in pb],'wave2':[r['item'] for r in w2]})
if __name__=='__main__':main()
