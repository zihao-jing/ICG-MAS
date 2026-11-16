"""Step 6: run the frozen point-level Silo-Bench extraction validation.

Rule `rebuttal/pilots/prereg/Per-fact-presence-points-v1.md` (sha e6263584),
prompt `per_fact_points_prompt_v1.json` (sha 86d84ff6), population
`rebuttal/pilots/20261115_sb_points/population.json` (sha 1d1fd1af).
Haiku 5.5 labeller, Opus 5.5 reference, identical prompt, temperature 0.
Cap $3.5, every call logged.

    ./run.sh python -m scripts.per_fact_points_run --run
    ./run.sh python -m scripts.per_fact_points_run --score
"""
import argparse
import hashlib
import os
import json
import math
import random
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.coverage_validation import kappa_binary
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_sb_points'
RULE = ROOT / 'rebuttal/pilots/prereg/Per-fact-presence-points-v1.md'
AMENDMENT = ROOT / 'rebuttal/pilots/prereg/Per-fact-presence-points-v1-amendment-1.md'
PROMPT = ROOT / 'rebuttal/pilots/prereg/per_fact_points_prompt_v1.json'
POP = OUT / 'population.json'
BUILD = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
VALIDATION = OUT / 'validation.json'
REPORT = OUT / 'report.md'
REGISTRY = ROOT / 'rebuttal/validations/registry.json'

OPUS = 'anthropic/claude-opus-5.5'
GEMINI = 'google/gemini-3.6-flash'
HAIKU = 'anthropic/claude-haiku-5.5'
REF = GEMINI  # amendment 1
PRICE = {OPUS: (4.0 / 1e6, 20.0 / 1e6), GEMINI: (0.75 / 1e6, 3.75 / 1e6),
         HAIKU: (0.1 / 1e6, 0.5 / 1e6)}
CAP = 3.5
MAX_TOKENS = int(os.environ.get('POINTS_MAX_TOKENS', '3000'))
SEED = 43
STATUS = {'present', 'partial', 'absent'}
LABEL = 'silobench_extraction_presence_points'


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def render(spec, row, fact):
    entries = '\n'.join(f"[{u['unit_id']}] (agent {u['agent_id']}) {u['text'][:1500]}"
                        for u in row['entries'])
    atoms = '\n'.join(f"{a['atom_id']}: {a['text']}" for a in fact['atoms'])
    return spec['user'].format(question=row['question'], fact=fact['text'],
                               atoms=atoms, entries=entries)


def parse(content, atom_ids):
    obj = last_object(content or '')
    if not isinstance(obj, dict) or not isinstance(obj.get('atoms'), dict):
        return None
    got = obj['atoms']
    if set(got) != atom_ids:
        return None
    out = {}
    for k in atom_ids:
        x = got[k]
        if not isinstance(x, dict) or x.get('status') not in STATUS:
            return None
        if not isinstance(x.get('unit_ids'), list):
            return None
        out[k] = {'status': x['status'], 'unit_ids': x['unit_ids'],
                  'reason': str(x.get('reason', ''))[:240]}
    return out


