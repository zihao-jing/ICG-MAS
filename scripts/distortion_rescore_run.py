"""A4 re-score: strict fidelity on the four new models' distortion pairs.

Rule `rebuttal/pilots/prereg/Strict-fidelity-new-models-v1.md` (sha 167dcb36),
prompt `strict_fidelity_pair_prompt_v1.json`. Haiku 5.5 labeller, Opus 5.5 reference,
cap $4, every call logged.

    ./run.sh python -m scripts.distortion_rescore_run --validate
    ./run.sh python -m scripts.distortion_rescore_run --full
    ./run.sh python -m scripts.distortion_rescore_run --score
"""
import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.coverage_validation import kappa_binary
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_distortion_rescore'
RULE = ROOT / 'rebuttal/pilots/prereg/Strict-fidelity-new-models-v1.md'
PROMPT = ROOT / 'rebuttal/pilots/prereg/strict_fidelity_pair_prompt_v1.json'
PAIRS = OUT / 'population_pairs.json'
VAL = OUT / 'validation_sample.json'
BUILD = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
VALIDATION = OUT / 'validation.json'
REPORT = OUT / 'report.md'
REGISTRY = ROOT / 'rebuttal/validations/registry.json'
HAIKU = 'anthropic/claude-haiku-5.5'
OPUS = 'anthropic/claude-opus-5.5'
PRICE = {OPUS: (4.0 / 1e6, 20.0 / 1e6), HAIKU: (0.1 / 1e6, 0.5 / 1e6)}
CAP = 4.0
MAX_TOKENS = 2500
FID = {'faithful', 'partial', 'distorted', 'absent'}
LABEL = 'strict_fidelity_new_models_pairs'
SEED = 43


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def render(spec, pair):
    entries = f"[unit 1] {pair['unit'][:2000]}"
    return spec['user'].format(question='(not shown)', gold=pair['gold'][:2000],
                               entries=entries)


def parse(content):
    obj = last_object(content or '')
    if not isinstance(obj, dict) or not isinstance(obj.get('facts'), list):
        return None
    for x in obj['facts']:
        if x.get('fact_id') != 'f1':
            continue
        if str(x.get('fidelity')) not in FID or str(x.get('status')) not in {'present', 'partial', 'absent'}:
            return None
        return {'status': x['status'], 'fidelity': x['fidelity'],
                'reason': str(x.get('reason', ''))[:240]}
    return None


def call(key, model, spec, user, cap, total):
    pin, pout = PRICE[model]
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    est_out = 900 if model == OPUS else 300
    if total + est_in * pin + est_out * pout > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap', 'cost_usd': 0.0}) + '\n')
        return None, total
    call_id = sha('|'.join([key, spec['system'], user, str(MAX_TOKENS)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': call_id, 'model': model,
                            'system_sha256': sha(spec['system']), 'user_sha256': sha(user),
                            'max_tokens': MAX_TOKENS, 'temperature': 0}) + '\n')
    from utility.apis.router import single_request
    req = APIRequest(system_query=spec['system'], user_query=user, model=model,
                     max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'distortion_rescore', 'key': key,
                               'openrouter_reasoning': model == OPUS})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * pin
            + usage.get('completion_tokens', 0) * pout)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': call_id, 'model': model,
                            'success': resp.success, 'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def done_keys():
    out = set()
    if CALLS.exists():
        for l in CALLS.read_text().splitlines():
            if not l.strip():
                continue
            e = json.loads(l)
            if e.get('event') == 'result' and e.get('success') and parse(e.get('content')):
                out.add(e['key'])
    return out


def loop(pairs, tags, cap):
    man = json.loads(BUILD.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(PROMPT) == man['prompt_sha256'], 'prompt changed'
    spec = json.loads(PROMPT.read_text())
    done = done_keys()
    total = spent()
    for p in pairs:
        user = render(spec, p)
        for tag, model in tags:
            key = f"{tag}/{p['pair_id']}"
            if key in done:
                continue
            for attempt in (1, 2):
                resp, total = call(key, model, spec, user, cap, total)
                if resp is None:
                    print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
                    return
                ok = resp.success and parse(resp.content) is not None
                if ok or attempt == 2:
                    break
            print(json.dumps({'key': key, 'ok': ok, 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(total, 6)}))


def labels():
    got = {}
    for l in CALLS.read_text().splitlines():
        if not l.strip():
            continue
        e = json.loads(l)
        if e.get('event') != 'result' or not e.get('success'):
            continue
        p = parse(e.get('content'))
        if p is not None:
            got[e['key']] = p
    return got


def boot(pairs, seed=SEED, draws=2000):
    by = {}
    for x, y, inst in pairs:
        by.setdefault(inst, []).append((x, y))
    keys = sorted(by)
    def stats(sub):
        n = len(sub)
        if not n:
            return float('nan'), float('nan')
        return sum(a == b for a, b in sub) / n, kappa_binary(sub)
    a, k = stats([(x, y) for x, y, _ in pairs])
    rng = random.Random(seed)
    aa, kk = [], []
    for _ in range(draws):
        sub = []
        for _ in keys:
            sub += by[keys[rng.randrange(len(keys))]]
        av, kv = stats(sub)
        if av == av:
            aa.append(av)
        if kv == kv:
            kk.append(kv)
    def ci(v):
        v = sorted(v)
        return (v[int(.025 * len(v))], v[int(.975 * len(v)) - 1]) if v else (float('nan'), float('nan'))
    return a, ci(aa), k, ci(kk)


def cp(k, n):
    """Clopper-Pearson 95% interval by bisection on the binomial CDF."""
    if n == 0:
        return 0.0, 1.0
    def cdf(p, upto):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(upto + 1))
    def solve(f, target):
        lo, hi = 0.0, 1.0
        for _ in range(90):
            mid = (lo + hi) / 2
            if f(mid) > target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    lo = 0.0 if k == 0 else solve(lambda p: cdf(p, k - 1), 0.975)
    hi = 1.0 if k == n else solve(lambda p: cdf(p, k), 0.025)
    return lo, hi


