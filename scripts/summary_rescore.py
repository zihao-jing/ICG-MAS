"""Summary-exchange strict fidelity re-score under the validated prompt (cap $0.25).

Rule: rebuttal/pilots/prereg/Summary-rescore-v1.md. Helpers copied from scripts/relay_v2_rescore.py.

    ./.conda-env/bin/python -m scripts.summary_rescore --build
    ./.conda-env/bin/python -m scripts.summary_rescore --run
    ./.conda-env/bin/python -m scripts.summary_rescore --score
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from scripts.answer_equiv import last_object
from scripts.compute_audit_metrics import align_gold_to_transmitted, get_gold_units
from src.eval.silo_bench_loader import load_silobench
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
RULE = ROOT / 'rebuttal/pilots/prereg/Summary-rescore-v1.md'
PROMPT = ROOT / 'rebuttal/pilots/prereg/strict_fidelity_pair_prompt_v2.json'
OUT = ROOT / 'rebuttal/pilots/20261115_summary_rescore'
POP = OUT / 'population_pairs.json'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
REPORT = OUT / 'report.md'
RATES = OUT / 'rates.json'
RUNS = {5: 'run_qwen235b_n5', 10: 'run_qwen235b_n10'}
HAIKU = 'anthropic/claude-haiku-5.5'
PIN, POUT = 0.1 / 1e6, 0.5 / 1e6
EST_OUT = 300
CAP = 0.25
MAX_TOKENS = 2500
EXPECTED = 390
LOCK = Lock()
TOTAL = {'v': 0.0}


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def render(spec, pair):
    return spec['user'].format(question='(not shown)', gold=pair['gold'][:2000],
                               entries=f"[unit 1] {pair['unit'][:2000]}")


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    pairs, skipped = [], 0
    for n, run in RUNS.items():
        resp = [json.loads(l) for l in (ROOT / 'results' / run / 'api_responses.jsonl').read_text().splitlines()
                if l.strip()]
        summaries = {}
        for r in resp:
            if r.get('phase') == 'summary' and str(r.get('success')) == 'True':
                summaries.setdefault(r['instance_id'], {})[int(r['agent'])] = r['content']
        for inst in load_silobench(n_agents_filter=n):
            own = summaries.get(inst['id'])
            if not own:
                continue
            transmitted = [own[a] for a in sorted(own)]
            gold = get_gold_units(inst)
            aln = align_gold_to_transmitted(gold, transmitted)
            for (agent_id, gold_text), a in zip(gold, aln):
                unit = a.get('best_unit') or own.get(agent_id)
                if unit is None:
                    skipped += 1
                    continue
                pairs.append({'pair_id': sha(f'summary|{n}|{inst["id"]}|{agent_id}')[:16],
                              'protocol': 'summary_exchange', 'tier': f'n{n}', 'inst_id': inst['id'],
                              'agent_id': agent_id, 'gold': gold_text, 'unit': unit,
                              'best_match_found': a.get('best_unit') is not None})
    if len(pairs) != EXPECTED:
        raise SystemExit(f'pairs {len(pairs)} != {EXPECTED}; not frozen')
    POP.write_text(json.dumps(pairs, ensure_ascii=False))
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE), 'prompt_sha256': file_sha(PROMPT),
           'population_sha256': file_sha(POP), 'pairs': len(pairs), 'skipped_no_unit': skipped,
           'best_match_found': sum(1 for p in pairs if p['best_match_found']),
           'by_tier': dict(Counter(p['tier'] for p in pairs)), 'labeller_model': HAIKU, 'cap_usd': CAP}
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def check_frozen():
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(PROMPT) == man['prompt_sha256'], 'prompt changed'
    assert file_sha(POP) == man['population_sha256'], 'population changed'


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def call(key, spec, user, cap):
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    with LOCK:
        if TOTAL['v'] + est_in * PIN + EST_OUT * POUT > cap:
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap', 'cost_usd': 0.0}) + '\n')
            return None
    cid = sha('|'.join([key, spec['system'], user, str(MAX_TOKENS)]))
    with LOCK, CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid, 'model': HAIKU,
                            'system_sha256': sha(spec['system']), 'user_sha256': sha(user),
                            'max_tokens': MAX_TOKENS, 'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    resp = single_request(APIRequest(system_query=spec['system'], user_query=user, model=HAIKU,
                                     max_tokens=MAX_TOKENS, temperature=0,
                                     metadata={'pilot': 'summary_rescore', 'key': key}))
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * PIN + usage.get('completion_tokens', 0) * POUT
    with LOCK:
        TOTAL['v'] += cost
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid, 'model': HAIKU,
                                'success': resp.success, 'error': resp.error, 'content': resp.content,
                                'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp


def parse(content):
    obj = last_object(content or '')
    if not isinstance(obj, dict) or not isinstance(obj.get('facts'), list) or not obj['facts']:
        return None
    f = obj['facts'][0]
    if f.get('fidelity') not in ('faithful', 'partial', 'distorted', 'absent'):
        return None
    return f['fidelity']


def labels():
    out = {}
    if not CALLS.exists():
        return out
    for l in CALLS.read_text().splitlines():
        if not l.strip():
            continue
        e = json.loads(l)
        if e.get('event') != 'result' or not e.get('success'):
            continue
        f = parse(e.get('content'))
        if f is not None:
            out.setdefault(e['key'].rsplit('/attempt-', 1)[0], f)
    return out


def run():
    check_frozen()
    spec = json.loads(PROMPT.read_text())
    pairs = json.loads(POP.read_text())
    done = set(labels())
    todo = [p for p in pairs if f'labh/{p["pair_id"]}' not in done]
    TOTAL['v'] = spent()
    print(json.dumps({'todo': len(todo), 'spent': round(TOTAL['v'], 6)}), flush=True)

    def one(p):
        user = render(spec, p)
        for attempt in (1, 2):
            resp = call(f'labh/{p["pair_id"]}/attempt-{attempt}', spec, user, CAP)
            if resp is None:
                return None
            if resp.success and parse(resp.content) is not None:
                return True
        return False

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(one, p) for p in todo]
        for i, f in enumerate(as_completed(futs), 1):
            f.result()
            if i % 100 == 0 or i == len(todo):
                print(json.dumps({'done': i, 'of': len(todo), 'spent': round(spent(), 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}), flush=True)


def score():
    check_frozen()
    pairs = json.loads(POP.read_text())
    got = labels()
    c = Counter()
    per_tier = {}
    for p in pairs:
        f = got.get(f'labh/{p["pair_id"]}')
        if f is None:
            c['unlabelled'] += 1
            continue
        c[f] += 1
        per_tier.setdefault(p['tier'], Counter())[f] += 1
    labelled = sum(c[k] for k in ('faithful', 'partial', 'distorted', 'absent'))
    covered = labelled - c['absent']
    res = {'labelled': labelled, 'unlabelled': c['unlabelled'], 'counts': dict(c), 'covered': covered,
           'strict': {'k': c['distorted'], 'n': covered, 'rate': c['distorted'] / covered if covered else None,
                      'ci': wilson(c['distorted'], covered)},
           'broad': {'k': c['distorted'] + c['partial'], 'n': covered,
                     'rate': (c['distorted'] + c['partial']) / covered if covered else None,
                     'ci': wilson(c['distorted'] + c['partial'], covered)},
           'omission': {'k': c['absent'], 'n': labelled, 'rate': c['absent'] / labelled if labelled else None,
                        'ci': wilson(c['absent'], labelled)},
           'by_tier': {t: dict(v) for t, v in per_tier.items()},
           'spend_usd': round(spent(), 6), 'cap_usd': CAP}
    RATES.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.run:
        run()
    if a.score:
        score()
