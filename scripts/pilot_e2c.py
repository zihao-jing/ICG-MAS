"""Five reserved technical traces, all three released baselines × both backbones."""
import argparse,json
from pathlib import Path
from src.audit.pilot_common import CallLedger,freeze,digest
from src.audit.official_adapters import run_baselines
from scripts.pilot_e4p import validate_action_manifest

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',default='rebuttal/pilots/configs/E2-C-technical.json');p.add_argument('--execute',action='store_true');p.add_argument('--max-calls',type=int);a=p.parse_args()
 c=json.loads(Path(a.config).read_text());rows=validate_action_manifest(c)
 if c.get('label_status')!='pilot_provisional':raise ValueError('Technical-only runner')
 print(json.dumps({'items':len(rows),'calls':len(rows)*6,'paid':a.execute}),flush=True)
 if not a.execute:return
 ledger=CallLedger(c['output'],c,c['prereg'],a.max_calls)
 try:
  for row in rows:
   result=run_baselines(ledger,row['trace_id'],row,c['backbones'])
   freeze(Path(c['output'])/'raw'/(row['trace_id']+'.json'),{'instance_id':row['instance_id'],'label_status':'pilot_provisional','outputs':result})
   print(json.dumps({'completed_item':row['instance_id']}),flush=True)
 finally:ledger.close()
if __name__=='__main__':main()
