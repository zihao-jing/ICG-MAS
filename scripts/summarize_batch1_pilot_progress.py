"""Operational totals and predetermined examples only; no failure-group summaries."""
import json,time
from pathlib import Path
from collections import defaultdict
from src.audit.pilot_common import digest

ROOT=Path('rebuttal/pilots')
def main():
    reports={}
    for name in ('20261108_e1','20261108_e1_calibration'):
        p=ROOT/name;rows=[json.loads(x) for x in (p/'calls.jsonl').read_text().splitlines()] if (p/'calls.jsonl').exists() else []
        calls=[r for r in rows if r['event']=='result'];started=[r for r in rows if r['event']=='intent']
        by_item=defaultdict(list)
        for r in calls:by_item[r['key'].split('/')[0]].append(r)
        completed=[]
        for line in (p/'run.log').read_text().splitlines():
            try:r=json.loads(line)
            except ValueError:continue
            if 'completed_instance' in r:completed.append(r['completed_instance'])
        completed=sorted(set(completed));complete_calls=[r for i in completed for r in by_item[i]]
        summary={'captured_at_unix':time.time(),'dispatched':len(started),'responses':len(calls),'pending':len(started)-len(calls),
            'api_failures':sum(not r['success'] for r in calls),'cost_usd':sum(r.get('cost_usd') or 0 for r in calls),
            'unknown_costs':sum(r.get('cost_usd') is None for r in calls),'summed_call_seconds':sum(r['seconds'] for r in calls),
            'completed_items':len(completed),'completed_item_ids':completed,'completed_traces':len(list((p/'traces').glob('*.json'))),
            'valid_matcher_packages':len(list((p/'matcher').glob('*.json'))),'schema_failures':len(list((p/'parse_issues').glob('*.json'))),
            'process':json.loads((p/'process.json').read_text()),'cost_note':'provider usage.cost when present; otherwise token-price estimate'}
        if completed:
            summary['per_completed_item']={'calls':len(complete_calls)/len(completed),'usd':sum(r.get('cost_usd') or 0 for r in complete_calls)/len(completed),
                'summed_call_seconds':sum(r['seconds'] for r in complete_calls)/len(completed)}
        # First three by immutable filename hash, never chosen for diagnosis/outcome.
        examples=[]
        for f in sorted((p/'traces').glob('*.json'))[:3]:
            t=json.loads(f.read_text());examples.append({'path':str(f),'instance_id':t['instance_id'],'model':t['model'],'k':t['k'],'answer_text':t['answer_text']})
        summary['raw_examples']=examples
        (p/'progress.json').write_text(json.dumps(summary,indent=2)+'\n');reports[name]=summary
    (ROOT/'20261108_preflight/progress.json').write_text(json.dumps(reports,indent=2)+'\n')
    for k,r in reports.items():print(k,json.dumps({x:r[x] for x in ['dispatched','responses','cost_usd','completed_items','schema_failures']}))
if __name__=='__main__':main()
