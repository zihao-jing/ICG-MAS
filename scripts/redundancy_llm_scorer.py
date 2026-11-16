"""Redundancy rerun with the paper's LLM relevance scorer on the rebuilt units (cap $0.20).

Rule `prereg/Redundancy-LLM-scorer.md`, hashed before any call.
"""
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

from scripts.redundancy_paperdef import load_supports, redundancy, useful_budget
from src.protocols.relay import _SCORING_SYSTEM, _redundancy_select
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
PILOTS = ROOT / 'rebuttal/pilots'
RULE = PILOTS / 'prereg/Redundancy-LLM-scorer.md'
OUT = PILOTS / '20261115_redundancy'
UNITS = OUT / 'rebuild_units.json'
CALLS = OUT / 'llm_score_calls.jsonl'
RES = OUT / 'llm_scores.json'
REP = OUT / 'report_llm.md'
MODEL = 'qwen/qwen3-235b-a22b-2507'
PRICE = (0.14 / 1e6, 0.8 / 1e6)
CAP = 0.20
K = 3


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def run():
    assert file_sha(RULE) and RES.parent.exists()
    units = json.loads(UNITS.read_text())
    pop = {r['instance_id']: r for r in json.loads((PILOTS / '20261115_proxy_support_mq/population.json').read_text())
           if r['protocol'] == 'random_relay'}
    have = json.loads(RES.read_text()) if RES.exists() else {}
    total = spent()
    for inst, agents in units.items():
        if inst in have:
            continue
        q = pop[inst]['question']
        rec = {}
        for agent, us in agents.items():
            scores = []
            for i, u in enumerate(us):
                user = f'Question: {q}\n\nEvidence unit:\n{u}'
                est_in = math.ceil((len(_SCORING_SYSTEM) + len(user)) / 4)
                est_out = 60
                if total + est_in * PRICE[0] + est_out * PRICE[1] > CAP:
                    print(json.dumps({'stop': 'cap', 'spent': round(total, 6)}))
                    RES.write_text(json.dumps(have, indent=1)); return
                with CALLS.open('a') as f:
                    f.write(json.dumps({'event': 'intent', 'key': f'{inst}/{agent}/{i}'}) + '\n')
                r = single_request(APIRequest(system_query=_SCORING_SYSTEM, user_query=user, model=MODEL,
                                              max_tokens=128, temperature=0))
                usg = r.usage or {}
                cost = usg.get('prompt_tokens', est_in) * PRICE[0] + usg.get('completion_tokens', 0) * PRICE[1]
                total += cost
                txt = r.content or ''
                a, b = txt.find('{'), txt.rfind('}')
                try:
                    obj = json.loads(txt[a:b + 1])
                    ok = isinstance(obj, dict) and 'overall' in obj
                except Exception:
                    obj, ok = {}, False
                sc = {'overall': float(obj.get('overall', 0.5)) if ok else 0.5, 'parsed': ok}
                scores.append(sc)
                with CALLS.open('a') as f:
                    f.write(json.dumps({'event': 'result', 'key': f'{inst}/{agent}/{i}', 'usage': usg,
                                        'cost_usd': round(cost, 8), 'parsed': ok}) + '\n')
            rec[agent] = {'units': us, 'overall': [s['overall'] for s in scores],
                          'parsed': [s['parsed'] for s in scores]}
        have[inst] = rec
        RES.write_text(json.dumps(have, indent=1))
        print(json.dumps({'inst': inst, 'agents': len(agents), 'units': sum(len(v) for v in agents.values()),
                          'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


def bootstrap(vals, seed=43, draws=2000):
    rng = random.Random(seed)
    out = []
    n = len(vals)
    for _ in range(draws):
        out.append(sum(vals[rng.randrange(n)] for _ in range(n)) / n)
    out.sort()
    return out[int(0.025 * draws)], out[int(0.975 * draws) - 1]


def score_report():
    units = json.loads(UNITS.read_text())
    sc = json.loads(RES.read_text())
    supports = load_supports()
    rows = []
    for inst, agents in units.items():
        gold = supports.get(inst)
        if not gold:
            continue
        sel = {}
        for proto in ('random_relay', 'score_ranked_relay', 'redundancy_aware_relay'):
            picked = []
            rng = random.Random(hash((inst, proto)) & 0xffffffff)
            for agent, us in agents.items():
                scores = [{'overall': o} for o in sc[inst][agent]['overall']]
                if proto == 'random_relay':
                    idx = list(range(len(us)))
                    rng.shuffle(idx)
                    chosen = [us[i] for i in idx[:K]]
                elif proto == 'score_ranked_relay':
                    chosen = [us[i] for i in sorted(range(len(us)), key=lambda i: -scores[i]['overall'])[:K]]
                else:
                    chosen = _redundancy_select(us, scores, K, 0.5)
                picked += chosen
            sel[proto] = picked
        for proto, us in sel.items():
            rows.append({'instance': inst, 'protocol': proto,
                         'red': redundancy(us), 'ub': useful_budget(us, gold)})
    by = defaultdict(list)
    for r in rows:
        by[r['protocol']].append(r)
    table = {}
    for p, rs in by.items():
        red = [r['red'] for r in rs]
        ub = [r['ub'] for r in rs]
        table[p] = {'n': len(rs), 'red': sum(red) / len(red), 'ub': sum(ub) / len(ub),
                    'red_ci': bootstrap(red), 'ub_ci': bootstrap(ub)}
    # crowding-out
    pool = [r for r in rows if r['protocol'] != 'random_relay']
    qs = sorted(pool, key=lambda r: r['red'])
    parts = [qs[i * len(qs) // 4:(i + 1) * len(qs) // 4] for i in range(4)]
    crowd = [sum(x['ub'] for x in part) / len(part) if part else 0.0 for part in parts]
    overlap = True
    ps = list(by)
    for i in range(len(ps)):
        for j in range(i + 1, len(ps)):
            a, b = table[ps[i]]['red_ci'], table[ps[j]]['red_ci']
            if a[1] < b[0] or b[1] < a[0]:
                overlap = False
    out = {'rule_sha256': file_sha(RULE), 'spend_usd': round(spent(), 6), 'protocols': table,
           'crowd_out_ub_by_red_quartile': [round(x, 4) for x in crowd],
           'red_intervals_overlap': overlap, 'model': MODEL, 'k': K}
    (OUT / 'report_llm.json').write_text(json.dumps(out, indent=1))
    lines = ['# Redundancy rerun with the paper\'s LLM relevance scorer', '',
             '2026-11-15. Rule `Redundancy-LLM-scorer.md` (sha `%s...`). Qwen-235B with the paper\'s scoring prompt; '
             'rebuilt units, k = 3, rho = .5. Spend $%.6f, cap $0.20.' % (out['rule_sha256'][:8], out['spend_usd']),
             '', '| protocol | n | Red [95% CI] | UB [95% CI] |', '| --- | ---: | --- | --- |']
    for p, v in table.items():
        lines.append('| %s | %d | %.3f [%.3f, %.3f] | %.3f [%.3f, %.3f] |'
                     % (p, v['n'], v['red'], v['red_ci'][0], v['red_ci'][1], v['ub'], v['ub_ci'][0], v['ub_ci'][1]))
    lines += ['', 'Crowding-out: useful budget by Red quartile %s.' % out['crowd_out_ub_by_red_quartile'],
              'Red intervals overlap across all protocols: %s.' % out['red_intervals_overlap']]
    REP.write_text('\n'.join(lines) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    import sys
    if '--run' in sys.argv:
        run()
    if '--score' in sys.argv:
        score_report()