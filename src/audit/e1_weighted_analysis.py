"""Weighted E1 estimates; instance clusters and lexical strata, no pass/fail threshold."""
import argparse,json,random
from collections import defaultdict,Counter
from pathlib import Path

def weighted_kappa(rows,a='human_a',b='human_b'):
 if not rows:return None
 total=sum(r['weight'] for r in rows);ca=Counter();cb=Counter();agree=0
 for r in rows:
  w=r['weight'];ca[r[a]]+=w;cb[r[b]]+=w;agree+=w*(r[a]==r[b])
 pe=sum(ca[x]*cb[x] for x in set(ca)|set(cb))/total**2
 return None if abs(1-pe)<1e-12 else (agree/total-pe)/(1-pe)
def weighted_accuracy(rows):
 return sum(r['weight']*(r.get('matcher_status')!='failed' and r.get('matcher')==r['adjudicated']) for r in rows)/sum(r['weight'] for r in rows) if rows else None

def interval(rows,stat,draws=2000,seed=42):
 if not rows:return {'estimate':None,'lo':None,'hi':None,'valid_draws':0}
 strata=defaultdict(lambda:defaultdict(list))
 for r in rows:strata[r['stratum']][r['instance_id']].append(r)
 rng=random.Random(seed);values=[]
 for _ in range(draws):
  sample=[]
  for h,groups in sorted(strata.items()):
   keys=sorted(groups)
   # Full-population rate includes dev instances as observed certainty units.
   selected=keys if h.endswith('/dev_certainty') else rng.choices(keys,k=len(keys))
   sample.extend(r for k in selected for r in groups[k])
  v=stat(sample)
  if v is not None:values.append(v)
 values.sort();n=len(values)
 return {'estimate':stat(rows),'lo':values[int(.025*(n-1))] if n else None,'hi':values[int(.975*(n-1))] if n else None,'valid_draws':n,'draws':draws}

def binary_rows(rows,partial_lost=False):
 out=[];wrong=[r for r in rows if not r['correct']]
 excluded={'partial':sum('partial' in [r[k] for k in ['human_a','human_b','adjudicated']] for r in wrong),'uncertain':sum('uncertain' in [r[k] for k in ['human_a','human_b','adjudicated']] for r in wrong)}
 for r in rows:
  if r['correct']:continue
  labels=[r[k] for k in ['human_a','human_b','adjudicated']]
  if 'uncertain' in labels:continue
  if 'partial' in labels and not partial_lost:continue
  x=dict(r)
  if partial_lost:
   for k in ['human_a','human_b','adjudicated','matcher']:
    if x.get(k)=='partial':x[k]='lost'
  out.append(x)
 return out,dict(excluded)

