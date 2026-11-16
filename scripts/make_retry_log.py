"""Write rebuttal/results/batch1/retry_log.csv: one row per retried call or trace (job, id, original attempt time, original failure, retry time, retry result).
Reads counts-only logs, UNSEALED ledgers, and the lock manifest. For E1 the original error text sits in the sealed ledger and is never read: the column says so."""
import csv,datetime,json,re
from pathlib import Path
from src.audit.pilot_common import digest
from scripts.make_status import _read
B=Path('rebuttal/results/batch1');OUT=B/'retry_log.csv'
E1_FAIL='failed (error text sealed; outage inferred from timing)';MODELS=('qwen235b','gpt4omini','gemma31b')
def utc_of(epoch):return datetime.datetime.fromtimestamp(epoch,datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def log_lines(path,pattern):
    return [m for l in _read(path).splitlines() for m in [re.match(pattern,l.strip())] if m]
def e1_rows(root=B,ids=None,first_log=None,retry_log=None):
    from scripts.run_e1_judge import heldout_ids
    ids=ids or heldout_ids();items=sorted([(i,m) for i in ids for m in MODELS],key=lambda im:(digest(['E1-judge',42,im[0],im[1]]),im[0]))
    first=log_lines(first_log or root/'E1_judge_run.log',r'^(\d+)/240 (valid|format_invalid|failed)(?: \S+)?$')
    pos=[int(m.group(1)) for m in first if m.group(2)=='failed']
    retry=log_lines(retry_log or root/'E1_judge_retry.log',r'^(\d+)/(\d+) (valid|format_invalid|failed)(?: (\S+))?$')
    assert len(pos)==len(retry),(len(pos),len(retry))
    return [{'job':'E1 judge','id':f'{items[p-1][0]}|{items[p-1][1]}','original_attempt_time_utc':'not recorded','original_failure':E1_FAIL,'retry_time_utc':r.group(4) or 'not recorded','retry_result':r.group(3)} for p,r in zip(pos,retry)]
def e4p_rows(root=B):
    E=Path(root)/'E4P_seed43';ids=sorted(f.name.replace('.json','') for f in (E/'data').glob('*.json'));rows=[]
    for m in ('qwen','gemma'):
        d=E/m;first=log_lines(d/'run.log',r'^(\d+)/26 (ok|FAILED)(?: (\S+))?(?: (\S+))?$')
        failed_pos=[int(x.group(1)) for x in first if x.group(2)=='FAILED']
        led=[r for r in map(json.loads,_read(d/'calls.jsonl').splitlines()) if r['event']=='result' and not r['success']]
        retry=log_lines(d/'retry'/'run.log',r'^(\d+)/(\d+) (ok|FAILED)(?: (\S+))?(?: (\S+))?$')
        assert len(failed_pos)==len(led)==len(retry),(m,len(failed_pos),len(led),len(retry))
        for p,l,r in zip(failed_pos,led,retry):
            when=r.group(5) or r.group(4) or 'not recorded'
            rows.append({'job':f'E4-P seed-43 sources, {m}','id':f'{ids[p-1]}::seed43|{m}','original_attempt_time_utc':utc_of(l['time']),'original_failure':(l.get('error') or 'unknown')[:80],'retry_time_utc':when,'retry_result':'ok' if r.group(3)=='ok' else 'failed'})
    return rows
def main():
    rows=e1_rows()+e4p_rows()
    with OUT.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['job','id','original_attempt_time_utc','original_failure','retry_time_utc','retry_result']);w.writeheader();w.writerows(rows)
    print(json.dumps({'rows':len(rows),'e1':sum(r['job']=='E1 judge' for r in rows),'e4p':sum(r['job'].startswith('E4-P') for r in rows),'retry_failed':sum(r['retry_result'] not in ('valid','ok') for r in rows)}))
if __name__=='__main__':main()
