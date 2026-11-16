"""Released R1 prompt/taxonomy on its own examples; not numerical reproduction."""
import argparse,json
from pathlib import Path
from src.audit.pilot_common import CallLedger,freeze
from src.audit.official_adapters import r1_prompt,parse_r1

def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--max-calls',type=int);a=p.parse_args()
 c=json.loads(Path('rebuttal/pilots/configs/R1-structural.json').read_text());rows=json.loads(Path(c['examples']).read_text());print(json.dumps({'calls':len(rows),'paid':a.execute}),flush=True)
 if not a.execute:return
 ledger=CallLedger(c['output'],c,c['prereg'],a.max_calls)
 try:
  for row in rows:
   msgs,steps=r1_prompt(release=row);raw=ledger.call(row['id'],c['judge_model'],msgs,max_tokens=4096)
   parsed=parse_r1(raw,steps);freeze(Path(c['output'])/(row['id']+'.json'),{'id':row['id'],'raw':raw,'steps':steps,'parsed':parsed})
   print(json.dumps({'id':row['id'],**parsed}),flush=True)
 finally:ledger.close()
if __name__=='__main__':main()
