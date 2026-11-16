"""Regenerate iclr2027_rebuttal/drafts/STATUS.md for the authors. Sources: counts-only logs, UNSEALED ledgers' count and cost fields, the summaries the runs write, and the intake check.
It never reads anything inside E1_judge_sealed/ or any other sealed folder: every read goes through _read(), which refuses a path containing "sealed".
Usage: python -m scripts.make_status"""
import datetime,json,re
from pathlib import Path
from scripts.intake_check import intake
B=Path('rebuttal/results/batch1');OUT=Path('iclr2027_rebuttal/drafts/STATUS.md')
def _read(path):
    if 'sealed' in str(path).lower():raise ValueError(f'status generator must never read a sealed path: {path}')
    return Path(path).read_text()
def _iso(s):return datetime.datetime.strptime(s,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
def _rate_eta(times,done,total,finished,now):
    if len(times)<2 or finished:return None,('finished' if finished else 'n/a')
    span=(max(times)-min(times)).total_seconds()
    if span<=0:return None,'n/a'
    rate=(len(times)-1)/span*60
    if done>=total:return rate,'finished'
    return rate,(now+datetime.timedelta(minutes=(total-done)/rate)).strftime('%Y-%m-%d %H:%MZ')
def ledger_job(name,d,total,now,summary=None):
    p=Path(d)/'calls.jsonl'
    if not p.exists():return {'name':name,'state':'not started','done':0,'total':total,'ok':0,'failed':0,'cost':0.0,'rate':None,'eta':'n/a'}
    res=[r for r in map(json.loads,_read(p).splitlines()) if r['event']=='result']
    times=[datetime.datetime.fromtimestamp(r['time'],datetime.timezone.utc) for r in res]
    fin=(Path(d)/'summary.json').exists() if summary is None else Path(summary).exists()
    cost=round(sum(r.get('cost_usd') or 0 for r in res),4);rate,eta=_rate_eta(times,len(res),total,fin,now)
    j={'name':name,'state':'finished' if fin else 'running','done':len(res),'total':total,'ok':sum(r['success'] for r in res),'failed':sum(not r['success'] for r in res),'cost':cost,'rate':rate,'eta':eta,'upper_bound':True}
    s=Path(d)/'summary.json'
    if fin and s.exists():
        own=json.loads(_read(s)).get('cost_usd');j['own_cost']=own
        if own and abs(cost-own)/own>0.01:j['cost_flag']=f'COST MISMATCH: status {cost} vs run summary {own}'
    return j
def counts_log_job(name,log,summary,total,now):
    lines=_read(log).splitlines() if Path(log).exists() else []
    ok=bad=fail=n=0;times=[]
    for l in lines:
        m=re.match(r'^(\d+)/(\d+) (valid|format_invalid|failed)(?: (\S+))?$',l.strip())
        if m:
            n=int(m.group(1));ok+=m.group(3)=='valid';bad+=m.group(3)=='format_invalid';fail+=m.group(3)=='failed'
            if m.group(4):times.append(_iso(m.group(4)))
    fin=Path(summary).exists();cost=json.loads(_read(summary))['cost_usd'] if fin else None
    rate,eta=_rate_eta(times,n,total,fin,now)
    return {'name':name,'state':'finished' if fin else ('running' if n else 'not started'),'done':n,'total':total,'ok':ok,'failed':fail+bad,'cost':cost if cost is not None else 'pending end of run','rate':rate,'eta':eta}
def counts_jsonl_job(name,path,summary,total,now):
    p=Path(path)
    if not p.exists():return {'name':name,'state':'not started','done':0,'total':total,'ok':0,'failed':0,'cost':'pending end of run','rate':None,'eta':'n/a'}
    rows=[json.loads(l) for l in _read(p).splitlines() if l.strip()];calls=[r for r in rows if r.get('event','call')=='call']
    times=[_iso(r['time_utc']) for r in rows if r.get('time_utc')];last=calls[-1] if calls else None
    fin=Path(summary).exists();run=last['running'] if last else {}
    j={'name':name,'state':'finished' if fin else ('running' if calls else 'starting'),'done':last['n'] if last else 0,'total':total,'ok':run.get('valid',0),'failed':run.get('failed_calls',0)+run.get('format_invalid',0),'cost':run.get('cost_usd',0.0)}
    j['rate'],j['eta']=_rate_eta(times,j['done'],total,fin,now)
    if fin:
        own=json.loads(_read(summary)).get('cost_usd');j['own_cost']=own
        if own and abs(j['cost']-own)/own>0.01:j['cost_flag']=f'COST MISMATCH: status {j["cost"]} vs run summary {own}'
    return j
def jobs(now,root=B):
    r=Path(root);E=r/'E4P_seed43';miss={'qwen':8,'gemma':4}
    out=[counts_log_job('E1 judge, first run (240 calls)',r/'E1_judge_run.log',r/'E1_judge_run_summary.json',240,now),
         counts_jsonl_job('E1 judge, retry of the 48 failed calls',r/'E1_judge_retry_counts.jsonl',r/'E1_judge_retry_summary.json',48,now)]
    for m in ('gpt','qwen','gemma'):out.append(ledger_job(f'E4-P seed-43 source traces, first run, {m}',E/m,1066,now,summary=E/m/'run.log'))
    for m,k in miss.items():out.append(ledger_job(f'E4-P source traces, retry of {k} missing, {m}',E/m/'retry',k*41,now))
    return out
def fmt_cost(c):return c if isinstance(c,str) else f'${c:.2f}'
def build(now=None,root=B,out=OUT,returned=None):
    now=now or datetime.datetime.now(datetime.timezone.utc);J=jobs(now,root);intk=intake() if returned is None else intake(returned)
    L=['# Status (regenerated automatically)','',f'**Last updated:** {now.strftime("%Y-%m-%d %H:%M UTC")}. Generated by `scripts/make_status.py` from counts-only logs, unsealed ledgers\' count and cost fields, the runs\' own summaries and the intake check. It never reads a sealed folder.','','## Jobs','','| Job | State | Calls done / total | % | OK / failed | Cost so far | Calls per min | Estimated finish (UTC) |','|---|---|---|---:|---|---|---:|---|']
    for j in J:
        pct=f"{100*j['done']/j['total']:.0f}%" if j['total'] else ''
        tot=f"{j['total']}{' (upper bound)' if j.get('upper_bound') else ''}"
        L.append(f"| {j['name']} | {j['state']} | {j['done']} / {tot} | {pct} | {j['ok']} / {j['failed']} | {fmt_cost(j['cost'])} | {('%.1f'%j['rate']) if j['rate'] else 'n/a'} | {j['eta']} |")
    flags=[j['cost_flag'] for j in J if j.get('cost_flag')]
    L+=['','**Cost cross-check at the end of each job:** '+('; '.join(flags) if flags else 'no mismatch above 1% so far (compared when a job finishes and writes its own summary).'),'','## Author tasks (files received / expected, complete rows / expected rows)','','| Author | Calibration | E1 dev | E1 anchor | E2 spot-checks (wave 1) |','|---|---|---|---|---|']
    names=['T0_calibration_E1','T1_E1_dev','T2_E1_anchor','T3_E2_spotcheck_wave1']
    for a in 'ABCD':
        cells=[]
        for t in names:
            c=intk['authors'][a][t];cells.append(f"{'received' if c['received'] is True else ('unreadable' if c['received'] else 'not received')}; {c['complete']} / {c['expected']}")
        L.append(f'| {a} | '+' | '.join(cells)+' |')
    L+=['',f"Files received: {intk['files_received']} of {intk['files_expected']}.",'']
    running=[j['name'] for j in J if j['state']=='running']
    L+=['## Next gate','','The lead annotator\'s dry run of the labelling folder, then the fixes it needs, then the lead\'s gate review. Every run that depends on labels stays held until then.'+(f' Running now: {", ".join(running)}.' if running else ' No job is running now.'),'']
    Path(out).write_text('\n'.join(L)+'\n');return J,intk
if __name__=='__main__':build()
