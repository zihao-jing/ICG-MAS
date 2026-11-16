"""Read only pre-outcome manifests: no repair/control results loaded."""
import json
from pathlib import Path
from src.audit.pilot_common import digest,freeze
from src.audit.base_tokenizers import count_added_tokens
from src.audit.e4_balance import balance
P=Path('rebuttal/pilots');O=P/'20261108_review5'
def main():
 O.mkdir(exist_ok=True)
 actions=json.loads((P/'20261108_technical_inputs/actions.json').read_text())
 rows=[]
 for a in actions:
  for arm in ['V-ext','V-sel','V-dist']:
   m=json.loads((P/'20261108_e4_donor_v2/manifests'/(digest([a['trace_id'],arm])+'.json')).read_text())
   raw='\n'.join([a['question']]+[u['text'] for u in a['pool_units']]+[u['text'] for u in a['board_units']])
   rows.append({'instance_id':a['instance_id'],'trace_id':a['trace_id'],'failure_type':a['diagnosis']['group'] if isinstance(a['diagnosis'],dict) else a['diagnosis'],'benchmark':'MuSiQue','protocol':'MQ','base_model':a['model'],'repair_arm':arm.replace('V-','R-'),'trace_tokens':count_added_tokens(a['model'],raw),**{k:m['match'][k] for k in ['repair_tokens','control_tokens','matched']}})
 freeze(O/'e4_balance.json',{'prereg_sha256':digest((P/'prereg/E4-v2.md').read_bytes()),'rows':rows,'balance':balance(rows),'outcomes_read':False})
if __name__=='__main__':main()
