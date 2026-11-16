"""Deterministic preregistration selections; requires labels, never infers them."""
import hashlib
from src.audit.pilot_common import ranked,digest

def select_casebook(rows,counts):
    groups={k:[] for k in counts}
    for r in rows:
        if r['correct'] or r['k']!=1 or r['split']!='held_out' or not r['adjudicated']:continue
        label=r['diagnosis'];dataset=r['dataset']
        key=('extraction' if label=='extraction_omission' else 'selection' if label=='selection_omission' else None) if dataset=='silobench' else None
        if label=='candidate_aggregation':key='aggregation_'+dataset
        if key in groups:groups[key].append(r['trace_id'])
    return {k:ranked(set(v))[:counts[k]] for k,v in groups.items()}

def placement_hash_agent(source_id,instance_id,n_agents):
    return int.from_bytes(hashlib.sha256(f'42:{source_id}:{instance_id}'.encode()).digest()[:8],'big')%n_agents

def choose_target_donor(trace,label):
    """Label row supplies eligible target IDs; no repair outcome is accepted."""
    board=trace['checkpoints']['board'];agents={u['agent_id'] for u in trace['source_contexts']}
    targets=set(label['eligible_target_agents'])
    if not targets or not targets<=agents:raise ValueError('No valid target candidates')
    order=lambda xs:sorted(xs,key=lambda a:(digest([42,trace['instance_id'],a]),a))
    t=order(targets)[0];board_agents={u['agent_id'] for u in board};other=board_agents-{t}
    if not other:raise ValueError('No other donor board agent')
    no_support=other-set(label['support_holder_agents']);d=order(no_support or other)[0]
    return {'target_agent':t,'donor_agent':d,'donor_fallback':not bool(no_support),
            'target_unit_ids':[u['unit_id'] for u in board if u['agent_id']==t],
            'donor_unit_ids':[u['unit_id'] for u in board if u['agent_id']==d],'board_sha256':digest(board)}

def e2a_eligible(row):
    required=('complete_pool','complete_board','any_partial_or_distorted','any_uncertain')
    if any(row.get(k) is None for k in required):return False
    return (len(set(row.get('annotators',[])))==2 and row.get('adjudicated') is True and
        row.get('clean_reruns_correct')==[True,True] and row['complete_pool'] is True and
        row['complete_board'] is True and row['any_partial_or_distorted'] is False and row['any_uncertain'] is False)

def injection_keep(kind,row):
    if len(set(row.get('annotators',[])))!=2 or row.get('only_one_critical_defect') is not True:return False
    if kind=='aggregation':return row.get('wrong_answer') is True and row.get('exactly_one_reasoning_step_changed') is True
    return row.get('wrong_reruns')==[True,True] and row.get('matcher_checked') is True
