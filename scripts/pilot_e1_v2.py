"""Re-pilot dev matcher on the identical reserved traces; no final evaluation calls."""
import argparse,json
from pathlib import Path
from collections import defaultdict
from src.audit.pilot_common import CallLedger,digest,freeze
from src.audit.matcher_v2 import match_trace,PROMPT_SHA256

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',default='rebuttal/pilots/configs/E1-v2.json');p.add_argument('--execute',action='store_true');p.add_argument('--max-calls',type=int);a=p.parse_args()
    c=json.loads(Path(a.config).read_text());files=sorted(Path(c['source_traces']).glob('*.json'));traces=[json.loads(f.read_text()) for f in files]
    assert len(traces)==30 and {t['instance_id'] for t in traces}==set(c['pilot_ids'])
    assert PROMPT_SHA256==c['prompt_sha256']
    print(json.dumps({'items':5,'traces':30,'logical_calls':60,'max_attempts':180,'paid':a.execute}),flush=True)
    if not a.execute:return
    ledger=CallLedger(c['output'],c,c['prereg'],a.max_calls)
    try:
        for t in traces:
            key=digest([t['instance_id'],t['model'],t['k']]);result=match_trace(ledger,key,t,c['judge_model'])
            freeze(Path(c['output'])/'matcher'/f'{key}.json',{'instance_id':t['instance_id'],'base_model':t['model'],'k':t['k'],**result})
            print(json.dumps({'trace':key,'status':result['status']}),flush=True)
    finally:ledger.close()
if __name__=='__main__':main()
