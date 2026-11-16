"""Released W&W all-at-once on184 release traces, GPT-4o-mini only, sanity reproduction."""
import argparse,json,re
from pathlib import Path
from src.audit.pilot_common import CallLedger,digest,freeze
from src.audit.official_adapters import ww

def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--max-calls',type=int);a=p.parse_args()
 c=json.loads(Path('rebuttal/pilots/configs/WW-sanity.json').read_text());paths=sorted(Path(c['data']).glob('*/*.json'))
 assert len(paths)==184
 print(json.dumps({'reference_traces':len(paths),'calls':2*len(paths),'paid':a.execute}),flush=True)
 if not a.execute:return
 ledger=CallLedger(c['output'],c,c['prereg'],a.max_calls)
 try:
  for f in paths:
   row=json.loads(f.read_text());hand=f.parent.name=='Hand-Crafted'
   for gold in [True,False]:
    key=f'{f.parent.name}/{f.name}/gold-{gold}'
    result=ww(ledger,key,c['model'],row['history'],row.get('question',''),row.get('ground_truth','') if gold else None,temperature=None,is_handcrafted=hand)
    freeze(Path(c['output'])/'raw'/(digest(key)+'.json'),{'id':str(f),'gold':gold,'system_type':f.parent.name,'reference_agent':row.get('mistake_agent'),
        'reference_step':row.get('mistake_step'),**result})
   print(json.dumps({'completed_trace':str(f)}),flush=True)
 finally:ledger.close()
if __name__=='__main__':main()
