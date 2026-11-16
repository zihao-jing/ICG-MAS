"""Regenerate iclr2027_rebuttal/drafts/STATUS.md for the authors. Sources: counts-only logs, UNSEALED ledgers' count and cost fields, the summaries the runs write, and the intake check.
It never reads anything inside E1_judge_sealed/ or any other sealed folder: every read goes through _read(), which refuses a path containing "sealed".
Usage: python -m scripts.make_status"""
import datetime,json,re
from pathlib import Path
from scripts.intake_check import intake
B=Path('rebuttal/results/batch1');OUT=Path('iclr2027_rebuttal/drafts/STATUS.md');CORRECTED=Path('rebuttal/annotation/returns_corrected_1')
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
def trace_files_job(name,d,total,now,extra=()):
    """Jobs that write one JSON record per trace (the matcher: two calls per trace).

    `extra` lists further run folders of the same frozen matcher (the one-attempt top-up); their
    records and cost are added to the first run's."""
    dirs=[Path(d)]+[Path(e) for e in extra]
    recs=sorted(p for dd in dirs for p in (dd/'matcher').glob('*.json'))
    fin=Path(d)/'summary.json'
    if not recs and not fin.exists():return {'name':name,'state':'not started','done':0,'total':total,'ok':0,'failed':0,'cost':0.0,'rate':None,'eta':'n/a','upper_bound':True}
    times=[datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc) for p in recs]
    ok=bad=0;cost=0.0
    for p in recs:
        r=json.loads(_read(p));ok+=r.get('status')=='ok';bad+=r.get('status')!='ok'
    for dd in dirs:
        if (dd/'calls.jsonl').exists():
            cost+=sum((r.get('cost_usd') or 0) for r in map(json.loads,_read(dd/'calls.jsonl').splitlines()) if r['event']=='result')
    cost=round(cost,4)
    rate,eta=_rate_eta(times,len(recs),total,fin.exists(),now)
    j={'name':name,'state':'finished' if fin.exists() else ('running' if recs else 'starting'),'done':len(recs),'total':total,'ok':ok,'failed':bad,'cost':cost,'rate':rate,'eta':eta,'upper_bound':True}
    if fin.exists():
        own=sum(json.loads(_read(Path(dd)/'summary.json')).get('cost_usd') or 0 for dd in dirs if (dd/'summary.json').exists());j['own_cost']=round(own,4)
        if own and abs(cost-own)/own>0.01:j['cost_flag']=f'COST MISMATCH: status {cost} vs run summary {own:.4f}'
    return j
def jobs(now,root=B):
    r=Path(root);E=r/'E4P_seed43';miss={'qwen':8,'gemma':4}
    out=[counts_log_job('E1 judge, first run (240 calls)',r/'E1_judge_run.log',r/'E1_judge_run_summary.json',240,now),
         counts_jsonl_job('E1 judge, retry of the 48 failed calls',r/'E1_judge_retry_counts.jsonl',r/'E1_judge_retry_summary.json',48,now)]
    for m in ('gpt','qwen','gemma'):out.append(ledger_job(f'E4-P seed-43 source traces, first run, {m}',E/m,1066,now,summary=E/m/'run.log'))
    for m,k in miss.items():out.append(ledger_job(f'E4-P source traces, retry of {k} missing, {m}',E/m/'retry',k*41,now))
    out.append(trace_files_job('E1 anchor matcher, frozen semantic-dev-v2 (90 traces)',r/'E1_matcher_anchor',90,now,extra=(r/'E1_matcher_anchor_topup',)))
    out.append(ledger_job('E2-A stage-1 judge, Gemini 3.6 Flash (12 items)',r/'E2_stage1_judge',12,now))
    out.append(trace_files_job('E4 pool matcher, frozen semantic-dev-v2 (240 traces)',r/'E4_pool_matcher',240,now))
    out.append(ledger_job('E2-A wave-1 screening, Gemini 3.6 Flash (68 bases)',r/'E2A_wave1_screening',68,now))
    out.append(ledger_job('Paper-evaluator full run, Qwen3-235B (852 judged rows)',r/'Paper_evaluators_full_v11',852,now))
    out.append(ledger_job('E4 action/donor manifest, V-ext donor extractions (40 calls)',r/'E4_manifest',40,now))
    out.append(ledger_job('E4 direct insertion (A3), 17 cases x 2 arms (34 calls)',r/'E4_direct_insertion',34,now))
    return out
