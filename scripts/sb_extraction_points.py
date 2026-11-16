"""Silo-Bench extraction checkpoint re-scored with the post-amendment point label (cap $6).

51 qwen235b random_relay traces (the E3 population). Gold supports labelled atom by atom against the extraction
entries with `per_fact_points_prompt_v1.json` (validated on Silo-Bench extraction, κ .847).
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from scripts.per_fact_points_run import parse
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
PILOTS = ROOT / 'rebuttal/pilots'
PROMPT = PILOTS / 'prereg/per_fact_points_prompt_v1.json'
POP = PILOTS / '20261115_proxy_support_sb_fixed/population.json'
E3 = PILOTS / '20261114_e3_sb/population.json'
OUT = PILOTS / '20261115_sb_extraction_points'
CALLS = OUT / 'calls.jsonl'
RES = OUT / 'results.jsonl'
MODEL = 'anthropic/claude-haiku-5.5'
PRICE = (0.10 / 1e6, 0.50 / 1e6)
CAP = 6.0
TOK = 4096


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def atoms_of(text):
    return [a.strip() for a in text.replace('\n', ' ').split('. ') if len(a.strip()) > 3]


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
            atoms = [(f'a{i}', t) for i, t in enumerate(atoms_of(sup['text']), 1)]
            if not atoms:
                continue
            user = spec['user'].format(question=r['question'], fact=sup['text'],
                                       atoms='\n'.join(f'{a}: {t}' for a, t in atoms), entries=entries)
            est_in = math.ceil((len(spec['system']) + len(user)) / 4)
            est_out = min(TOK, 120 + 28 * len(atoms))
            if total + est_in * PRICE[0] + est_out * PRICE[1] > CAP:
                print(json.dumps({'stop': 'cap', 'spent': round(total, 6)})); return
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'intent', 'key': r['key'], 'support': si}) + '\n')
            resp = single_request(APIRequest(system_query=spec['system'], user_query=user, model=MODEL,
                                             max_tokens=TOK, temperature=0))
            u = resp.usage or {}
            cost = u.get('prompt_tokens', est_in) * PRICE[0] + u.get('completion_tokens', 0) * PRICE[1]
            total += cost
            lab = parse(resp.content or '', {a for a, _ in atoms})
            statuses = {} if lab is None else {k: v['status'] for k, v in lab.items()}
            rec = {'key': r['key'], 'instance': r['instance_id'], 'support_idx': si,
                   'atoms': len(atoms), 'statuses': statuses, 'valid': lab is not None}
            with RES.open('a') as f:
                f.write(json.dumps(rec) + '\n')
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'result', 'key': r['key'], 'support': si, 'usage': u,
                                    'cost_usd': round(cost, 8), 'valid': lab is not None}) + '\n')
            print(json.dumps({'inst': r['instance_id'], 'support': si, 'atoms': len(atoms),
                              'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6), 'calls': sum(1 for _ in CALLS.read_text().splitlines())}))


def score():
    rows = [json.loads(l) for l in RES.read_text().splitlines() if l.strip()]
    per_trace = {}
    atom_total = atom_present = support_total = support_present = 0
    for r in rows:
        if not r['valid']:
            continue
        st = list(r['statuses'].values())
        atom_total += len(st)
        atom_present += sum(1 for s in st if s == 'present')
        support_total += 1
        support_present += 1 if st and all(s == 'present' for s in st) else 0
        per_trace.setdefault(r['key'], []).extend(st)
    n = len(per_trace)
    trace_cr = {k: (sum(1 for s in v if s == 'present') / len(v)) for k, v in per_trace.items() if v}
    out = {'traces': n, 'supports': support_total, 'atoms': atom_total,
           'atom_presence': atom_present / atom_total if atom_total else None,
           'support_complete': support_present / support_total if support_total else None,
           'trace_atom_cr_mean': sum(trace_cr.values()) / len(trace_cr) if trace_cr else None,
           'spend_usd': round(spent(), 6),
           'prompt_sha': file_sha(PROMPT), 'cap_usd': CAP}
    (OUT / 'score.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.run: run()
    if a.score: score()