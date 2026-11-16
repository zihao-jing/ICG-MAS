"""Blind rendering of one trace for a judge. Frozen: its source hash is recorded in the named judge prompt versions."""
import json
from src.audit.pilot_common import blind_view,render_trace
def trace_text(t):
    b=blind_view(t);r=render_trace(b);body=r if isinstance(r,str) else json.dumps(r,ensure_ascii=False,indent=1)
    return 'Question: '+b['question']+'\nGold answer: '+str(b['gold_answer'])+'\nSource shards:\n'+'\n'.join(f"[agent-{c['agent_id']}] {c['text']}" for c in b['source_contexts'])+'\nGold supports:\n'+'\n'.join(f"[agent-{c['agent_id']}] {c['text']}" for c in b['source_supports'])+'\nSteps:\n'+body