def score_validation():
    pairs = json.loads(VAL.read_text())
    got = labels()
    lab, ref = [], []
    cells = {}
    for p in pairs:
        a = got.get(f'labh/{p["pair_id"]}')
        b = got.get(f'refg/{p["pair_id"]}')
        if not a or not b:
            continue
        lab.append((b['fidelity'] == 'distorted', a['fidelity'] == 'distorted', p['instance_id']))
        ref.append((b['fidelity'], a['fidelity']))
        cells[(b['fidelity'], a['fidelity'])] = cells.get((b['fidelity'], a['fidelity']), 0) + 1
    aa, aci, ak, akci = boot(lab)
    three = [(x, y) for x, y in ref]
    a3 = sum(x == y for x, y in three) / len(three) if three else float('nan')
    passes = aa >= 0.80 and ak >= 0.60
    v = {'label': LABEL, 'rule_sha256': file_sha(RULE), 'prompt_sha256': file_sha(PROMPT),
         'validation_sha256': file_sha(VAL), 'models': {'labeller': HAIKU, 'reference': OPUS},
         'n_pairs': len(lab), 'n_instances': len({p['instance_id'] for p in pairs}),
         'distorted_vs_not': {'agreement': aa, 'agreement_ci': list(aci), 'kappa': ak, 'kappa_ci': list(akci)},
         'three_class_agreement': a3, 'cells': {f'{x}->{y}': c for (x, y), c in sorted(cells.items())},
         'bars': {'agreement': 0.8, 'kappa': 0.6},
         'wide_interval': akci[0] < 0.40, 'passes': passes, 'spend_usd': round(spent(), 6),
         'bootstrap': {'draws': 2000, 'seed': SEED, 'cluster': 'instance'}}
    VALIDATION.write_text(json.dumps(v, indent=1))
    if passes:
        data = json.loads(REGISTRY.read_text())
        data['validations'] = [x for x in data['validations']
                               if not (x.get('label') == LABEL and x.get('prompt_sha256') == file_sha(PROMPT))]
        data['validations'].append({'label': LABEL, 'version': 'v1', 'prompt_sha256': file_sha(PROMPT),
                                    'passed': True, 'n_valid': len(lab), 'n_excluded': 0,
                                    'agreement': aa, 'agreement_ci': list(aci),
                                    'kappa': ak, 'kappa_ci': list(akci),
                                    'record': str(VALIDATION.relative_to(ROOT)),
                                    'note': 'distorted vs not; 120 eligible pairs, 30 per model'})
        REGISTRY.write_text(json.dumps(data, indent=1))
    print(json.dumps(v, indent=1))


def score_rates():
    pairs = json.loads(PAIRS.read_text())
    got = labels()
    out = {}
    for p in pairs:
        lab = got.get(f'labh/{p["pair_id"]}')
        if not lab:
            continue
        m = out.setdefault(p['model'], {'eligible': 0, 'labelled': 0, 'absent': 0,
                                        'covered': 0, 'distorted': 0, 'partial': 0, 'faithful': 0})
        m['eligible'] += 1
        m['labelled'] += 1
        f = lab['fidelity']
        m[f] = m.get(f, 0) + 1
        if f != 'absent':
            m['covered'] += 1
    for model, m in out.items():
        m['rate_covered'] = m['distorted'] / m['covered'] if m['covered'] else None
        m['rate_covered_ci'] = list(cp(m['distorted'], m['covered'])) if m['covered'] else None
        m['rate_eligible'] = m['distorted'] / m['eligible'] if m['eligible'] else None
        m['rate_eligible_ci'] = list(cp(m['distorted'], m['eligible'])) if m['eligible'] else None
    (OUT / 'rates.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--validate', action='store_true')
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--score', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    if a.validate:
        loop(json.loads(VAL.read_text()), (('refg', OPUS), ('labh', HAIKU)), a.cap_usd)
    if a.full:
        loop(json.loads(PAIRS.read_text()), (('labh', HAIKU),), a.cap_usd)
    if a.score:
        score_validation()
        score_rates()