"""Offline single-fault edits. Human eligibility and postchecks remain mandatory."""
from copy import deepcopy
from src.protocols.relay import _topk_select

def inject_evidence(trace,kind,agent,carrier_ids,*,replacement_text=None):
    """Return an edited trace without altering the input or choosing outcomes.

    Caller must certify fact necessity across all support sets and unique target
    ownership. This function rejects obvious violations, but does not certify
    absence of other critical defects (that is a human post-injection task).
    """
    out=deepcopy(trace);cp=out['checkpoints'];pool=cp['extraction'];board=cp['board']
    if not carrier_ids or not set(carrier_ids)<={u['unit_id'] for u in pool}:raise ValueError('Unknown fact carrier')
    if any(u['agent_id']!=agent for u in pool if u['unit_id'] in carrier_ids):raise ValueError('Fact has carrier outside target')
    target_board=[u for u in board if u['agent_id']==agent]
    if len(target_board)!=1:raise ValueError('Expected one target board unit at k=1')
    if target_board[0]['unit_id'] not in carrier_ids:raise ValueError('Target board does not carry injected fact')
    agent_pool=[u for u in pool if u['agent_id']==agent]
    original_scores=trace['scores'][agent]
    if len(original_scores)!=len(agent_pool):raise ValueError('Pool/score alignment mismatch')
    remaining=[(u,s) for u,s in zip(agent_pool,original_scores) if u['unit_id'] not in carrier_ids]
    if kind=='extraction_omission':
        cp['extraction']=[u for u in pool if u['unit_id'] not in carrier_ids]
        out['scores'][agent]=[s for u,s in remaining]
    if kind in ('extraction_omission','selection_omission'):
        if not remaining:raise ValueError('No noncarrier replacement; candidate ineligible')
        texts=[u['text'] for u,s in remaining];scores=[s for u,s in remaining]
        selected=_topk_select(texts,scores,1)[0];replacement=next(u for u,s in remaining if u['text']==selected)
    elif kind=='distortion':
        if not replacement_text or replacement_text==target_board[0]['text']:raise ValueError('Distortion requires changed text')
        replacement=dict(target_board[0],unit_id=target_board[0]['unit_id']+':injected',text=replacement_text)
    else:raise ValueError('Unsupported evidence injection')
    cp['board']=[replacement if u['agent_id']==agent else u for u in board]
    cp['transmission']=deepcopy(cp['board'])
    # The old answer cannot be rendered as the edited trace's answer.
    out['answer_text']=''
    out['injection']={'type':kind,'agent':agent,'carrier_ids':list(carrier_ids)}
    return out

def provisional_single_defect(carriers, target_fact, kind):
    """Conservative technical check; never substitutes for author confirmation."""
    kind={'extraction_omission':'extraction','selection_omission':'selection'}.get(kind,kind)
    if not target_fact or kind not in {'extraction','selection','distortion'}:
        return False
    rows={r['fact_id']:r for r in carriers['facts']}
    if target_fact not in rows:return False
    def faithful(items):
        return bool(items) and all(c['fidelity']=='faithful' for c in items)
    for fid,r in rows.items():
        if fid!=target_fact and not all(faithful(r[cp]) for cp in ['extraction','board']):
            return False
    r=rows[target_fact]
    if kind=='extraction':return not r['extraction'] and not r['board']
    if kind=='selection':return faithful(r['extraction']) and not r['board']
    return faithful(r['extraction']) and bool(r['board']) and all(c['fidelity']=='distorted' for c in r['board'])
