"""Separate approved planning ledger from tiny-pilot operational projection."""
import json
from pathlib import Path
P=Path('rebuttal/pilots');r=json.loads((P/'20261108_preflight/technical_progress.json').read_text());cost=json.loads((P/'20261108_preflight/costs.json').read_text())
rows={}
for label,key,n in [('E1','e1_v2',912),('E4','e4_technical',426),('E4-P','e4_p_technical',426),('E2-C','e2_c_technical',12),('E2-A','e2_a_technical',200)]:
 v=r[key];den=30 if label=='E1' else 5
 rows[label]={k:v[src]/den*n for k,src in [('calls','responses'),('usd','usd'),('api_seconds','seconds')]}
# 152 missing prerequisite aggregation calls have no like-for-like measured sample; keep planning component explicit.
prereq=sum(c*t*rate/1e6 for c,t,rate in cost['experiments']['E1']['components'][1:]);rows['E1']['calls']+=152;rows['E1']['usd']+=prereq;rows['E1']['prerequisite_usd_estimated']=prereq
extra=r['e4_p_seed43'];rows['E4-P']['calls']+=extra['responses']*78;rows['E4-P']['usd']+=extra['usd']*78;rows['E4-P']['api_seconds']+=extra['seconds']*78
proxy=r['e2_a_proxy'];rows['E2-A']['proxy_separate']={k:proxy[src]/5*200 for k,src in [('calls','responses'),('usd','usd'),('api_seconds','seconds')]}
total={k:sum(v[k] for v in rows.values()) for k in ['calls','usd','api_seconds']};withproxy={k:total[k]+rows['E2-A']['proxy_separate'][k] for k in total}
(P/'20261108_review3/cost_projection.json').write_text(json.dumps({'planned':cost['batch1'],'projection':rows,'total_excluding_proxy':total,'total_with_proxy':withproxy,'assumptions':'200 E2-A injection candidates, not 200 kept. Measured technical path runs baselines even on unkept cases; workload projection is not expected scientific sample. Extra seed one-item projection is fragile. E1 prerequisites remain planning estimate. Unapproved E1 enlargement and donor v2 changes excluded.'},indent=2)+'\n')
print(cost['batch1'],total,withproxy)
