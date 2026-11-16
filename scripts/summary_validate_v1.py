"""Summary-exchange strict-fidelity validation, stratified 30 pairs. Cap $0.50.

Rule: rebuttal/pilots/prereg/Summary-strict-validation-v1.md (frozen before any call).

    ./.conda-env/bin/python -m scripts.summary_validate_v1 --build
    ./.conda-env/bin/python -m scripts.summary_validate_v1 --run
    ./.conda-env/bin/python -m scripts.summary_validate_v1 --score
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from scripts.distortion_rescore_run import boot, parse
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_summary_validation_v1'
POP = ROOT / 'rebuttal/pilots/20261115_summary_rescore/population_pairs.json'
POP_CALLS = ROOT / 'rebuttal/pilots/20261115_summary_rescore/calls.jsonl'
RULE = ROOT / 'rebuttal/pilots/prereg/Summary-strict-validation-v1.md'
PROMPT = ROOT / 'rebuttal/pilots/prereg/strict_fidelity_pair_prompt_v2.json'
SAMPLE = OUT / 'validation_sample.json'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
VALIDATION = OUT / 'validation.json'
REPORT = OUT / 'report.md'
REGISTRY = ROOT / 'rebuttal/validations/registry.json'
HAIKU = 'anthropic/claude-haiku-5.5'
OPUS = 'anthropic/claude-opus-5.5'
CAP = 0.5
MAX_TOKENS = 2500
LABEL = 'strict_fidelity_summary_qwen'
SEED = 49
QUOTA = {'distorted': 10, 'partial': 7, 'faithful': 7, 'absent': 6}
PRICE = {OPUS: (4.0 / 1e6, 20.0 / 1e6), HAIKU: (0.1 / 1e6, 0.5 / 1e6)}
EST_OUT = {OPUS: 900, HAIKU: 300}


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def render(spec, pair):
    return spec['user'].format(question='(not shown)', gold=pair['gold'][:2000],
                               entries=f"[unit 1] {pair['unit'][:2000]}")


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def call(key, model, spec, user, cap, total):
    pin, pout = PRICE[model]
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    if total + est_in * pin + EST_OUT[model] * pout > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap', 'cost_usd': 0.0}) + '\n')
        return None, total
    call_id = sha('|'.join([key, spec['system'], user, str(MAX_TOKENS)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': call_id, 'model': model,
                            'system_sha256': sha(spec['system']), 'user_sha256': sha(user),
                            'max_tokens': MAX_TOKENS, 'temperature': 0}) + '\n')
    from utility.apis.router import single_request
    req = APIRequest(system_query=spec['system'], user_query=user, model=model, max_tokens=MAX_TOKENS,
                     temperature=0, metadata={'pilot': 'summary_validation_v1', 'key': key,
                                              'openrouter_reasoning': model == OPUS})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * pin + usage.get('completion_tokens', 0) * pout
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': call_id, 'model': model,
                            'success': resp.success, 'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def pop_labels():
    """Haiku labels of the 390 population pairs (key labh/<pair_id>), from the population run."""
    out = {}
    for l in POP_CALLS.read_text().splitlines():
        if not l.strip():
            continue
        e = json.loads(l)
        if e.get('event') != 'result' or not e.get('success'):
            continue
        p = parse(e.get('content'))
        if p is not None:
            out.setdefault(e['key'].rsplit('/attempt-', 1)[0].split('labh/', 1)[1], p['fidelity'])
    return out


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = json.loads(POP.read_text())
    lab = pop_labels()
    by_label = {}
    for p in pairs:
        if p['pair_id'] in lab:
            by_label.setdefault(lab[p['pair_id']], []).append(p)
    sample = []
    for label, n in QUOTA.items():
        pool = sorted(by_label.get(label, []), key=lambda p: sha(f'{SEED}|sumv|{p["pair_id"]}'))
        for p in pool[:n]:
            row = dict(p)
            row['arm'] = f'stratum:{label}'
            row['pop_label'] = label
            sample.append(row)
    assert len(sample) == sum(QUOTA.values()), len(sample)
    assert len({p['pair_id'] for p in sample}) == len(sample)
    SAMPLE.write_text(json.dumps(sample, ensure_ascii=False))
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE), 'prompt_sha256': file_sha(PROMPT),
           'population_sha256': file_sha(POP), 'sample_sha256': file_sha(SAMPLE), 'seed': SEED,
           'quota': QUOTA, 'population_labels': dict(Counter(lab.values())),
           'stratum_pool_sizes': {k: len(by_label.get(k, [])) for k in QUOTA},
           'by_protocol': dict(Counter(p['protocol'] for p in sample)),
           'labeller_model': HAIKU, 'reference_model': OPUS, 'cap_usd': CAP,
           'selection': [p['pair_id'] for p in sample]}
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def check_frozen():
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(PROMPT) == man['prompt_sha256'], 'prompt changed'
    assert file_sha(SAMPLE) == man['sample_sha256'], 'sample changed'
    return man


def labels():
    got = {}
    if not CALLS.exists():
        return got
    for l in CALLS.read_text().splitlines():
        if not l.strip():
            continue
        e = json.loads(l)
        if e.get('event') != 'result' or not e.get('success'):
            continue
        p = parse(e.get('content'))
        if p is not None:
            got[e['key'].rsplit('/attempt-', 1)[0]] = p
    return got


def run(cap):
    check_frozen()
    spec = json.loads(PROMPT.read_text())
    sample = json.loads(SAMPLE.read_text())
    done = labels()
    total = spent()
    for p in sample:
        user = render(spec, p)
        for tag, model in (('refg', OPUS), ('labh', HAIKU)):
            key = f'{tag}/{p["pair_id"]}'
            if key in done:
                continue
            for attempt in (1, 2):
                resp, total = call(f'{key}/attempt-{attempt}', model, spec, user, cap, total)
                if resp is None:
                    print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}), flush=True)
                    return
                ok = resp.success and parse(resp.content) is not None
                if ok or attempt == 2:
                    break
            print(json.dumps({'key': key, 'ok': ok, 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(total, 6)}), flush=True)


def score():
    man = check_frozen()
    sample = json.loads(SAMPLE.read_text())
    got = labels()
    lab, cells = [], {}
    for p in sample:
        a = got.get(f'labh/{p["pair_id"]}')
        b = got.get(f'refg/{p["pair_id"]}')
        if not a or not b:
            continue
        lab.append((b['fidelity'] == 'distorted', a['fidelity'] == 'distorted', p['inst_id']))
        k = f"{b['fidelity']}->{a['fidelity']}"
        cells[k] = cells.get(k, 0) + 1
    aa, aci, ak, akci = boot(lab)
    passes = bool(aa is not None and ak is not None and aa >= 0.80 and ak >= 0.60)
    v = {'label': LABEL, 'rule_sha256': file_sha(RULE), 'prompt_sha256': file_sha(PROMPT),
         'sample_sha256': file_sha(SAMPLE), 'models': {'labeller': HAIKU, 'reference': OPUS},
         'n_pairs': len(lab), 'n_instances': len({p['inst_id'] for p in sample}),
         'distorted_vs_not': {'agreement': aa, 'agreement_ci': list(aci), 'kappa': ak, 'kappa_ci': list(akci)},
         'cells': cells, 'bars': {'agreement': 0.8, 'kappa': 0.6},
         'wide_interval': akci[0] < 0.40, 'passes': passes, 'spend_usd': round(spent(), 6),
         'bootstrap': {'draws': 2000, 'seed': 43, 'cluster': 'instance'}}
    VALIDATION.write_text(json.dumps(v, indent=1))
    if passes:
        data = json.loads(REGISTRY.read_text())
        data['validations'] = [x for x in data['validations'] if x.get('label') != LABEL]
        data['validations'].append({'label': LABEL, 'version': 'v1-stratified', 'prompt_sha256': file_sha(PROMPT),
                                    'passed': True, 'n_valid': len(lab), 'n_excluded': 0,
                                    'agreement': aa, 'agreement_ci': list(aci), 'kappa': ak,
                                    'kappa_ci': list(akci), 'record': str(VALIDATION.relative_to(ROOT)),
                                    'note': 'Qwen-235B summary-exchange population, 30 stratified pairs (10 distorted, '
                                            '7 partial, 7 faithful, 6 absent), seed 49; Haiku labeller, Opus 5.5 reference'})
        REGISTRY.write_text(json.dumps(data, indent=1))
    d = v['distorted_vs_not']
    lines = ['# Summary-exchange strict-fidelity validation, v1 (stratified 30 pairs)', '',
             '2026-11-15. Rule `Summary-strict-validation-v1.md` (sha `%s...`). Prompt `strict_fidelity_pair_prompt_v2.json`. '
             'Haiku 5.5 labeller, Opus 5.5 reference. Spend $%.6f, cap $0.50.' % (v['rule_sha256'][:8], v['spend_usd']), '',
             '| quantity | value [95% CI] |', '| --- | --- |',
             '| distorted vs not, agreement | %.3f [%.3f, %.3f] |' % (d['agreement'], *d['agreement_ci']) if d['agreement'] is not None else '| distorted vs not, agreement | n/a |',
             '| distorted vs not, kappa | %s |' % ('%.3f [%.3f, %.3f]' % (d['kappa'], *d['kappa_ci']) if d['kappa'] is not None else 'n/a'), '',
             '**%s**' % ('PASSES' if passes else 'FAILS'), '',
             'Cells (reference->labeller): ' + ', '.join(f'{k} {n}' for k, n in sorted(cells.items())), '',
             'Pairs scored: %d of %d. Bars: agreement >= .80 and kappa >= .60.' % (len(lab), len(sample)), '']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps(v, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.run:
        run(CAP)
    if a.score:
        score()
