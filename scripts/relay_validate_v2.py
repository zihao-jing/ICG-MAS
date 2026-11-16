"""Relay strict-fidelity validation v2 (clarified prompt, seed 48). Cap $0.5.

    ./run.sh python -m scripts.relay_validate_v2 --build
    ./run.sh python -m scripts.relay_validate_v2 --run
    ./run.sh python -m scripts.relay_validate_v2 --score
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.relay_validate_run import boot, cp, parse
from scripts.answer_equiv import last_object  # noqa: F401  (parser dependency chain)
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_relay_validation_v2'
SRC = ROOT / 'rebuttal/pilots/20261115_relay_rescore/population_pairs.json'
RULE = ROOT / 'rebuttal/pilots/prereg/Relay-strict-fidelity-validation-v2.md'
PROMPT = ROOT / 'rebuttal/pilots/prereg/strict_fidelity_pair_prompt_v2.json'
SAMPLE = OUT / 'validation_sample.json'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
VALIDATION = OUT / 'validation.json'
REPORT = OUT / 'report.md'
REGISTRY = ROOT / 'rebuttal/validations/registry.json'
HAIKU = 'anthropic/claude-haiku-5.5'
OPUS = 'anthropic/claude-opus-5.5'
PRICE = {OPUS: (4.0 / 1e6, 20.0 / 1e6), HAIKU: (0.1 / 1e6, 0.5 / 1e6)}
EST_OUT = {OPUS: 900, HAIKU: 300}
CAP = 0.5
MAX_TOKENS = 2500
LABEL = 'strict_fidelity_relay_qwen'
SEED = 48
PER = 10


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build():
    pairs = json.loads(SRC.read_text())
    sample = []
    for prot in ('random_relay', 'score_ranked_relay', 'redundancy_aware_relay'):
        pool = sorted([p for p in pairs if p['protocol'] == prot],
                      key=lambda p: sha(f'{SEED}|relayval|{p["pair_id"]}'))
        sample += pool[:PER]
    assert len(sample) == len({p['pair_id'] for p in sample})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'validation_sample.json').write_text(json.dumps(sample, ensure_ascii=False))
    v1 = json.loads((ROOT / 'rebuttal/pilots/20261115_relay_validation/validation_sample.json').read_text())
    v1_ids = {p['pair_id'] for p in v1}
    overlap = [p['pair_id'] for p in sample if p['pair_id'] in v1_ids]
    man = {
        'recorded_before_any_call': True,
        'rule_sha256': file_sha(RULE), 'prompt_sha256': file_sha(PROMPT),
        'source_population_sha256': file_sha(SRC),
        'sample_sha256': file_sha(SAMPLE),
        'seed': SEED, 'per_protocol': PER,
        'pairs': len(sample), 'by_protocol': dict(Counter(p['protocol'] for p in sample)),
        'v1_overlap_pairs': len(overlap), 'v1_overlap_ids': overlap,
        'labeller_model': HAIKU, 'reference_model': OPUS,
        'cap_usd': CAP,
        'selection': [p['pair_id'] for p in sample],
    }
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def check_frozen():
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(PROMPT) == man['prompt_sha256'], 'prompt changed'
    assert file_sha(SAMPLE) == man['sample_sha256'], 'sample changed'
    return man


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def render(spec, pair):
    return spec['user'].format(question='(not shown)', gold=pair['gold'][:2000],
                               entries=f"[unit 1] {pair['unit'][:2000]}")


def call(key, model, spec, user, cap, total):
    import math
    pin, pout = PRICE[model]
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    if total + est_in * pin + EST_OUT[model] * pout > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                'cost_usd': 0.0}) + '\n')
        return None, total
    call_id = sha('|'.join([key, spec['system'], user, str(MAX_TOKENS)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': call_id, 'model': model,
                            'system_sha256': sha(spec['system']), 'user_sha256': sha(user),
                            'max_tokens': MAX_TOKENS, 'temperature': 0}) + '\n')
    from utility.apis.router import single_request
    req = APIRequest(system_query=spec['system'], user_query=user, model=model,
                     max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'relay_validation_v2', 'key': key,
                               'openrouter_reasoning': model == OPUS})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * pin + usage.get('completion_tokens', 0) * pout
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
                k = e['key']
                out.add(k.rsplit('/attempt-', 1)[0] if '/attempt-' in k else k)
    return out


def run(cap):
    check_frozen()
    spec = json.loads(PROMPT.read_text())
    pairs = json.loads(SAMPLE.read_text())
    done = done_keys()
    total = spent()
    for p in pairs:
        user = render(spec, p)
        for tag, model in (('refg', OPUS), ('labh', HAIKU)):
            key = f'{tag}/{p["pair_id"]}'
            if key in done:
                continue
            for attempt in (1, 2):
                resp, total = call(f'{key}/attempt-{attempt}', model, spec, user, cap, total)
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
            key = e['key']
            if '/attempt-' in key:
                key = key.rsplit('/attempt-', 1)[0]
            got[key] = p
    return got


def score():
    man = check_frozen()
    pairs = json.loads(SAMPLE.read_text())
    got = labels()
    lab, cells, agree3 = [], {}, 0
    for p in pairs:
        a = got.get(f'labh/{p["pair_id"]}')
        b = got.get(f'refg/{p["pair_id"]}')
        if not a or not b:
            continue
        lab.append((b['fidelity'] == 'distorted', a['fidelity'] == 'distorted', p['inst_id']))
        k = f"{b['fidelity']}->{a['fidelity']}"
        cells[k] = cells.get(k, 0) + 1
        agree3 += a['fidelity'] == b['fidelity']
    aa, aci, ak, akci = boot(lab)
    a3 = agree3 / len(lab) if lab else None
    passes = bool(aa is not None and ak is not None and aa >= 0.80 and ak >= 0.60)
    v = {'label': LABEL, 'version': 'v2', 'rule_sha256': file_sha(RULE), 'prompt_sha256': file_sha(PROMPT),
         'sample_sha256': file_sha(SAMPLE),
         'models': {'labeller': HAIKU, 'reference': OPUS},
         'n_pairs': len(lab), 'n_instances': len({p['inst_id'] for p in pairs}),
         'distorted_vs_not': {'agreement': aa, 'agreement_ci': list(aci),
                              'kappa': ak, 'kappa_ci': list(akci)},
         'three_class_agreement': a3, 'cells': cells,
         'bars': {'agreement': 0.8, 'kappa': 0.6},
         'wide_interval': akci[0] < 0.40, 'passes': passes,
         'spend_usd': round(spent(), 6),
         'bootstrap': {'draws': 2000, 'seed': 43, 'cluster': 'instance'}}
    VALIDATION.write_text(json.dumps(v, indent=1))
    if passes:
        data = json.loads(REGISTRY.read_text())
        data['validations'] = [x for x in data['validations']
                               if not (x.get('label') == LABEL
                                       and x.get('prompt_sha256') == file_sha(PROMPT))]
        data['validations'].append({
            'label': LABEL, 'version': 'v2', 'prompt_sha256': file_sha(PROMPT),
            'passed': True, 'n_valid': len(lab), 'n_excluded': 0,
            'agreement': aa, 'agreement_ci': list(aci), 'kappa': ak, 'kappa_ci': list(akci),
            'record': str(VALIDATION.relative_to(ROOT)),
            'note': 'Qwen-235B relay population, 30 pairs, 10 per protocol, seed 48; distorted vs not; '
                    'Haiku labeller, Opus 5.5 reference; clarified prompt v2'})
        REGISTRY.write_text(json.dumps(data, indent=1))
    write_report(v, cells, man)
    print(json.dumps(v, indent=1))


def write_report(v, cells, man):
    d = v['distorted_vs_not']
    n_ref_dist = sum(n for k, n in cells.items() if k.startswith('distorted->'))
    n_lab_dist = sum(n for k, n in cells.items() if k.endswith('->distorted'))
    lines = [
        '# Relay strict-fidelity validation v2 (clarified prompt)',
        '',
        '2026-11-15. Rule `Relay-strict-fidelity-validation-v2.md` (sha `%s…`), prompt '
        '`strict_fidelity_pair_prompt_v2.json` (sha `%s…`). 30 relay pairs (10 per protocol, seed 48, '
        '%d shared with the v1 draw), Haiku 5.5 labeller, Opus 5.5 reference. Spend **$%.6f**, cap $0.5.'
        % (v['rule_sha256'][:8], v['prompt_sha256'][:8], man['v1_overlap_pairs'], v['spend_usd']),
        '',
        '## Result',
        '',
        '| quantity | value [95% CI] |',
        '| --- | --- |',
        '| distorted vs not, agreement | %.3f [%.3f, %.3f] |' % (d['agreement'], *d['agreement_ci']),
        '| distorted vs not, kappa | %.3f [%.3f, %.3f] |' % (d['kappa'], *d['kappa_ci']),
        '| three-class agreement | %.3f |' % v['three_class_agreement'],
        '',
        'Reference calls %d of 30 distorted; labeller calls %d.' % (n_ref_dist, n_lab_dist),
        '',
        'Bars: agreement >= .80 and kappa >= .60. **%s**. Wide-interval rule: %s.'
        % ('PASSES' if v['passes'] else 'FAILS', 'applies' if v['wide_interval'] else 'does not apply'),
        '',
        '| reference \\ labeller | faithful | partial | distorted | absent |',
        '| --- | ---: | ---: | ---: | ---: |',
    ]
    for ref in ('faithful', 'partial', 'distorted', 'absent'):
        lines.append('| ' + ref + ' | ' + ' | '.join(
            str(cells.get(f'{ref}->{x}', 0))
            for x in ('faithful', 'partial', 'distorted', 'absent')) + ' |')
    lines += ['', '## Registration', '',
              'Registered as `strict_fidelity_relay_qwen` v2 (prompt v2). The relay strict rates may be '
              'quoted under this prompt.' if v['passes'] else
              'Not registered. The relay rates stay unvalidated and the text may not quote them.']
    lines += ['', '## Ledger', 'Spend $%.6f.' % v['spend_usd']]
    REPORT.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    if a.build:
        build()
    if a.run:
        run(a.cap_usd)
    if a.score:
        score()