def call(key, model, spec, user, atoms, cap, total):
    pin, pout = PRICE[model]
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    est_out = min(MAX_TOKENS, 120 + 28 * atoms)
    if total + est_in * pin + est_out * pout > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                'cost_usd': 0.0}) + '\n')
        return None, total
    call_id = sha('|'.join([key, spec['system'], user, str(MAX_TOKENS)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': call_id,
                            'model': model, 'system_sha256': sha(spec['system']),
                            'user_sha256': sha(user), 'max_tokens': MAX_TOKENS,
                            'temperature': 0}) + '\n')
    from utility.apis.router import single_request
    req = APIRequest(system_query=spec['system'], user_query=user, model=model,
                     max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'per_fact_points', 'key': key,
                               'openrouter_reasoning': model == GEMINI})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * pin
            + usage.get('completion_tokens', 0) * pout)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': call_id,
                            'model': model, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def run(cap, limit=None):
    man = json.loads(BUILD.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(PROMPT) == man['prompt_sha256'], 'prompt changed'
    assert file_sha(POP) == man['population_sha256'], 'population changed'
    assert file_sha(AMENDMENT) == man['amendment_sha256'], 'amendment changed'
    spec = json.loads(PROMPT.read_text())
    rows = json.loads(POP.read_text())
    done = set()
    atom_ids = {(r['key'], f['fact_id']): {a['atom_id'] for a in f['atoms']}
                for r in rows for f in r['facts']}
    if CALLS.exists():
        for l in CALLS.read_text().splitlines():
            if not l.strip():
                continue
            e = json.loads(l)
            if e.get('event') != 'result' or not e.get('success'):
                continue
            tag, rest = e['key'].split('/', 1)
            key, fid = rest.rsplit('/', 1)
            if parse(e.get('content'), atom_ids[(key, fid)]) is not None:
                done.add(e['key'])
    total = spent()
    calls = [(r, f) for r in rows for f in r['facts']]
    if limit:
        calls = calls[:limit]
    # remaining expected spend over all unfinished calls
    def expected(r, f):
        user = render(spec, r, f)
        est_in = math.ceil((len(spec['system']) + len(user)) / 4)
        return est_in * (PRICE[REF][0] + PRICE[HAIKU][0]) + \
            min(MAX_TOKENS, 120 + 28 * len(f['atoms'])) * (PRICE[REF][1] + PRICE[HAIKU][1])
    remaining = sum(expected(r, f) for r, f in calls
                    if f"ref/{r['key']}/{f['fact_id']}" not in done
                    or f"lab/{r['key']}/{f['fact_id']}" not in done)
    print(json.dumps({'calls': len(calls) * 2, 'spent': round(total, 4),
                      'remaining_expected': round(remaining, 4),
                      'projected_total': round(total + remaining, 4), 'cap': cap}), flush=True)
    if total + remaining > cap:
        print(json.dumps({'stopped': 'projection_over_cap'}))
        return
    for r, f in calls:
        user = render(spec, r, f)
        ids = {a['atom_id'] for a in f['atoms']}
        for tag, model in (('refg', REF), ('labh', HAIKU)):
            key = f"{tag}/{r['key']}/{f['fact_id']}"
            if key in done:
                continue
            for attempt in (1, 2):
                resp, total = call(key, model, spec, user, len(f['atoms']), cap, total)
                if resp is None:
                    print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
                    return
                ok = resp.success and parse(resp.content, ids) is not None
                if ok or attempt == 2:
                    break
            print(json.dumps({'key': key, 'success': bool(resp.success), 'ok': ok,
                              'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(total, 6)}))


def labels():
    man = json.loads(BUILD.read_text())
    assert file_sha(POP) == man['population_sha256']
    rows = json.loads(POP.read_text())
    atom_ids = {(r['key'], f['fact_id']): {a['atom_id'] for a in f['atoms']}
                for r in rows for f in r['facts']}
    calls = {}
    for l in CALLS.read_text().splitlines():
        if not l.strip():
            continue
        e = json.loads(l)
        if e.get('event') != 'result' or not e.get('success'):
            continue
        try:
            _, rest = e['key'].split('/', 1)
            key, fid = rest.rsplit('/', 1)
        except ValueError:
            continue
        if parse(e.get('content'), atom_ids.get((key, fid), set())) is not None:
            calls[e['key']] = e
    # only parsable results are kept; every attempt stays in the log
    out = []
    for r in rows:
        atoms = {}
        for f in r['facts']:
            ids = {a['atom_id'] for a in f['atoms']}
            rec = {'fact_id': f['fact_id'], 'atoms': {}}
            for tag in ('refg', 'labh'):
                c = calls.get(f"{tag}/{r['key']}/{f['fact_id']}")
                p = parse(c.get('content'), ids) if c and c.get('success') else None
                rec['atoms'][tag] = p
            out.append({'key': r['key'], 'instance_id': r['instance_id'],
                        'model': r['model'], 'fact_id': f['fact_id'],
                        'n_atoms': len(f['atoms']), 'atoms': rec['atoms']})
    return out


def fact_rollup(rec):
    """present iff all atoms present; partial iff some; absent iff none."""
    out = {}
    for tag in ('refg', 'labh'):
        a = rec['atoms'][tag]
        if not a:
            out[tag] = None
            continue
        st = [x['status'] for x in a.values()]
        if all(s == 'present' for s in st):
            out[tag] = 'present'
        elif any(s == 'present' for s in st):
            out[tag] = 'partial'
        else:
            out[tag] = 'absent'
    return out


def boot(pairs, seed=SEED, draws=2000):
    """pairs: list of (x, y, instance). Returns (agreement, ci, kappa, ci)."""
    by = {}
    for x, y, inst in pairs:
        by.setdefault(inst, []).append((x, y))
    keys = sorted(by)

    def stats(sub):
        n = len(sub)
        if not n:
            return float('nan'), float('nan')
        return sum(x == y for x, y in sub) / n, kappa_binary(sub)

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


def score():
    rows = labels()
    # atom-level binary: present vs not
    atom_pairs = []
    atom3 = []
    for r in rows:
        a, b = r['atoms']['refg'], r['atoms']['labh']
        if not a or not b:
            continue
        for k in a:
            x = a[k]['status']; y = b[k]['status']
            atom_pairs.append((x == 'present', y == 'present', r['instance_id']))
            atom3.append((x, y, r['instance_id']))
    # roll-up binary: fact present vs not
    fact_pairs = []
    for r in rows:
        ro = fact_rollup(r)
        if not ro['refg'] or not ro['labh']:
            continue
        fact_pairs.append((ro['refg'] == 'present', ro['labh'] == 'present', r['instance_id']))
    aa, aci, ak, akci = boot(atom_pairs)
    fa, faci, fk, fkci = boot(fact_pairs)
    paired = [r for r in rows if r['atoms']['refg'] and r['atoms']['labh']]
    n_facts_paired = len(paired)
    excluded = len(rows) - n_facts_paired
    wide = akci[0] < 0.40
    passes = (aa >= 0.80 and ak >= 0.60)
    validity = {
        'rule_sha256': file_sha(RULE), 'prompt_sha256': file_sha(PROMPT),
        'amendment_sha256': file_sha(AMENDMENT),
        'population_sha256': file_sha(POP), 'label': LABEL,
        'models': {'labeller': HAIKU, 'reference': REF},
        'n_facts': len(rows), 'n_facts_scored': n_facts_paired, 'n_excluded_facts': excluded,
        'n_atoms': len(atom_pairs), 'n_instances': len({r['instance_id'] for r in rows}),
        'atom': {'agreement': aa, 'agreement_ci': list(aci), 'kappa': ak, 'kappa_ci': list(akci)},
        'rollup': {'agreement': fa, 'agreement_ci': list(faci), 'kappa': fk, 'kappa_ci': list(fkci)},
        'n_facts_paired': len(fact_pairs),
        'bars': {'agreement': 0.8, 'kappa': 0.6}, 'wide_interval': wide,
        'passes': passes, 'spend_usd': round(spent(), 6),
        'bootstrap': {'draws': 2000, 'seed': SEED, 'cluster': 'instance'},
    }
    VALIDATION.write_text(json.dumps(validity, indent=1))
    if passes:
        data = json.loads(REGISTRY.read_text())
        data['validations'] = [v for v in data['validations']
                               if not (v.get('label') == LABEL and
                                       v.get('prompt_sha256') == file_sha(PROMPT))]
        data['validations'].append({
            'label': LABEL, 'version': 'v1', 'prompt_sha256': file_sha(PROMPT),
            'passed': True, 'n_valid': n_facts_paired, 'n_excluded': excluded,
            'agreement': aa, 'agreement_ci': list(aci), 'kappa': ak, 'kappa_ci': list(akci),
            'record': str(VALIDATION.relative_to(ROOT)),
            'note': ('atom level, present vs not; roll-up in the record; fresh 21-instance sample; '
                     'reference Gemini 3.6 Flash under amendment 1'),
        })
        REGISTRY.write_text(json.dumps(data, indent=1))
    print(json.dumps(validity, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    ap.add_argument('--limit', type=int, default=None)
    a = ap.parse_args()
    if a.run:
        run(a.cap_usd, a.limit)
    if a.score:
        score()