def analyze(facts,traces,draws=2000):
 out={'primary':{},'secondary':{},'thresholds':None}
 for metric in ['presence','fidelity']:
  rs=[r for r in facts if r['metric']==metric and r.get('adjudicated')!='uncertain' and r.get('human_a')!='uncertain' and r.get('human_b')!='uncertain']
  out['primary'][metric]={'human_kappa':interval(rs,weighted_kappa,draws),'matcher_accuracy':interval(rs,weighted_accuracy,draws),'excluded_uncertain':sum(r['metric']==metric for r in facts)-len(rs)}
 out['primary']['fidelity']['status']='reported accuracy; kappa and AC1 secondary'
 fidelity=[r for r in facts if r['metric']=='fidelity' and all(r.get(k)!='uncertain' for k in ['adjudicated','human_a','human_b'])]
 out['primary']['fidelity']['human_ac1']=interval(fidelity,weighted_ac1,draws)
 fidelity_result=out['primary'].pop('fidelity')
 out['reported_fidelity_accuracy']=fidelity_result['matcher_accuracy']
 out['secondary']['fidelity_kappa']=fidelity_result['human_kappa']
 out['secondary']['fidelity_ac1']=fidelity_result['human_ac1']
 out['secondary']['fidelity_excluded_uncertain']=fidelity_result['excluded_uncertain']
 for sensitivity in [False,True]:
  rs,excluded=binary_rows([r for r in traces if not r['stratum'].endswith('/dev_certainty')],sensitivity)
  out['secondary']['partial_as_lost' if sensitivity else 'binary_primary']={'human_kappa':interval(rs,weighted_kappa,draws),'matcher_accuracy':interval(rs,weighted_accuracy,draws),'excluded_counts':excluded,'eligible_traces':len(rs)}
 for bench,model in [(b,m) for b in ['MQ','SB'] for m in [None]+sorted({r.get('model','unspecified') for r in traces if r['benchmark']==b})]:
  rs=[r for r in traces if r['benchmark']==bench and (model is None or r.get('model','unspecified')==model)]
  # Denominator ALL traces, matching the original CR8J headline, not only wrong traces.
  def rate(data):return sum(r['weight']*(not r['correct'] and r['adjudicated']=='reached_but_unused') for r in data)/sum(r['weight'] for r in data) if data else None
  def unresolved_upper(data):return sum(r['weight']*(not r['correct'] and r['adjudicated'] in ['reached_but_unused','uncertain']) for r in data)/sum(r['weight'] for r in data) if data else None
  out['secondary'][bench+'_candidate_aggregation_failure_rate_human'+('' if model is None else '/'+model)]={'estimate_ci':interval(rs,rate,draws),'uncertain_upper_sensitivity':interval(rs,unresolved_upper,draws),'denominator':'all human-labelled traces, including correct; must include dev certainty units for full-frame claim','unresolved':sum(r['adjudicated']=='uncertain' for r in rs)}
 out['binary_sensitivity_comparison']={}
 for metric in ['human_kappa','matcher_accuracy']:
  primary=out['secondary']['binary_primary'][metric]['estimate'];sensitivity=out['secondary']['partial_as_lost'][metric]['estimate']
  out['binary_sensitivity_comparison'][metric]={'primary':primary,'partial_as_lost':sensitivity,'difference':sensitivity-primary if primary is not None and sensitivity is not None else None,'interpretation':'Report any changed substantive interpretation in plain words; no threshold verdict.'}
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--labels',required=True);p.add_argument('--design',default='rebuttal/pilots/20261108_review4/e1_n80_design.json');p.add_argument('--size',type=int,choices=[60,80,100],default=80);p.add_argument('--output',required=True);a=p.parse_args()
 d=json.loads(Path(a.design).read_text());data=json.loads(Path(a.labels).read_text())
 if data.get('label_source')!='human_adjudicated':raise ValueError('Human labels required; pilot_provisional forbidden')
 selected={i:(h,s['weight']) for h,s in d['designs'][str(a.size)]['strata'].items() for i in s['ids']};dev={r['instance_id']:r['benchmark'] for r in d['rows'] if r['is_dev']}
 for group in ['facts','traces']:
  for r in data[group]:
   if r['instance_id'] in selected:r['stratum'],r['weight']=selected[r['instance_id']]
   elif group=='traces' and r['instance_id'] in dev:r['stratum'],r['weight']=dev[r['instance_id']]+'/dev_certainty',1
   else:raise ValueError('Label ID outside specified design')
 if set(r['instance_id'] for r in data['traces'])!=set(selected)|set(dev):raise ValueError('Full-frame rate requires all selected and dev certainty instances')
 out=analyze(data['facts'],data['traces']);path=Path(a.output).resolve()
 if Path('rebuttal/pilots').resolve() not in path.parents:raise ValueError('Pilot analysis output path required')
 path.write_text(json.dumps(out,indent=2)+'\n')



def weighted_ac1(rows, categories=('absent','faithful','partial','distorted')):
    """Nominal Gwet AC1, fixed categories, weighted mean of two human marginals."""
    if not rows:return None
    q=len(categories)
    if q<2:raise ValueError('At least two fixed categories required')
    total=sum(r['weight'] for r in rows);counts=Counter();agree=0
    for r in rows:
        a,b=r['human_a'],r['human_b'];w=r['weight']
        if a not in categories or b not in categories:raise ValueError('Unknown AC1 category')
        counts[a]+=w/2;counts[b]+=w/2;agree+=w*(a==b)
    pe=sum((counts[c]/total)*(1-counts[c]/total) for c in categories)/(q-1)
    return (agree/total-pe)/(1-pe)

if __name__=='__main__':main()
