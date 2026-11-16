"""Frozen-output format diagnostics and strict/code-only sensitivity; no prompt edits."""
import json,re
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from src.audit.official_adapters import parse_r1,r1_prompt
from src.audit.pilot_common import render_trace,digest
from src.audit.base_tokenizers import count_added_tokens
P=Path('rebuttal/pilots');O=P/'20261108_review3'
def r1_valid(raw,steps):
 p=parse_r1(raw,steps);causes=[]
 if not p['agent']:causes.append('missing agent')
 elif not p['agent_in_trace']:causes.append('other: agent outside trace')
 if not p['step_in_trace']:causes.append('step format/range')
 if not p['valid_mode_code']:causes.append('other: invalid/missing mode code')
 elif not p['valid_mode_pair']:causes.append('missing mode name')
 strict=not causes;code=bool(p['parses'] and p['agent_in_trace'] and p['step_in_trace'] and p['valid_mode_code'])
 return p,causes,strict,code

def ww_valid(output,steps):
 raw=output['stdout'];a=re.search(r'Agent Name:\s*([^\n]+)',raw,re.I);s=re.search(r'Step Number:\s*(\d+)',raw,re.I);causes=[]
 if 'No decisive errors found' in raw and not a:causes.append('other: released no-error abstention')
 elif not a:causes.append('missing agent')
 if s and not 0<=int(s[1])<len(steps):causes.append('step format/range')
 elif not s and a:causes.append('step format/range')
 if a and a[1].strip() not in {x['agent'] for x in steps}:causes.append('other: agent outside trace')
 if not causes and not(a and s):causes.append('other: incomplete attribution')
 return {'agent':a[1].strip() if a else None,'canonical_step':str(int(s[1])+1) if s else None},causes,not causes,not causes

