"""Read-only outcome summaries; no failure-group splits or label repairs."""
import json,re,hashlib
from pathlib import Path
from collections import Counter
from src.audit.official_adapters import parse_r1
from src.audit.pilot_common import render_trace
P=Path('rebuttal/pilots');D=P/'20261108_preflight'
def load(p):return json.loads(p.read_text())
def calls(p):return [json.loads(s) for s in (p/'calls.jsonl').read_text().splitlines() if json.loads(s)['event']=='result'] if (p/'calls.jsonl').exists() else []
def summary(p):
 r=calls(p);return {'responses':len(r),'usd':sum(x.get('cost_usd') or 0 for x in r),'seconds':sum(x['seconds'] for x in r),'api_errors':sum(not x['success'] for x in r),'unknown_costs':sum(x.get('cost_usd') is None for x in r),'finish_reasons':dict(Counter(x.get('finish_reason') for x in r)),'completed_items':len(list((p/'raw').glob('*.json')))}
def main():
 names=['e1','e1_calibration','e1_v2','e4_technical','e4_p_technical','e2_c_technical','e2_a_technical','e2_a_proxy','e4_p_seed43','r1_structural','ww_sanity']
 out={n:summary(P/('20261108_'+n)) for n in names}
 rows=[load(f) for f in (P/'20261108_e1_v2/matcher').glob('*.json')];cells={}
 for r in rows:
  key=r['base_model']+'/k'+str(r['k']);v=cells.setdefault(key,{'traces':0,'failed':0,'logical_calls':0,'retried_calls':0})
  v['traces']+=1;v['failed']+=r['status']!='ok'
  for c in [r.get('facts_call'),r.get('carrier_call')]:
   if c:v['logical_calls']+=1;v['retried_calls']+=c['retried']
 out['e1_v2']['cells']=cells
 r1=[]
 for f in sorted((P/'20261108_r1_structural').glob('alf*.json')):
  r=load(f);r1.append({'id':r['id'],**parse_r1(r['raw'],r['steps'])})
 out['r1_structural']['checks']=r1
 matches=[]
 for f in sorted((P/'20261108_e4_technical/raw').glob('*.json')):
  for r in load(f):
   if r['arm'] in ['R-ext','R-sel','R-dist']:matches.append(r['control_match'])
 out['e4_technical']['volume_controls']={'matched':sum(r['matched'] for r in matches),'total':len(matches)}
 fidelity=[]
 for f in (P/'20261108_e4_technical/raw').glob('*.json'):
  fidelity += [r['fidelity'] for r in load(f) if r.get('fidelity')]
 out['e4_technical']['fidelity_failed']=sum(r['status']!='ok' for r in fidelity);out['e4_technical']['fidelity_retried']=sum(r['retried'] for r in fidelity)
 actions={r['instance_id']:r for r in load(P/'20261108_technical_inputs/actions.json')}
 for name,field in [('e2_c_technical','outputs'),('e2_a_technical','baselines')]:
  errors=Counter();total=Counter()
  for f in (P/('20261108_'+name)/'raw').glob('*.json'):
   package=load(f);trace=package.get('edited_trace',actions[package['instance_id']])
   for r in package.get(field,[]):
    method=r['method'];total[method]+=1
    if method=='r1':
     parsed=parse_r1(r['raw'],render_trace(trace));ok=parsed['parses'] and parsed['valid_mode_pair'] and parsed['step_in_trace']
    elif method=='mast':ok=r['parsed']['parse_ok']
    else:
     raw=r['stdout'];ok=bool(re.search(r'Agent Name:\s*\S+',raw,re.I) and re.search(r'Step Number:\s*\d+',raw,re.I))
    errors[method]+=not ok
  out[name]['format_failures']={k:{'failed':errors[k],'total':v} for k,v in total.items()}
 # Native W&W released substring evaluator and strict exact sensitivity; partial denominators explicit.
 ww=[]
 for f in (P/'20261108_ww_sanity/raw').glob('*.json'):
  r=load(f);a=re.search(r'Agent Name:\s*([\w_]+)',r['stdout'],re.I);s=re.search(r'Step Number:\s*(\d+)',r['stdout'],re.I)
  aa=str(r['reference_agent']);ss=str(r['reference_step']);ww.append({'gold':r['gold'],'system':r['system_type'],'parse':bool(a and s),'agent':bool(a and aa in a[1]),'step':bool(s and ss in s[1]),'agent_exact':bool(a and aa==a[1]),'step_exact':bool(s and ss==s[1])})
 out['ww_sanity']['evaluation']={'completed_conditions':len(ww),'planned_conditions':368,**{k:sum(r[k] for r in ww)/len(ww) if ww else None for k in ['parse','agent','step','agent_exact','step_exact']}}
 out['ww_sanity']['evaluation']['cells']=[{'gold':g,'system':s,'n':len(rs),**{k:sum(r[k] for r in rs)/len(rs) if rs else None for k in ['agent','step']}} for g in [False,True] for s in ['Algorithm-Generated','Hand-Crafted'] if (rs:=[r for r in ww if r['gold']==g and r['system']==s])]
 (D/'technical_progress.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
