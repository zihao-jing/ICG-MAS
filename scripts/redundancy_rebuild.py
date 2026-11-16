"""Redundancy rebuild: re-extract 30 MuSiQue traces at up to 5 units per agent (cap $0.20).

Then rerun the selection at k = 3 (now strictly smaller than the unit count) and the protection and
crowding-out tests on the paper's Red/UB definitions.
"""
import json, math
from pathlib import Path
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request
from src.protocols.relay import _EXTRACTION_SYSTEM, _SCORING_SYSTEM, _parse_units

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_redundancy'
CALLS = OUT / 'rebuild_calls.jsonl'
UNITS = OUT / 'rebuild_units.json'
MODEL = 'qwen/qwen3-235b-a22b-2507'
PRICE = (0.14 / 1e6, 0.8 / 1e6)
CAP = 0.20
TOK = 400
K = 5


def spent():
    if not CALLS.exists(): return 0.0
    return sum(json.loads(l).get('cost_usd', 0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def main():
    pop = json.loads(Path('rebuttal/pilots/20261115_proxy_support_mq/population.json').read_text())
    res = json.loads(Path('results/run_qwen235b_musique/results.json').read_text())
    wrong = {r['id'] for r in res['instance_results']['score_ranked_relay'] if not r['correct']}
    pool = [x for x in pop if x['model'] == 'qwen235b' and x['instance_id'] in wrong and x.get('has_extraction')][:30]
    OUT.mkdir(parents=True, exist_ok=True)
    out = {}
    total = spent()
    for t in pool:
        inst = t['instance_id']
        agents = {}
        for d in t['documents']:
            agents[d['unit_id']] = d['text']
        rec = {}
        for agent, shard in agents.items():
            user = (f'Question: {t["question"]}\nAgent {agent} private evidence:\n{shard}\n\n'
                    f'Extract at most {K} atomic evidence units.')
            est = math.ceil((len(_EXTRACTION_SYSTEM) + len(user)) / 4)
            if total + est * PRICE[0] + TOK * PRICE[1] > CAP:
                print(json.dumps({'stop': 'cap', 'spent': round(total, 6)})); UNITS.write_text(json.dumps(out, indent=1)); return
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'intent', 'key': f'{inst}/{agent}/extract'}) + '\n')
            r = single_request(APIRequest(system_query=_EXTRACTION_SYSTEM, user_query=user, model=MODEL,
                                          max_tokens=TOK, temperature=0))
            u = r.usage or {}
            cost = u.get('prompt_tokens', est) * PRICE[0] + u.get('completion_tokens', 0) * PRICE[1]
            total += cost
            rec[agent] = _parse_units(r.content or '', K)
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'result', 'key': f'{inst}/{agent}/extract', 'usage': u,
                                    'cost_usd': round(cost, 8), 'content': (r.content or '')[:800]}) + '\n')
        out[inst] = rec
        UNITS.write_text(json.dumps(out, indent=1))
        print(json.dumps({'instance': inst, 'agents': {a: len(v) for a, v in rec.items()}, 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6), 'n': len(out)}))


if __name__ == '__main__':
    main()