def main():
 actions={r['instance_id']:r for r in json.loads((P/'20261108_technical_inputs/actions.json').read_text())};rows=[]
 for exp,name,field in [('E2-C','e2_c_technical','outputs'),('E2-A','e2_a_technical','baselines')]:
  for f in sorted((P/('20261108_'+name)/'raw').glob('*.json')):
   package=json.loads(f.read_text());t=package.get('edited_trace',actions[package['instance_id']]);steps=render_trace(t)
   transcript='\n'.join(f"Step {s['step']} | Agent: {s['agent']}\n{s['text']}" for s in steps)
   for r in package[field]:
    if r['method'] not in ['r1','ww_step','ww_all','mast']:continue
    raw=r['raw'] if isinstance(r['raw'],str) else '\n'.join(r['raw'])
    if r['method']=='mast':
     parsed=r['parsed'];strict=code=parsed['parse_ok'];causes=[] if strict else ['other: missing MAST taxonomy flags']
    else:parsed,causes,strict,code=r1_valid(raw,steps) if r['method']=='r1' else ww_valid(r,steps)
    row={'experiment':exp,'method':r['method'],'backbone':r['backbone'],'benchmark':'MuSiQue','gold':r['gold'],'instance_id':t['instance_id'],'strict_valid':strict,'code_only_valid':code,'causes':causes,'parsed':parsed,'transcript_tokens':count_added_tokens('qwen/qwen3-235b-a22b-2507',transcript),'tokenizer':'Qwen pinned common transcript tokenizer, excludes fixed judge prompt','format':{'contiguous_steps':True,'hyphenated_agents':True,'empty_steps':sum(s['text']=='(empty)' for s in steps),'step_start':'Step N | Agent: agent-X'},'raw_path':str(f),'raw_excerpt':raw[:600]}
    # Technical injected reference only, never presented as human-validated accuracy.
    if exp=='E2-A' and r['method']=='r1':
     target={'extraction_omission':'V.1','selection_omission':'C.2','distortion':'R.1','aggregation':'R.2'}[package['injection_type']]
     row['reference_mode']=target;row['strict_mode_correct']=strict and parsed['mode']==target;row['code_only_mode_correct']=code and parsed['mode']==target
     refstage={'extraction_omission':'extraction','selection_omission':'transmission','distortion':'transmission','aggregation':'aggregation'}[package['injection_type']]
     refagent='aggregator' if package['injection_type']=='aggregation' else 'agent-'+str(t['injection']['agent'])
     predictedstage=next((x['stage'] for x in steps if str(x['step'])==parsed['canonical_step']),None)
     for scoring,valid in [('strict',strict),('code_only',code)]:
      row[scoring+'_family_correct']=valid and parsed['mode'].split('.')[0]==target.split('.')[0]
      row[scoring+'_agent_correct']=valid and parsed['agent']==refagent
      row[scoring+'_stage_correct']=valid and predictedstage==refstage
    rows.append(row)
 for f in sorted((P/'20261108_r1_structural').glob('alf*.json')):
  r=json.loads(f.read_text());parsed,causes,strict,code=r1_valid(r['raw'],r['steps']);source=next(x for x in json.loads((P/'20261108_preflight/r1_examples.json').read_text()) if x['id']==r['id']);msgs,_=r1_prompt(release=source)
  from whowhen_eval.render import get_renderer
  release=dict(source)
  for key in ('task','trajectory','ground_truth','extras'):
   if isinstance(release.get(key),str):release[key]=json.loads(release[key])
  rr=get_renderer(release['framework'])(release);native_text='\n'.join(b.text for b in rr.blocks)
  rows.append({'experiment':'R1-own','method':'r1','backbone':'qwen/qwen3-235b-a22b-2507','benchmark':'ALFWorld','gold':False,'instance_id':r['id'],'strict_valid':strict,'code_only_valid':code,'causes':causes,'transcript_tokens':count_added_tokens('qwen/qwen3-235b-a22b-2507',native_text),'raw_path':str(f),'raw_excerpt':r['raw'][:600],'format':{'step_start':'official renderer','empty_steps':None}})
 groups=defaultdict(list)
 for r in rows:groups[(r['method'],r['backbone'],r['benchmark'],r['experiment'])].append(r)
 grouped=[];quartiles=[]
 for k,rs in sorted(groups.items()):
  grouped.append({'setting':list(k),'n':len(rs),'strict_invalid':sum(not r['strict_valid'] for r in rs),'code_only_invalid':sum(not r['code_only_valid'] for r in rs),'causes':dict(Counter(c for r in rs for c in r['causes'])),'strict_mode_correct':sum(r.get('strict_mode_correct',False) for r in rs) if k[-1]=='E2-A' and k[0]=='r1' else None,'code_only_mode_correct':sum(r.get('code_only_mode_correct',False) for r in rs) if k[-1]=='E2-A' and k[0]=='r1' else None})
  if k[-1]=='E2-A' and k[0]=='r1':
   grouped[-1]['scores']={scoring:{metric:sum(r[scoring+'_'+metric+'_correct'] for r in rs) for metric in ['agent','stage','family','mode']} for scoring in ['strict','code_only']}
  usable=[r for r in rs if r['transcript_tokens'] is not None]
  if usable:
   cuts=np.quantile([r['transcript_tokens'] for r in usable],[.25,.5,.75])
   for q in range(4):
    subset=[r for r in usable if np.searchsorted(cuts,r['transcript_tokens'],side='left')==q]
    quartiles.append({'setting':list(k),'quartile':q+1,'cutpoints':cuts.tolist(),'n':len(subset),'strict_invalid':sum(not r['strict_valid'] for r in subset),'code_only_invalid':sum(not r['code_only_valid'] for r in subset)})
 (O/'baseline_diagnostics.json').write_text(json.dumps({'rows':rows,'settings':grouped,'token_quartiles':quartiles,'quartile_rule':'empirical .25/.5/.75 cuts within setting, ties kept together; empty bins allowed; common Qwen transcript tokenizer, not provider request tokens'},indent=2)+'\n')
 print(json.dumps(grouped,indent=2))
if __name__=='__main__':main()
