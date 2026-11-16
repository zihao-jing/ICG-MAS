"""A2: run the point-level labeller on the aligned E1 anchor facts and score it.

Rule `rebuttal/pilots/prereg/Anchor-alignment-v1.md` (sha 1d73f49e), point prompt
`per_fact_points_prompt_v1.json` (sha 86d84ff6). Haiku 5.5 labeller, Gemini 3.6 Flash
reference, temperature 0, cap $1.5, every call logged.

    ./run.sh python -m scripts.point_anchor_run --run
    ./run.sh python -m scripts.point_anchor_run --score
"""
import argparse
import hashlib
import json
import random
from pathlib import Path

from scripts.coverage_validation import kappa_binary
from scripts import per_fact_points_run as pfp

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_anchor_points'
RULE = ROOT / 'rebuttal/pilots/prereg/Anchor-alignment-v1.md'
PROMPT = ROOT / 'rebuttal/pilots/prereg/per_fact_points_prompt_v1.json'
POP = OUT / 'population_aligned.json'
BUILD = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
VALIDATION = OUT / 'validation.json'
REPORT = OUT / 'report.md'
REGISTRY = ROOT / 'rebuttal/validations/registry.json'
HAIKU = 'anthropic/claude-haiku-5.5'
GEMINI = 'google/gemini-3.6-flash'
CAP = 1.5
SEED = 43
pfp.CALLS = CALLS  # keep this run's log separate from the point pilot


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')
LABEL = 'point_presence_anchor_e1'


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(cap):
    man = json.loads(BUILD.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(PROMPT) == man['prompt_sha256'], 'prompt changed'
    assert file_sha(POP) == (man.get('pool_sha256') or man.get('population_sha256')), 'population changed'
    spec = json.loads(PROMPT.read_text())
    rows = json.loads(POP.read_text())
    done = set()
    ids = {(r['key'], r['facts'][0]['fact_id']): {a['atom_id'] for a in r['facts'][0]['atoms']}
           for r in rows}
    if CALLS.exists():
        for l in CALLS.read_text().splitlines():
            if not l.strip():
                continue
            e = json.loads(l)
            if e.get('event') != 'result' or not e.get('success'):
                continue
            _, rest = e['key'].split('/', 1)
            key, fid = rest.rsplit('/', 1)
            if pfp.parse(e.get('content'), ids.get((key, fid), set())) is not None:
                done.add(e['key'])
    total = spent()
    for r in rows:
        f = r['facts'][0]
        user = pfp.render(spec, r, f)
        for tag, model in (('refg', GEMINI), ('labh', HAIKU)):
            key = f"{tag}/{r['key']}/{f['fact_id']}"
            if key in done:
                continue
            for attempt in (1, 2):
                resp, total = pfp.call(key, model, spec, user, len(f['atoms']), cap, total)
                if resp is None:
                    print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
                    return
                ok = resp.success and pfp.parse(resp.content, ids[(r['key'], f['fact_id'])]) is not None
                if ok or attempt == 2:
                    break
            print(json.dumps({'key': key, 'ok': ok, 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(total, 6)}))


def labels():
    rows = json.loads(POP.read_text())
    calls = {}
    ids = {(r['key'], r['facts'][0]['fact_id']): {a['atom_id'] for a in r['facts'][0]['atoms']}
           for r in rows}
    for l in CALLS.read_text().splitlines() if CALLS.exists() else []:
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
        if pfp.parse(e.get('content'), ids.get((key, fid), set())) is not None:
            calls[e['key']] = e
    out = []
    for r in rows:
        fid = r['facts'][0]['fact_id']
        rec = {'key': r['key'], 'instance_id': r['instance_id'],
               'author_present': r['author_present']}
        for tag in ('refg', 'labh'):
            c = calls.get(f"{tag}/{r['key']}/{fid}")
            rec[tag] = pfp.parse(c.get('content'), ids[(r['key'], fid)]) if c else None
        out.append(rec)
    return out


def present(atom_labels):
    if not atom_labels:
        return None
    return all(x['status'] == 'present' for x in atom_labels.values())


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


def score():
    rows = labels()
    lab_pairs = []
    cells = {}
    for r in rows:
        l = present(r['labh'])
        if l is None:
            continue
        a = bool(r['author_present'])
        lab_pairs.append((a, l, r['instance_id']))
        cells[(a, l)] = cells.get((a, l), 0) + 1
    aa, aci, ak, akci = boot(lab_pairs)
    ref_pairs = []
    for r in rows:
        p = present(r['refg'])
        if p is None:
            continue
        ref_pairs.append((bool(r['author_present']), p, r['instance_id']))
    ra, raci, rk, rkci = boot(ref_pairs)
    wide = akci[0] < 0.40
    passes = aa >= 0.80 and ak >= 0.60
    v = {
        'label': LABEL, 'rule_sha256': file_sha(RULE), 'prompt_sha256': file_sha(PROMPT),
        'population_sha256': file_sha(POP),
        'models': {'labeller': HAIKU, 'reference': GEMINI},
        'n_facts': len(lab_pairs), 'n_instances': len({r['instance_id'] for r in rows}),
        'cells': {f'author_{a}_lab_{l}': c for (a, l), c in sorted(cells.items())},
        'labeller_vs_author': {'agreement': aa, 'agreement_ci': list(aci),
                               'kappa': ak, 'kappa_ci': list(akci)},
        'reference_vs_author': {'agreement': ra, 'agreement_ci': list(raci),
                                'kappa': rk, 'kappa_ci': list(rkci)},
        'bars': {'agreement': 0.8, 'kappa': 0.6}, 'wide_interval': wide,
        'passes': passes, 'spend_usd': round(spent(), 6),
        'bootstrap': {'draws': 2000, 'seed': SEED, 'cluster': 'instance'},
        'note': 'E1 anchor, 80 facts (10 author-absent + 70 present), board checkpoint, '
                'author present = a non-absent board carrier',
    }
    VALIDATION.write_text(json.dumps(v, indent=1))
    if passes:
        data = json.loads(REGISTRY.read_text())
        data['validations'] = [x for x in data['validations']
                               if not (x.get('label') == LABEL and
                                       x.get('prompt_sha256') == file_sha(PROMPT))]
        data['validations'].append({
            'label': LABEL, 'version': 'v1', 'prompt_sha256': file_sha(PROMPT),
            'passed': True, 'n_valid': len(lab_pairs),
            'n_excluded': len(rows) - len(lab_pairs),
            'agreement': aa, 'agreement_ci': list(aci), 'kappa': ak, 'kappa_ci': list(akci),
            'record': str(VALIDATION.relative_to(ROOT)),
            'note': 'E1 anchor facts, board; author present = non-absent carrier',
        })
        REGISTRY.write_text(json.dumps(data, indent=1))
    print(json.dumps(v, indent=1))


def configure(out_dir, rule, population, label, build):
    global OUT, RULE, POP, BUILD, VALIDATION, REPORT, LABEL, CALLS
    OUT = Path(out_dir)
    RULE = Path(rule)
    POP = Path(population)
    BUILD = Path(build)
    VALIDATION = OUT / 'validation.json'
    REPORT = OUT / 'report.md'
    LABEL = label
    CALLS = OUT / 'calls.jsonl'
    pfp.CALLS = CALLS


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    ap.add_argument('--dir')
    ap.add_argument('--rule')
    ap.add_argument('--population')
    ap.add_argument('--build')
    ap.add_argument('--label')
    a = ap.parse_args()
    if a.dir:
        configure(a.dir, a.rule or str(RULE), a.population or str(Path(a.dir) / 'population_matched.json'),
                  a.label or 'silobench_extraction_presence_matched', a.build or str(Path(a.dir) / 'build_manifest.json'))
    if a.run:
        run(a.cap_usd)
    if a.score:
        score()