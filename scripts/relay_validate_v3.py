"""Relay strict-fidelity validation v3 (distortion-enriched sample). Cap $0.5.

    ./run.sh python -m scripts.relay_validate_v3 --build
    ./run.sh python -m scripts.relay_validate_v3 --run
    ./run.sh python -m scripts.relay_validate_v3 --score
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.relay_validate_run import boot, cp, parse
from scripts.answer_equiv import last_object
from utility.apis.base import APIRequest
import math

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_relay_validation_v3_enriched'
SRC = ROOT / 'rebuttal/pilots/20261115_relay_rescore/population_pairs.json'
RESCORE = ROOT / 'rebuttal/pilots/20261115_relay_rescore/calls.jsonl'
RULE = ROOT / 'rebuttal/pilots/prereg/Relay-strict-fidelity-validation-v3-enriched.md'
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
LABEL = 'strict_fidelity_relay_qwen'
SEED = 49
N_ENRICH = 15
N_CONTROL = 15


PRICE = {OPUS: (4.0 / 1e6, 20.0 / 1e6), HAIKU: (0.1 / 1e6, 0.5 / 1e6)}
EST_OUT = {OPUS: 900, HAIKU: 300}


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
                     metadata={'pilot': 'relay_validation_v3', 'key': key,
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
            k = e['key']
            got[k.rsplit('/attempt-', 1)[0] if '/attempt-' in k else k] = p
    return got


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def haiku_labels():
    out = {}
    for line in RESCORE.read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get('event') != 'result' or not e.get('success'):
            continue
        pid = e['key'].split('/')[1].rsplit('/attempt-', 1)[0]
        p = last_object(e.get('content') or '')
        if isinstance(p, dict) and p.get('facts'):
            out[pid] = p['facts'][0]['fidelity']
    return out


def pools():
    pairs = json.loads(SRC.read_text())
    haiku = haiku_labels()
    old = {p['pair_id']: p['old_label'] for p in pairs}
    v1 = {p['pair_id'] for p in json.loads(
        (ROOT / 'rebuttal/pilots/20261115_relay_validation/validation_sample.json').read_text())}
    v2 = {p['pair_id'] for p in json.loads(
        (ROOT / 'rebuttal/pilots/20261115_relay_validation_v2/validation_sample.json').read_text())}
    flagged = {p for p in haiku if haiku[p] == 'distorted'} | {p for p in old if old[p] == 'DISTORTED'}
    flagged -= (v1 | v2)
    controls = {p['pair_id'] for p in pairs
                if p['pair_id'] not in flagged and p['pair_id'] not in (v1 | v2)
                and old.get(p['pair_id']) != 'NO_MATCH'}
    return pairs, sorted(flagged), sorted(controls), haiku, old


def draw(pool, n):
    return sorted(pool, key=lambda p: sha(f'{SEED}|enal|{p}'))[:n]


def build():
    pairs, flagged, controls, haiku, old = pools()
    sel_e, sel_c = draw(flagged, N_ENRICH), draw(controls, N_CONTROL)
    by_id = {p['pair_id']: p for p in pairs}
    sample = []
    for kind, ids in (('enriched', sel_e), ('control', sel_c)):
        for pid in ids:
            row = dict(by_id[pid])
            row['arm'] = kind
            row['prior_flags'] = sorted({f'old:{old[pid]}'} if old.get(pid) == 'DISTORTED' else set()
                                        | ({f'haiku:{haiku[pid]}'} if haiku.get(pid) == 'distorted'
                                           else set()))
            sample.append(row)
    assert len(sample) == len({p['pair_id'] for p in sample})
    OUT.mkdir(parents=True, exist_ok=True)
    SAMPLE.write_text(json.dumps(sample, ensure_ascii=False))
    man = {
        'recorded_before_any_call': True,
        'rule_sha256': file_sha(RULE), 'prompt_sha256': file_sha(PROMPT),
        'source_population_sha256': file_sha(SRC),
        'sample_sha256': file_sha(SAMPLE),
        'seed': SEED, 'enriched': len(sel_e), 'controls': len(sel_c),
        'enrichment_pool': len(flagged), 'control_pool': len(controls),
        'by_protocol': dict(Counter(p['protocol'] for p in sample)),
        'by_arm': dict(Counter(p['arm'] for p in sample)),
        'prior_flag_counts': dict(Counter(
            ('both' if len(p['prior_flags']) == 2 else
             ('old_judge' if p['prior_flags'] and p['prior_flags'][0].startswith('old')
              else ('haiku' if p['prior_flags'] else 'none'))) for p in sample)),
        'labeller_model': HAIKU, 'reference_model': OPUS,
        'cap_usd': CAP,
        'selection': [f"{p['arm']}:{p['pair_id']}" for p in sample],
        'excluded_sources': ['v1 design sample', 'v2 validation sample'],
    }
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def check_frozen():
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(PROMPT) == man['prompt_sha256'], 'prompt changed'
    assert file_sha(SAMPLE) == man['sample_sha256'], 'sample changed'
    return man


def run(cap):
    check_frozen()
    spec = json.loads(PROMPT.read_text())
    sample = json.loads(SAMPLE.read_text())
    done = done_keys()
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
                    print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
                    return
                ok = resp.success and parse(resp.content) is not None
                if ok or attempt == 2:
                    break
            print(json.dumps({'key': key, 'ok': ok, 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(total, 6)}))


def score():
    man = check_frozen()
    sample = json.loads(SAMPLE.read_text())
    got = labels()
    lab, cells, agree3, arms = [], {}, 0, {}
    for p in sample:
        a = got.get(f'labh/{p["pair_id"]}')
        b = got.get(f'refg/{p["pair_id"]}')
        if not a or not b:
            continue
        lab.append((b['fidelity'] == 'distorted', a['fidelity'] == 'distorted', p['inst_id']))
        cells[f"{b['fidelity']}->{a['fidelity']}"] = cells.get(f"{b['fidelity']}->{a['fidelity']}", 0) + 1
        agree3 += a['fidelity'] == b['fidelity']
        arms.setdefault(p['arm'], Counter())[(b['fidelity'] == 'distorted', a['fidelity'] == 'distorted')] += 1
    aa, aci, ak, akci = boot(lab)
    passes = bool(aa is not None and ak is not None and aa >= 0.80 and ak >= 0.60)
    v = {'label': LABEL, 'version': 'v3-enriched', 'rule_sha256': file_sha(RULE),
         'prompt_sha256': file_sha(PROMPT), 'sample_sha256': file_sha(SAMPLE),
         'models': {'labeller': HAIKU, 'reference': OPUS},
         'n_pairs': len(lab), 'n_instances': len({p['inst_id'] for p in sample}),
         'enrichment': {'designed': f'{N_ENRICH} flagged + {N_CONTROL} controls',
                        'reference_distorted': sum(1 for r, _, _ in lab if r),
                        'labeller_distorted': sum(1 for _, l, _ in lab if l),
                        'by_arm': {k: {'ref_distorted': sum(vv for (r, _), vv in c.items() if r),
                                       'n': sum(c.values()), 'cells': {f'{r}->{l}': n
                                                                       for (r, l), n in c.items()}}
                                   for k, c in arms.items()}},
         'distorted_vs_not': {'agreement': aa, 'agreement_ci': list(aci),
                              'kappa': ak, 'kappa_ci': list(akci)},
         'three_class_agreement': agree3 / len(lab) if lab else None,
         'cells': cells, 'bars': {'agreement': 0.8, 'kappa': 0.6},
         'wide_interval': akci[0] < 0.40, 'passes': passes, 'spend_usd': round(spent(), 6),
         'bootstrap': {'draws': 2000, 'seed': 43, 'cluster': 'instance'}}
    VALIDATION.write_text(json.dumps(v, indent=1))
    if passes:
        data = json.loads(REGISTRY.read_text())
        data['validations'] = [x for x in data['validations']
                               if not (x.get('label') == LABEL
                                       and x.get('prompt_sha256') == file_sha(PROMPT))]
        data['validations'].append({
            'label': LABEL, 'version': 'v3-enriched', 'prompt_sha256': file_sha(PROMPT),
            'passed': True, 'n_valid': len(lab), 'n_excluded': 0,
            'agreement': aa, 'agreement_ci': list(aci), 'kappa': ak, 'kappa_ci': list(akci),
            'record': str(VALIDATION.relative_to(ROOT)),
            'note': 'Qwen-235B relay population, 30 pairs (15 distortion-flagged + 15 controls), seed 49; '
                    'distorted vs not; Haiku labeller, Opus 5.5 reference; prompt v2 clarified; '
                    'enriched sample, rates not derived from it'})
        REGISTRY.write_text(json.dumps(data, indent=1))
    write_report(v, man, cells)
    print(json.dumps(v, indent=1))


def write_report(v, man, cells):
    d = v['distorted_vs_not']
    lines = [
        '# Relay strict-fidelity validation v3: distortion-enriched sample',
        '',
        '2026-11-15. Rule `Relay-strict-fidelity-validation-v3-enriched.md` (sha `%s...`), prompt '
        '`strict_fidelity_pair_prompt_v2.json` (sha `%s...`). 30 relay pairs: **%d pairs flagged as distortion '
        'by a prior label** and **%d controls**, seed %d, excluding the v1 design sample and the v2 sample. '
        'Haiku 5.5 labeller, Opus 5.5 reference. Spend **$%.6f**, cap $0.5.'
        % (v['rule_sha256'][:8], v['prompt_sha256'][:8], man['enriched'], man['controls'], man['seed'],
           v['spend_usd']),
        '',
        '## Result',
        '',
        '| quantity | value [95% CI] |',
        '| --- | --- |',
        '| distorted vs not, agreement | %.3f [%.3f, %.3f] |' % (d['agreement'], *d['agreement_ci']),
        '| distorted vs not, kappa | %.3f [%.3f, %.3f] |' % (d['kappa'], *d['kappa_ci']),
        '| three-class agreement | %.3f |' % v['three_class_agreement'],
        '',
        'Reference calls %d of %d distorted; labeller calls %d. Bars: agreement >= .80 and kappa >= .60.'
        % (v['enrichment']['reference_distorted'], v['n_pairs'],
           v['enrichment']['labeller_distorted']),
        '**%s**%s'
        % ('PASSES' if v['passes'] else 'FAILS',
           '. Wide-interval rule applies.' if v['wide_interval'] else ' Wide-interval rule does not apply.'),
        '',
        '| reference \\ labeller | faithful | partial | distorted | absent |',
        '| --- | ---: | ---: | ---: | ---: |',
    ]
    for ref in ('faithful', 'partial', 'distorted', 'absent'):
        lines.append('| ' + ref + ' | ' + ' | '.join(
            str(cells.get(f'{ref}->{x}', 0))
            for x in ('faithful', 'partial', 'distorted', 'absent')) + ' |')
    lines += ['', '## Enrichment', '',
              'The prior flags came from the old Qwen-235B judge (`DISTORTED`, 3 pairs) and the Haiku step-9 '
              'relabel (`distorted`, 29 pairs); %d usable pairs remained after excluding the v1 and v2 samples. '
              'The draw is 15 of those and 15 controls, so distortion is over-represented by construction. '
              '**Agreement and kappa here describe the label on this enriched sample; any distortion rate must '
              'come from a population run, not from this sample.**' % man['enrichment_pool'],
              '', '## Registration', '',
              'Registered as `strict_fidelity_relay_qwen` v3-enriched (prompt v2).'
              if v['passes'] else
              'Not registered. The relay strict rates stay unvalidated and the text may not quote them.']
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