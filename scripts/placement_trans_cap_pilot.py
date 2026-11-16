"""Pilot: re-run the 12 diagnosed NO EVIDENCE transmissions with a 2,000-token cap.

Question: were the 382-385-token outputs cut off at the old 400-token cap?
Same model, prompt, shard and temperature as the matched run; only max_tokens changes.
Cap: $1.00 total. Output: rebuttal/pilots/20261113_placement_redo/trans_cap2000_pilot.json
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import scripts.placement_redo as P
from scripts.run_expansion_stage2 import packages

OUT = P.OUT / 'trans_cap2000_pilot.json'
NEW_CAP_TOKENS = 2000
CAP_USD = 1.0

done = json.loads((P.OUT / 'results_matched.json').read_text())['cases']
targets = [r for r in done if r['arm'] == 'diagnosed'
           and r.get('transmission') == 'NO EVIDENCE']
cases = {c['key']: c for c in json.loads(P.CASES.read_text())}
pk = {m: packages(m) for m in P.MODELS}

total = 0.0
rows = []
for r in targets:
    c = cases[r['key']]
    t = pk[c['model']][c['instance_id']]
    ctx = {x['agent_id']: x['text'] for x in t['source_contexts']}
    user = f"QUESTION\n{c['question']}\n\nYOUR DATA SHARD\n{ctx[c['agent_id']][:4000]}"
    key = f"cap2000/{r['key']}/{r['agent']}"
    resp, total = P.call(f"trans/{key}", P.STRONG, P.TRANS_SYSTEM, user,
                         NEW_CAP_TOKENS, CAP_USD, total)
    if resp is None:
        break
    rows.append({'key': r['key'], 'agent': r['agent'],
                 'old_text': r['transmission'],
                 'new_text': (resp.content or '').strip(),
                 'finish_reason': (resp.metadata or {}).get('finish_reason'),
                 'usage': resp.usage})
    print(json.dumps({'key': r['key'], 'new_text': rows[-1]['new_text'][:80],
                      'finish': rows[-1]['finish_reason'],
                      'spent_usd': round(total, 6)}), flush=True)

OUT.write_text(json.dumps({'max_tokens': NEW_CAP_TOKENS, 'cap_usd': CAP_USD,
                           'spent_usd': round(total, 6), 'n': len(rows),
                           'rows': rows}, indent=1, ensure_ascii=False))
print(json.dumps({'n': len(rows), 'spent_usd': round(total, 6)}, indent=1))
