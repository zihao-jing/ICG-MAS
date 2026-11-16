"""Silo-Bench extraction re-score under the validated point unit (list elements, dict keys, sentences).

The first re-score (`sb_extraction_points.py`) split supports on sentence boundaries only, so 350 of the 380
supports were labelled as one atom each and the figures do not inherit the atom-level validation (kappa .847).
This rerun uses `per_fact_points_build.atomize`, the unit frozen in `Per-fact-presence-points-v1.md`.

    ./run.sh python -m scripts.sb_extraction_points_rule --run
    ./run.sh python -m scripts.sb_extraction_points_rule --score
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from scripts.per_fact_points_build import atomize
from scripts.per_fact_points_run import parse
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
PILOTS = ROOT / 'rebuttal/pilots'
PROMPT = PILOTS / 'prereg/per_fact_points_prompt_v1.json'
POP = PILOTS / '20261115_proxy_support_sb_fixed/population.json'
E3 = PILOTS / '20261114_e3_sb/population.json'
OUT = PILOTS / '20261115_sb_extraction_points_rule'
CALLS = OUT / 'calls.jsonl'
RES = OUT / 'results.jsonl'
MODEL = 'anthropic/claude-haiku-5.5'
PRICE = (0.10 / 1e6, 0.50 / 1e6)
CAP = 2.0
TOK = 8192


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def population():
    e3 = {x['instance'] for x in json.loads(E3.read_text())}
    pop = json.loads(POP.read_text())
    return [r for r in pop if r['model'] == 'qwen235b' and r['protocol'] == 'random_relay'
            and r['instance_id'] in e3]


def run():
    spec = json.loads(PROMPT.read_text())
    rows = population()
    done = set()
    if RES.exists():
        for l in RES.read_text().splitlines():
            if l.strip():
                e = json.loads(l)
                done.add((e['key'], e['support_idx']))
    total = spent()
    for r in rows:
        entries = '\n'.join(f"[{u['unit_id']}] (agent {u['agent_id']}) {u['text'][:1500]}"
                            for u in r['checkpoints'].get('extraction') or [])
        for si, sup in enumerate(r.get('gold_supports') or []):
            if (r['key'], si) in done:
                continue
            atoms, kind = atomize(sup['text'])
            if not atoms:
                continue
            user = spec['user'].format(question=r['question'], fact=sup['text'],
                                       atoms='\n'.join(f'a{j}: {t}' for j, t in enumerate(atoms, 1)),
                                       entries=entries)
            est_in = math.ceil((len(spec['system']) + len(user)) / 4)
            est_out = min(TOK, 150 + 32 * len(atoms))
            if total + est_in * PRICE[0] + est_out * PRICE[1] > CAP:
                print(json.dumps({'stop': 'cap', 'spent': round(total, 6)})); return
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'intent', 'key': r['key'], 'support': si}) + '\n')
            resp = single_request(APIRequest(system_query=spec['system'], user_query=user, model=MODEL,
                                             max_tokens=TOK, temperature=0))
            u = resp.usage or {}
            cost = u.get('prompt_tokens', est_in) * PRICE[0] + u.get('completion_tokens', 0) * PRICE[1]
            total += cost
            lab = parse(resp.content or '', {f'a{j}' for j in range(1, len(atoms) + 1)})
            statuses = {} if lab is None else {k: v['status'] for k, v in lab.items()}
            rec = {'key': r['key'], 'instance': r['instance_id'], 'support_idx': si, 'kind': kind,
                   'atoms': len(atoms), 'statuses': statuses, 'valid': lab is not None}
            with RES.open('a') as f:
                f.write(json.dumps(rec) + '\n')
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'result', 'key': r['key'], 'support': si, 'usage': u,
                                    'cost_usd': round(cost, 8), 'valid': lab is not None}) + '\n')
            print(json.dumps({'inst': r['instance_id'], 'support': si, 'kind': kind, 'atoms': len(atoms),
                              'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6), 'calls': sum(1 for _ in CALLS.read_text().splitlines())}))


def score():
    rows = [json.loads(l) for l in RES.read_text().splitlines() if l.strip()]
    per_trace = {}
    atom_total = atom_present = support_total = 0
    support_present = support_partial = 0
    kind_stat = {}
    for r in rows:
        if not r['valid']:
            continue
        st = list(r['statuses'].values())
        atom_total += len(st)
        atom_present += sum(1 for s in st if s == 'present')
        support_total += 1
        allp = bool(st) and all(s == 'present' for s in st)
        some = any(s == 'present' for s in st)
        support_present += allp
        support_partial += some and not allp
        k = r['kind']
        a = kind_stat.setdefault(k, {'supports': 0, 'atoms': 0, 'present': 0})
        a['supports'] += 1; a['atoms'] += len(st); a['present'] += sum(1 for s in st if s == 'present')
        per_trace.setdefault(r['key'], []).extend(st)
    trace_cr = {k: sum(1 for s in v if s == 'present') / len(v) for k, v in per_trace.items() if v}
    out = {'traces': len(per_trace), 'supports': support_total, 'atoms': atom_total,
           'atom_presence': atom_present / atom_total if atom_total else None,
           'support_present': support_present / support_total if support_total else None,
           'support_partial': support_partial / support_total if support_total else None,
           'trace_atom_cr_mean': sum(trace_cr.values()) / len(trace_cr) if trace_cr else None,
           'invalid': sum(1 for r in rows if not r['valid']),
           'by_kind': {k: {'supports': v['supports'], 'atoms': v['atoms'],
                           'atom_presence': v['present'] / v['atoms'] if v['atoms'] else None}
                       for k, v in kind_stat.items()},
           'spend_usd': round(spent(), 6), 'prompt_sha': file_sha(PROMPT), 'cap_usd': CAP}
    (OUT / 'score.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.run: run()
    if a.score: score()