def fmt_cost(c):return c if isinstance(c,str) else f'${c:.2f}'
def sample_line(root):
    p=Path(root)/'SAMPLE_CHECK.md';return _read(p).strip() if p.exists() else 'not run yet'
def build(now=None,root=B,out=OUT,returned=None,corrected=None):
    now=now or datetime.datetime.now(datetime.timezone.utc);J=jobs(now,root)
    intk=intake(returned or 'rebuttal/annotation/returns',override=corrected)
    L=['# Status (regenerated automatically)','',f'**Last updated:** {now.strftime("%Y-%m-%d %H:%M UTC")}. Generated by `scripts/make_status.py` from counts-only logs, unsealed ledgers\' count and cost fields, the runs\' own summaries and the intake check. It never reads a sealed folder.','','## Jobs','','| Job | State | Calls done / total | % | OK / failed | Cost so far | Calls per min | Estimated finish (UTC) |','|---|---|---|---:|---|---|---:|---|']
    for j in J:
        pct=f"{100*j['done']/j['total']:.0f}%" if j['total'] else ''
        tot=f"{j['total']}{' (upper bound)' if j.get('upper_bound') else ''}"
        L.append(f"| {j['name']} | {j['state']} | {j['done']} / {tot} | {pct} | {j['ok']} / {j['failed']} | {fmt_cost(j['cost'])} | {('%.1f'%j['rate']) if j['rate'] else 'n/a'} | {j['eta']} |")
    flags=[j['cost_flag'] for j in J if j.get('cost_flag')]
    L+=['','**Cost cross-check at the end of each job:** '+('; '.join(flags) if flags else 'no mismatch above 1% so far (compared when a job finishes and writes its own summary).'),'','## Author tasks (files accepted by the intake check / expected, complete rows / expected rows)','',"**Status of the files in use: these are the authors' labels; file SHA-256 are in `rebuttal/results/batch1/UNSEAL_AUTHORISATION.md`.**",'','| Author | Calibration | E1 dev | E1 anchor | E2 spot-checks (wave 1) |','|---|---|---|---|---|']
    names=['E1calibration','E1dev','E1anchor','E2spotcheck1']
    for a in 'ABCD':
        cells=[]
        for t in names:
            c=intk['authors'][a][t];cells.append(f"{'received' if c['received'] is True else ('unreadable' if c['received'] else ('wrong version tag' if c.get('other_version_files') else 'not received'))}; {c['complete']} / {c['expected']}")
        L.append(f'| {a} | '+' | '.join(cells)+' |')
    L+=['',f"Files received: {intk['files_received']} of {intk['files_expected']} (version tag {intk.get('version','?')}; returns are read from `rebuttal/annotation/returns/`). The folder is `labelling-v1.0`; the dry run was skipped and no `labelling-v1.1` exists.",'',
        '**Provenance signs, 2026-11-09.** The 8 E1 dev/anchor first exports reproduce byte-for-byte from `labelling_20261108/scripts/label_dev_and_anchor.py`; the 7 corrected files reproduce byte-for-byte from `scripts/regenerate_independent_authors.py`. `E1calibration_A` is reproduced by neither recovered script (its generator is not on disk); calibration B–D derive from it. The 4 E2 spot-check files are single-author on disjoint items, and neither recovered script reads `T3_E2_spotcheck_wave1.jsonl`. Paired-author identity on the first export (A = B, C = D on every shared item) is a script property, not an agreement result. Hashes and the search log: `rebuttal/annotation/provenance_evidence/`.','',
        '**Author decision (2026-11-09, final):** the authors\' returned files are used as they are; file SHA-256 are in `rebuttal/results/batch1/UNSEAL_AUTHORISATION.md`. This supersedes the earlier "pending author decision; working assumption: fresh hand labels" note and the sentence "No label set is cleared for analysis." in the corrected re-export note.','',
        '**Corrected re-export, 2026-11-09 17:19 (7 files):** the counts above use these in place of the same-named originals: E1anchor_B_labelling-v1.0.json, E1anchor_D_labelling-v1.0.json, E1calibration_B_labelling-v1.0.json, E1calibration_C_labelling-v1.0.json, E1calibration_D_labelling-v1.0.json, E1dev_B_labelling-v1.0.json, E1dev_D_labelling-v1.0.json. The replaced originals are **superseded, on record and unused**. They are **not** preserved in `rebuttal/annotation/returns/` (that directory now holds the corrected files), and `rebuttal/annotation/returns_corrected_1/` does not exist; the originals\' hashes are preserved in `intake_hash_log.csv`.','',
        '**Script recovery, 2026-11-09.** Both scripts were recovered and copied unchanged into `rebuttal/annotation/provenance_evidence/`: `label_dev_and_anchor.py` (SHA-256 `f79565a2ef7bccb196f385e575b2e0b10189c0e82f3d89c3aac96970bd7e4eaa`) and `regenerate_independent_authors.py` (`36cc5c47502bd792f7264267b51bd24c4065581df9263e8c2ccfa7f28a567aa6`). The originals\' directory (`labelling_20261108/scripts/`) is gone; byte-identical copies survive under `rebuttal/results/batch1/provenance_evidence/` and `/private/tmp/`. No copy was found in git objects, the trash, editor local history, shell history or backups. The scripts are evidence only and are not run again.','']
    L+=['**Final sample check (IDs against the pre-registered lists):** '+sample_line(root),'']
    running=[j['name'] for j in J if j['state']=='running']
    L+=['## Next gate','','The E1 judge outputs are unsealed under `rebuttal/results/batch1/UNSEAL_AUTHORISATION.md`. The E1 anchor analysis with the frozen matcher is in `rebuttal/results/batch1/E1/`: the matcher has run once plus a one-attempt top-up of 6 traces (84 of the 90 anchor traces scored; 6 failed and unscored at the 4,096-token cap, 0 never attempted, $0.16 total) and has finished its single pass on the 240 E4-pool traces (227 scored, 13 failed and unscored, $0.44). The E2-A stage-1 gate passed (12 of 12 `defect_free` agreement; `rebuttal/results/batch1/E2_stage1_judge/gate.md`); wave-1 screening finished on the 68 combined candidate bases (67 valid, 1 failed, $0.79) and no outcome was read. The E4 case list is **frozen** with its matcher labels and before any outcome: `E4_pool_matcher/E4_cohort_frozen.json`, SHA-256 `9d55d723…`; the action/donor manifest is now built and **frozen before any outcome**: `E4_manifest/manifest.json`, SHA-256 `20926a06…`, `frozen_utc` 2026-11-09T17:55:14Z, from 40 logged V-ext donor calls ($0.01, 0 failed); matched pairs are distortion 7 of 25 and selection 0 of 1; the extraction R-ext unit count was fixed by the Phase 1 run. E4 Phase 1 ran as frozen (89 rows, 125 runs, 201 calls, 0 failed, $0.074841; 3 of 18 volume pairs matched) and its pre-registered analysis is in `E4_phase1/analysis.md`; the targeted fact was on the post-swap board in 0 of 17 cases by both checks, so the re-extraction arm is marked **not effective as specified**. Amendment A3 then ran direct insertion on the same 17 cases: R-ins appends the targeted-fact text as one board unit (a **positive control**; its 17/17 manipulation check passes by construction), and V-ins a donor passage (34 calls, 0 failed, $0.008385; 17/17 manipulation checks and 17/17 volume matches pass; contrast computed in `E4_direct_insertion/contrast.md`, numbers sent to the lead). E4 Phase 1b (distortion) and Phase 2 (aggregation) have since run as frozen (DEVIATIONS 2026-11-11T16:30:00Z; contrasts in `E4_phase23/analysis.md` and `tables/T18`). **C10 decision (2026-11-11): E4-P option A — unexecutable under the frozen design.** The hashed action manifest and frozen matcher labels are absent, `manifest_sha256` is null, `matcher_frozen` and `allow_full_run` are false, and 0 of 78 seed-43 traces are labelled; nothing is built. A future E4-P needs a new pre-registration with its own action manifest (DEVIATIONS 2026-11-11T16:55:00Z). The paper-evaluator study amendment `Paper-evaluators-v1.1` (SHA-256 `06aef4be…`) is frozen: lexical rule on all 1,356 rows, judge on the 852 untied rows only; its Qwen-235B run is listed above.'+(f' Running now: {", ".join(running)}.' if running else ' No job is running now.'),'']
    Path(out).write_text('\n'.join(L)+'\n');return J,intk
if __name__=='__main__':build(corrected=CORRECTED if CORRECTED.exists() else None)
