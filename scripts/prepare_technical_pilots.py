"""Freeze five reserved technical cases using dev matcher labels, never human sheets."""
import json,re
from pathlib import Path
from src.audit.pilot_common import digest,freeze,ranked
from src.audit.semantic_matcher import diagnose
from src.audit.pilot_selection import choose_target_donor,placement_hash_agent
from src.audit.alignment import _jaccard_sim
from src.eval.evaluate import answer_f1
from src.eval.data_loader import load_musique
from src.protocols.base import extract_answer

ROOT=Path('rebuttal/pilots')
def main():
 c=json.loads((ROOT/'configs/E1-v2.json').read_text());old=Path(c['source_traces']);rows=[]
 models=c['base_models'];instances={r['id']:r for r in load_musique()}
 for index,iid in enumerate(c['pilot_ids']):
  model=models[index%len(models)];key=digest([iid,model,1]);t=json.loads((old/(key+'.json')).read_text());m=json.loads((Path(c['output'])/'matcher'/(key+'.json')).read_text())
  if m['status']!='ok':raise ValueError('Cannot silently omit failed matcher case')
  facts=m['facts'];carriers=m['carriers'];correct=answer_f1(extract_answer(t['answer_text']),instances[iid])>=1
  diagnosis=diagnose(facts,carriers,correct)
  factmap={f['fact_id']:f for f in facts['facts']};unitmap={u['unit_id']:u for u in t['checkpoints']['extraction']}
  bad=next((r for r in carriers['facts'] if not r['extraction']),None) if diagnosis=='extraction_omission' else next((r for r in carriers['facts'] if not r['board']),None) if diagnosis=='selection_omission' else next((r for r in carriers['facts'] if any(x['fidelity']=='distorted' for x in r['board'])),None)
  selected=factmap[bad['fact_id']] if bad else facts['facts'][0]
  support_agents={int(s.rsplit('a',1)[1]) for f in facts['facts'] for s in f['source_ids']}
  candidates={int(s.rsplit('a',1)[1]) for s in selected['source_ids']}
  target=choose_target_donor(t,{'eligible_target_agents':list(candidates),'support_holder_agents':list(support_agents)})
  def next_units(agent):
   pool=[u for u in t['checkpoints']['extraction'] if u['agent_id']==agent];boardids={u['unit_id'] for u in t['checkpoints']['board']}
   scores=t['scores'][agent]
   return [u['unit_id'] for _,u in sorted(zip(scores,pool),key=lambda x:-x[0].get('overall',x[0].get('composite',0.0))) if u['unit_id'] not in boardids][:2]
  def swap(agent):
   unit=next(u for u in t['checkpoints']['board'] if u['agent_id']==agent);context=next(s['text'] for s in t['source_contexts'] if s['agent_id']==agent)
   spans=[s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+',context) if s.strip()]
   span=sorted(spans,key=lambda s:(-_jaccard_sim(s,unit['text']),s))[0]
   assert span in context
   return {'unit_id':unit['unit_id'],'text':span,'author_checked':False,'label_status':'pilot_provisional'}
  row={**t,'answer_aliases':instances[iid].get('answer_aliases',[]),**target,'trace_id':key,'source_id':model,'n_agents':len(t['source_contexts']),'pool_units':t['checkpoints']['extraction'],
    'board_units':t['checkpoints']['board'],'facts':facts,'carriers':carriers,'label_status':'pilot_provisional','diagnosis':diagnosis,
    'hash_agent':placement_hash_agent(model,iid,len(t['source_contexts'])),'target_next_unit_ids':next_units(target['target_agent']),
    'donor_next_unit_ids':next_units(target['donor_agent']),'target_swap':swap(target['target_agent']),'donor_swap':swap(target['donor_agent'])}
  rows.append(row)
 manifest=ROOT/'20261108_technical_inputs/actions.json';freeze(manifest,rows)
 for exp in ['E4','E4-P','E2-C','E2-A']:
  oldc=json.loads((ROOT/'configs'/f'{exp}.json').read_text());out=ROOT/('20261108_'+exp.lower().replace('-','_')+'_technical')
  cfg=oldc|{'output':str(out),'label_status':'pilot_provisional','allow_full_run':False,'action_manifest':str(manifest),
    'manifest_sha256':digest(manifest.read_bytes()),'matcher_frozen':False,'prereg':str(ROOT/'prereg'/f'{exp}-technical.md'),
    'backbones':[c['judge_model'],c['strong_model']]}
  if exp=='E4-P':cfg['e4_calls']='rebuttal/pilots/20261108_e4_technical/calls.jsonl'
  freeze(ROOT/'configs'/f'{exp}-technical.json',cfg)
  text=f'''# {exp} technical pilot — not a final evaluation
User-authorised exception: dev matcher labels marked pilot_provisional may drive technical pilots only. Never export these labels to annotators, never reuse them in final evaluation. No failure-group outcome summaries.
Five reserved MuSiQue IDs: {json.dumps(c['pilot_ids'])}.
One trace per ID; base model cycles Qwen/GPT/Gemma/Qwen/GPT in fixed ID order. k=1; all approved arms/backbones retained. E2A may exercise the injection and attribution path on an unkept trace for software validation only; mark ineligible/keep=false, never count it as evidence of causal attribution accuracy. Eligibility and keep metrics are provisional, not human-certified.
Action manifest: {manifest}; SHA256 {digest(manifest.read_bytes())}. Targets, donors, source-span swaps, placement hash agents fixed therein before outcomes. Exact base tokenizers count newly inserted unit text without chat framing. Source spans are verbatim; provisional checks do not stand in for author swap checks.
Config SHA256: {digest(cfg)}. Temperature0, seed42, max4096. Ledger caps and append-only attempts apply. Carrier checks use semantic-dev-v2 and at most2 retries, no label repair. Full runs and human validation stay blocked pending lead approval of E1 criteria and sample design.
E4-P enlargement(a) remains off by default; option(b) dropped because no second paper benchmark has both requested cached failure types.
'''
  Path(cfg['prereg']).write_text(text)
 print('Frozen technical manifests/configs for five reserved IDs; no outcomes called.')
if __name__=='__main__':main()
