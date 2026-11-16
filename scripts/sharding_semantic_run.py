"""Run the shard-presence labels and rescore both audit cells (cap $1).

Rule `prereg/Sharding-presence-semantic-v1.md` hashed into build_manifest.json before any call.

    ./run.sh python -m scripts.sharding_semantic_run --build
    ./run.sh python -m scripts.sharding_semantic_run --run
    ./run.sh python -m scripts.sharding_semantic_run --score
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import scripts.b5_attribution_2x2 as B
from scripts.per_fact_points_build import atomize
from scripts.per_fact_points_run import parse
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
PILOTS = ROOT / 'rebuttal/pilots'
RULE = PILOTS / 'prereg/Sharding-presence-semantic-v1.md'
PROMPT = PILOTS / 'prereg/per_fact_points_prompt_v1.json'
OUT = PILOTS / '20261115_sharding_semantic'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
MANIFEST = OUT / 'build_manifest.json'
MODEL = 'anthropic/claude-haiku-5.5'
PRICE = (0.10 / 1e6, 0.50 / 1e6)
CAP = 1.00
TOK = 4096


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def jobs():
    rows = json.loads((OUT / 'calls_to_make.json').read_text())
    out = []
    for r in rows:
        atoms, kind = atomize(r['fact'])
        if not atoms:
            continue
        entries = '\n'.join(f"[{a}] {t}" for a, t in zip(r['agents'], r['shards']))
        out.append({'key': r['key'], 'fact_id': r['fact_id'], 'fact': r['fact'], 'atoms': atoms,
                    'kind': kind, 'question': r['question'], 'entries': entries,
                    'old_label': r['old_shard_label'], 'old_recall': r['old_recall'],
                    'cells': r['cells']})
    return out


def rollup(statuses):
    vals = list(statuses.values())
    if not vals:
        return 'invalid'
    if all(x == 'present' for x in vals):
        return 'present'
    if all(x == 'absent' for x in vals):
        return 'absent'
    return 'partial'


def build():
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    r = jobs()
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE),
           'prompt_sha256': file_sha(PROMPT), 'model': MODEL, 'cap_usd': CAP,
           'calls': len(r), 'cases': len({x['key'] for x in r}),
           'projection_usd': round(sum(
               (math.ceil((len(json.loads(PROMPT.read_text())['system']) + 200) / 4)) * PRICE[0]
               + (150 + 32 * len(x['atoms'])) * PRICE[1] for x in r), 6)}
    OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def run():
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256'] and file_sha(PROMPT) == man['prompt_sha256']
    spec = json.loads(PROMPT.read_text())
    done = set()
    if RESULTS.exists():
        for l in RESULTS.read_text().splitlines():
            if l.strip():
                e = json.loads(l)
                done.add((e['key'], e['fact_id']))
    total = spent()
    for j in jobs():
        if (j['key'], j['fact_id']) in done:
            continue
        user = spec['user'].format(question=j['question'], fact=j['fact'],
                                   atoms='\n'.join(f'a{i}: {t}' for i, t in enumerate(j['atoms'], 1)),
                                   entries=j['entries'])
        est_in = math.ceil((len(spec['system']) + len(user)) / 4)
        est_out = 150 + 32 * len(j['atoms'])
        if total + est_in * PRICE[0] + est_out * PRICE[1] > CAP:
            print(json.dumps({'stop': 'cap', 'spent': round(total, 6)})); return
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'intent', 'key': j['key'], 'fact': j['fact_id']}) + '\n')
        resp = single_request(APIRequest(system_query=spec['system'], user_query=user, model=MODEL,
                                         max_tokens=TOK, temperature=0))
        u = resp.usage or {}
        cost = u.get('prompt_tokens', est_in) * PRICE[0] + u.get('completion_tokens', 0) * PRICE[1]
        total += cost
        lab = parse(resp.content or '', {f'a{i}' for i in range(1, len(j['atoms']) + 1)})
        statuses = {} if lab is None else {k: v['status'] for k, v in lab.items()}
        st = rollup(statuses) if lab is not None else 'invalid'
        rec = {'key': j['key'], 'fact_id': j['fact_id'], 'kind': j['kind'], 'atoms': len(j['atoms']),
               'statuses': statuses, 'label': st, 'old_label': j['old_label'],
               'old_recall': j['old_recall'], 'valid': lab is not None, 'cells': j['cells']}
        with RESULTS.open('a') as f:
            f.write(json.dumps(rec) + '\n')
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'result', 'key': j['key'], 'fact': j['fact_id'], 'usage': u,
                                'cost_usd': round(cost, 8), 'valid': lab is not None}) + '\n')
        print(json.dumps({'key': j['key'][:30], 'fact': j['fact_id'], 'old': j['old_label'],
                          'new': st, 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


def score():
    """Rebuild both cells with the new shard labels."""
    P = PILOTS
    new = {}
    for l in RESULTS.read_text().splitlines():
        if l.strip():
            e = json.loads(l)
            new[(e['key'], e['fact_id'])] = rollup(e['statuses']) if e['valid'] else 'invalid'
    cases = {c['key']: c for c in json.loads(B.CASES.read_text())}
    known = {k: c['known_stage'] for k, c in cases.items()}
    # stored per-case labels and the missing-fact sets are rebuilt from the build list
    cells_missing = json.loads((OUT / 'missing_by_cell.json').read_text())
    missing = {}
    for k, fids in cells_missing.items():
        key, cell = k.rsplit('|', 1)
        missing[(key, cell)] = fids
    old = {'gemini': {r['key']: r.get('stage') for r in json.loads(B.AUDIT_A_RESULTS.read_text())['items']},
           'qwen': {r['key']: r.get('stage') for r in
                    json.loads((P / '20261115_b5_qwen_design_a/results.json').read_text())['items']}}
    out = {}
    for cell in ('gemini', 'qwen'):
        rows = {}
        for key, stage in old[cell].items():
            if not stage:
                continue
            mf = missing.get((key, cell), [])
            labels = [new.get((key, f), 'invalid') for f in mf]
            if not labels or 'invalid' in labels:
                rows[key] = stage
                continue
            if all(x == 'absent' for x in labels):
                rows[key] = 'sharding'
            elif 'absent' in labels:
                rows[key] = 'sharding'
            else:
                rows[key] = 'extraction'
        keys = [k for k in known if k in rows]
        conf = Counter((known[k], rows[k]) for k in keys)
        out[cell] = {'n': len(keys), 'correct': sum(known[k] == rows[k] for k in keys),
                     'old_correct': sum(known[k] == old[cell][k] for k in keys),
                     'confusion': {f'{a}->{b}': n for (a, b), n in conf.items() if a != b},
                     'sharding_known_called_extraction': sum(1 for k in keys if known[k] == 'sharding'
                                                             and rows[k] == 'extraction'),
                     'sharding_known_called_extraction_old': sum(
                         1 for k in keys if known[k] == 'sharding' and old[cell][k] == 'extraction'),
                     'moved_to_sharding': sorted(
                         k for k in keys if known[k] == 'sharding' and old[cell][k] == 'extraction'
                         and rows[k] == 'sharding'),
                     'broke': sorted(k for k in keys if old[cell][k] == known[k] and rows[k] != known[k])}
    rows_all = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    for r in rows_all:
        r['label'] = rollup(r['statuses']) if r['valid'] else 'invalid'
    labels = Counter(r['label'] for r in rows_all)
    transitions = Counter((r['old_label'], r['label']) for r in rows_all)
    out['labels'] = {'new_counts': dict(labels), 'transitions': {f'{a}->{b}': n for (a, b), n in transitions.items()}}
    out['spend_usd'] = round(spent(), 6)
    (OUT / 'score.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.build: build()
    if a.run: run()
    if a.score: score()