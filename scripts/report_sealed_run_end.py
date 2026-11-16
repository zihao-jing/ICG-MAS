"""End-of-run report for the sealed E1 judge run, from the counts-only summary the run itself writes. Opens no ledger and no sealed file."""
import json,sys
from pathlib import Path
S0=Path('rebuttal/results/batch1/E1_judge_run_summary.json')
def main(path=None):
    S=Path(path) if path else S0
    if not S.exists():print(json.dumps({'status':'run not finished','cost_usd':'pending end of run'}));return
    s=json.loads(S.read_text())
    print(json.dumps({'calls':s['calls'],'valid':s['valid'],'format_invalid':s['format_invalid'],'failed_calls':s['failed_calls'],'refusals':s['refusals'],
        'prompt_tokens':s['prompt_tokens'],'completion_tokens':s['completion_tokens'],'cost_usd':s['cost_usd'],'sealed_manifest_sha256':s['sealed_manifest_sha256'],'sealed_files':s['sealed_files'],
        'sealed_ledger_file_opened_by_worker':'once in total, during the FIRST run (the breach logged in DEVIATIONS.md; only count, failure and cost fields were used); not opened for the retry, whose ledger is metadata-only and outside the sealed folder','end_utc':s.get('end_utc')},indent=1))
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else None)
