"""Outcome-free balance statistics for matched-volume pairs."""
import math,statistics

def standardized_difference(a,b,categorical=False):
 if not a or not b:return None
 ma,mb=statistics.mean(a),statistics.mean(b)
 if categorical:var=(ma*(1-ma)+mb*(1-mb))/2
 else:
  if min(len(a),len(b))<2:return None
  var=(statistics.variance(a)+statistics.variance(b))/2
 return (ma-mb)/math.sqrt(var) if var>0 else (0.0 if ma==mb else None)

def balance(rows):
 out=[]
 for key in ['failure_type','benchmark','protocol','base_model','trace_tokens','repair_tokens','control_tokens']:
  categorical=key in ['failure_type','benchmark','protocol','base_model']
  fixed={'failure_type':['extraction_omission','selection_omission','strict_distortion','candidate_aggregation','partial','correct_control'],'benchmark':['MuSiQue','Silo-Bench'],'protocol':['SB-5','SB-10','MQ']}
  for level in sorted(set(fixed.get(key,[]))|{r[key] for r in rows}) if categorical else [None]:
   a=[int(r[key]==level) if categorical else r[key] for r in rows if r['matched']]
   b=[int(r[key]==level) if categorical else r[key] for r in rows if not r['matched']]
   out.append({'variable':key,'level':level,'matched_n':len(a),'unmatched_n':len(b),'matched_count':sum(a) if categorical else len(a),'unmatched_count':sum(b) if categorical else len(b),'matched_median':statistics.median(a) if a else None,'unmatched_median':statistics.median(b) if b else None,'smd':standardized_difference(a,b,categorical)})
 return out

def equal_volume_contrast(rows):
 """Prespecified all-case OLS standardization; call separately per benchmark."""
 import numpy as np
 if len({r['benchmark'] for r in rows})!=1:raise ValueError('Fit each benchmark separately')
 factors=['failure_type','protocol','base_model','repair_arm']
 levels={k:sorted({r[k] for r in rows})[1:] for k in factors}
 def design(equal=False):
  return np.array([[1]+[float(r[k]==v) for k in factors for v in levels[k]]+[math.log1p(r['repair_tokens']),math.log1p(r['repair_tokens'] if equal else r['control_tokens'])] for r in rows])
 x=design();y=np.array([r['repair_score']-r['control_score'] for r in rows]);coef,_,rank,_=np.linalg.lstsq(x,y,rcond=None)
 if rank<x.shape[1] or len(rows)<=rank:return None
 predictions=design(True)@coef
 return {'overall':float(predictions.mean()),'by_group':{g:float(np.mean([p for r,p in zip(rows,predictions) if r['failure_type']==g])) for g in sorted({r['failure_type'] for r in rows})}}

def volume_sensitivity(rows,draws=2000,seed=42):
 import random
 from collections import defaultdict
 groups=defaultdict(list)
 for r in rows:groups[r['instance_id']].append(r)
 if len(groups)<10:return {'status':'descriptive_only','clusters':len(groups),'estimate':None}
 estimate=equal_volume_contrast(rows)
 if estimate is None:return {'status':'non_estimable','clusters':len(groups),'estimate':None}
 rng=random.Random(seed);keys=sorted(groups);samples=[]
 for _ in range(draws):
  fit=equal_volume_contrast([r for k in rng.choices(keys,k=len(keys)) for r in groups[k]])
  if fit is not None:samples.append(fit)
 def interval(values):
  values=sorted(values);return [values[int(.025*(len(values)-1))],values[int(.975*(len(values)-1))]] if len(values)>=.95*draws else None
 return {'status':'estimated','clusters':len(groups),'estimate':estimate,'valid_draws':len(samples),'draws':draws,'ci':interval([s['overall'] for s in samples]),'group_ci':{g:interval([s['by_group'][g] for s in samples if g in s['by_group']]) for g in estimate['by_group']}}

def matched_volume_contrast(rows,draws=2000,seed=42):
 """Repair minus control on matched pairs only; never filter the main repair comparison."""
 from src.audit.pilot_common import cluster_bootstrap
 if len({r['benchmark'] for r in rows})!=1:raise ValueError('Fit each benchmark separately')
 included=[r for r in rows if r['matched']]
 clusters=len({r['instance_id'] for r in included})
 statistic=lambda rs:sum(r['repair_score']-r['control_score'] for r in rs)/len(rs) if rs else None
 result={'pairs':len(included),'possible_pairs':len(rows),'clusters':clusters,'estimate':statistic(included),'status':'descriptive_only' if clusters<10 else 'estimated'}
 if clusters>=10:result['bootstrap']=cluster_bootstrap(included,statistic,draws=draws,seed=seed)
 return result
