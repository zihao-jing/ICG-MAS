"""Per-model report of the E4-P seed-43 source-trace jobs. Reads only their own run logs and ledgers (not sealed)."""
import json,re
from pathlib import Path
ROOT=Path('rebuttal/results/batch1/E4P_seed43')
def main():
    out={};tot={'traces_done':0,'traces_failed':0,'calls':0,'failed_calls':0,'cost_usd':0.0}
    for m in ('qwen','gpt','gemma'):
        d=ROOT/m;log=(d/'run.log').read_text().splitlines() if (d/'run.log').exists() else []
        ok=sum(bool(re.match(r'^\d+/\d+ ok$',l)) for l in log);bad=sum(bool(re.match(r'^\d+/\d+ FAILED',l)) for l in log)
        final=next((json.loads(l) for l in reversed(log) if l.startswith('{') and 'traces_done' in l),None)
        res=[r for r in map(json.loads,(d/'calls.jsonl').read_text().splitlines()) if r['event']=='result'] if (d/'calls.jsonl').exists() else []
        files=len(list((d/'traces').glob('*.json'))) if (d/'traces').exists() else 0
        rl=d/'retry'/'summary.json';retry=json.loads(rl.read_text()) if rl.exists() else None
        o={'traces_ok_in_log':ok,'traces_failed_in_log':bad,'trace_files':files,'of':26,'calls':len(res),'failed_calls':sum(not r['success'] for r in res),'cost_usd':round(sum(r.get('cost_usd') or 0 for r in res),4),'finished':final is not None,'retry_summary':retry}
        out[m]=o;tot['traces_done']+=ok;tot['traces_failed']+=bad;tot['calls']+=o['calls'];tot['failed_calls']+=o['failed_calls'];tot['cost_usd']+=o['cost_usd']
    tot['cost_usd']=round(tot['cost_usd'],4);out['total']=tot;print(json.dumps(out,indent=1))
if __name__=='__main__':main()
