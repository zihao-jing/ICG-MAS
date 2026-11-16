"""9f: re-label the four-model pair population with prompt v2 and rescore rates. Cap $0.5.

    ./run.sh python -m scripts.distortion_v2_recheck --build
    ./run.sh python -m scripts.distortion_v2_recheck --run
    ./run.sh python -m scripts.distortion_v2_recheck --score
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.distortion_rescore_run import cp, parse, render, boot
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'rebuttal/pilots/20261115_distortion_rescore'
OUT = ROOT / 'rebuttal/pilots/20261115_distortion_v2_recheck'
RULE = ROOT / 'rebuttal/pilots/prereg/Strict-fidelity-v2-recheck.md'
PROMPT = ROOT / 'rebuttal/pilots/prereg/strict_fidelity_pair_prompt_v2.json'
PAIRS = SRC / 'population_pairs.json'
VAL = SRC / 'validation_sample.json'
OPUS_CALLS = SRC / 'calls.jsonl'
MANIFEST = OUT / 'build_manifest.json'
POP = OUT / 'population_pairs.json'
CALLS = OUT / 'calls.jsonl'
RATES = OUT / 'rates.json'
VALIDATION = OUT / 'validation.json'
REPORT = OUT / 'report.md'
REGISTRY = ROOT / 'rebuttal/validations/registry.json'
HAIKU = 'anthropic/claude-haiku-5.5'
OPUS = 'anthropic/claude-opus-5.5'
PRICE_IN, PRICE_OUT = 0.1 / 1e6, 0.5 / 1e6
EST_OUT = 300
CAP = 0.5
MAX_TOKENS = 2500
LABEL = 'strict_fidelity_new_models_pairs_v2'
SEED = 43


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    POP.write_text(PAIRS.read_text())
    man = {'recorded_before_any_call': True,
           'rule_sha256': file_sha(RULE), 'prompt_sha256': file_sha(PROMPT),
           'population_sha256': file_sha(POP),
           'validation_sha256': file_sha(VAL),
           'opus_labels_source': str(OPUS_CALLS.relative_to(ROOT)),
           'opus_labels_sha256': file_sha(OPUS_CALLS),
           'pairs': len(json.loads(POP.read_text())),
           'validation_pairs': len(json.loads(VAL.read_text())),
           'labeller_model': HAIKU, 'reference_model': OPUS,
           'cap_usd': CAP}
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def check_frozen():
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(PROMPT) == man['prompt_sha256'], 'prompt changed'
    assert file_sha(POP) == man['population_sha256'], 'population changed'
    return man


def call(key, spec, user, cap):
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    total = spent()
    if total + est_in * PRICE_IN + EST_OUT * PRICE_OUT > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                'cost_usd': 0.0}) + '\n')
        return None
    call_id = sha('|'.join([key, spec['system'], user, str(MAX_TOKENS)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': call_id, 'model': HAIKU,
                            'system_sha256': sha(spec['system']), 'user_sha256': sha(user),
                            'max_tokens': MAX_TOKENS, 'temperature': 0}) + '\n')
    from utility.apis.router import single_request
    req = APIRequest(system_query=spec['system'], user_query=user, model=HAIKU,
                     max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'distortion_v2_recheck', 'key': key})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * PRICE_IN + usage.get('completion_tokens', 0) * PRICE_OUT
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': call_id, 'model': HAIKU,
                            'success': resp.success, 'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp


LOCK = None
TOTAL = {'v': 0.0}


def call_par(key, spec, user, cap):
    """Thread-safe cap-carrying call; returns the response or None at the cap."""
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    with LOCK:
        if TOTAL['v'] + est_in * PRICE_IN + EST_OUT * PRICE_OUT > cap:
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                    'cost_usd': 0.0}) + '\n')
            return None
    call_id = sha('|'.join([key, spec['system'], user, str(MAX_TOKENS)]))
    with LOCK, CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': call_id, 'model': HAIKU,
                            'system_sha256': sha(spec['system']), 'user_sha256': sha(user),
                            'max_tokens': MAX_TOKENS, 'temperature': 0}) + '\n')
    from utility.apis.router import single_request
    req = APIRequest(system_query=spec['system'], user_query=user, model=HAIKU,
                     max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'distortion_v2_recheck', 'key': key})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * PRICE_IN + usage.get('completion_tokens', 0) * PRICE_OUT
    with LOCK:
        TOTAL['v'] += cost
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'result', 'key': key, 'call_id': call_id, 'model': HAIKU,
                                'success': resp.success, 'error': resp.error, 'content': resp.content,
                                'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp


def run_par(cap, workers=8, only=None, fresh=False):
    """Parallel relabel: resume from calls.jsonl, cap on actual spend under a lock."""
    global LOCK
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from threading import Lock
    check_frozen()
    LOCK = Lock()
    spec = json.loads(PROMPT.read_text())
    pairs = json.loads(POP.read_text())
    done = done_keys()
    if only:
        only_set = set(json.loads(Path(only).read_text()))
        pairs = [p for p in pairs if p['pair_id'] in only_set]
        done = {k for k in done}
    todo = [p for p in pairs if f'labh/{p["pair_id"]}' not in done]
    TOTAL['v'] = 0.0 if fresh else spent()
    print(json.dumps({'todo': len(todo), 'done': len(done),
                      'spent': round(TOTAL['v'], 6)}), flush=True)

    def one(p):
        key = f'labh/{p["pair_id"]}'
        user = render(spec, p)
        for attempt in (1, 2):
            resp = call_par(f'{key}/attempt-{attempt}', spec, user, cap)
            if resp is None:
                return None
            if resp.success and parse(resp.content) is not None:
                return True
        return False

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(one, p): p for p in todo}
        for i, f in enumerate(as_completed(futs), 1):
            f.result()
            if i % 100 == 0 or i == len(todo):
                print(json.dumps({'done': i, 'of': len(todo),
                                  'spent': round(spent(), 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


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
    pairs = json.loads(POP.read_text())
    done = done_keys()
    for i, p in enumerate(pairs, 1):
        key = f'labh/{p["pair_id"]}'
        if key in done:
            continue
        user = render(spec, p)
        for attempt in (1, 2):
            resp = call(f'{key}/attempt-{attempt}', spec, user, cap)
            if resp is None:
                print(json.dumps({'stopped': 'cap', 'spent': round(spent(), 6)}))
                return
            ok = resp.success and parse(resp.content) is not None
            if ok or attempt == 2:
                break
        if i % 100 == 0:
            print(json.dumps({'done': i, 'of': len(pairs), 'spent': round(spent(), 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


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
            k = e['key']
            got[k.rsplit('/attempt-', 1)[0] if '/attempt-' in k else k] = p
    return got


def opus_labels():
    out = {}
    for l in OPUS_CALLS.read_text().splitlines():
        if not l.strip():
            continue
        e = json.loads(l)
        if e.get('event') != 'result' or not e.get('success') or not e['key'].startswith('refg/'):
            continue
        p = parse(e.get('content'))
        if p is not None:
            out[e['key'].split('/')[1].rsplit('/attempt-', 1)[0]] = p
    return out


def score():
    man = check_frozen()
    pairs = json.loads(POP.read_text())
    got = labels()
    val_ids = [p['pair_id'] for p in json.loads(VAL.read_text())]
    ref = opus_labels()
    lab, cells, agree3 = [], {}, 0
    for pid in val_ids:
        a, b = got.get(f'labh/{pid}'), ref.get(pid)
        if not a or not b:
            continue
        inst = next(p['instance_id'] for p in pairs if p['pair_id'] == pid)
        lab.append((b['fidelity'] == 'distorted', a['fidelity'] == 'distorted', inst))
        cells[f"{b['fidelity']}->{a['fidelity']}"] = cells.get(f"{b['fidelity']}->{a['fidelity']}", 0) + 1
        agree3 += a['fidelity'] == b['fidelity']
    aa, aci, ak, akci = boot(lab)
    passes = bool(aa is not None and ak is not None and aa >= 0.80 and ak >= 0.60)
    v = {'label': LABEL, 'prompt_sha256': file_sha(PROMPT), 'rule_sha256': file_sha(RULE),
         'models': {'labeller': HAIKU, 'reference': OPUS},
         'n_pairs': len(lab), 'distorted_vs_not': {'agreement': aa, 'agreement_ci': list(aci),
                                                   'kappa': ak, 'kappa_ci': list(akci)},
         'three_class_agreement': agree3 / len(lab) if lab else None, 'cells': cells,
         'bars': {'agreement': 0.8, 'kappa': 0.6}, 'wide_interval': akci[0] < 0.40,
         'passes': passes, 'spend_usd': round(spent(), 6)}
    VALIDATION.write_text(json.dumps(v, indent=1))

    rates = {}
    for p in pairs:
        m = rates.setdefault(p['model'], {'eligible': 0, 'absent': 0, 'covered': 0, 'faithful': 0,
                                          'partial': 0, 'distorted': 0})
        lab_ = got.get(f'labh/{p["pair_id"]}')
        if not lab_:
            continue
        m['eligible'] += 1
        m[lab_['fidelity']] += 1
        if lab_['fidelity'] != 'absent':
            m['covered'] += 1
    for m in rates.values():
        m['strict'] = m['distorted'] / m['covered'] if m['covered'] else None
        m['strict_ci'] = list(cp(m['distorted'], m['covered'])) if m['covered'] else None
        m['broad'] = (m['distorted'] + m['partial']) / m['covered'] if m['covered'] else None
        m['broad_ci'] = list(cp(m['distorted'] + m['partial'], m['covered'])) if m['covered'] else None
    RATES.write_text(json.dumps({'validation': v, 'by_model': rates}, indent=1))

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
            'note': 'four-model board pairs, 120 reference pairs, prompt v2, Haiku labeller against the '
                    'existing Opus 5.5 reference labels; distorted vs not'})
        REGISTRY.write_text(json.dumps(data, indent=1))
    write_report(v, rates, man)
    print(json.dumps({'validation': v, 'by_model': rates}, indent=1))


def write_report(v, rates, man):
    d = v['distorted_vs_not']
    lines = [
        '# Four-model strict fidelity under the clarified prompt (9f)',
        '',
        '2026-11-15. Rule `Strict-fidelity-v2-recheck.md` (sha `%s...`), prompt '
        '`strict_fidelity_pair_prompt_v2.json` (sha `%s...`). %d board pairs re-labelled with Haiku 5.5; '
        'reference labels are the existing Opus 5.5 labels on the 120-pair validation set (no new Opus calls). '
        'Spend **$%.6f**, cap $0.5.'
        % (v['rule_sha256'][:8], v['prompt_sha256'][:8], man['pairs'], v['spend_usd']),
        '',
        '## Validation of the v2 prompt on this population',
        '',
        '| quantity | value [95% CI] |', '| --- | --- |',
        '| distorted vs not, agreement | %.3f [%.3f, %.3f] |' % (d['agreement'], *d['agreement_ci']),
        '| distorted vs not, kappa | %.3f [%.3f, %.3f] |' % (d['kappa'], *d['kappa_ci']),
        '| three-class agreement | %.3f |' % v['three_class_agreement'],
        '',
        'Bars agreement >= .80, kappa >= .60: **%s**.' % ('PASSES' if v['passes'] else 'FAILS'),
        '',
        '| reference \\ labeller | faithful | partial | distorted | absent |',
        '| --- | ---: | ---: | ---: | ---: |',
    ]
    for r in ('faithful', 'partial', 'distorted', 'absent'):
        lines.append('| ' + r + ' | ' + ' | '.join(
            str(v['cells'].get(f'{r}->{x}', 0)) for x in ('faithful', 'partial', 'distorted', 'absent'))
            + ' |')
    lines += ['', '## Rates under the v2 prompt', '',
              '| model | covered | faithful | partial | distorted | absent | strict [95% CI] | broad [95% CI] |',
              '| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |']
    for model in ('geminifl', 'gpt4omini', 'deepseekr1_32b', 'gemma31b'):
        m = rates.get(model)
        if not m:
            continue
        lines.append('| %s | %d | %d | %d | %d | %d | %.1f%% [%.1f, %.1f] | %.1f%% [%.1f, %.1f] |'
                     % (model, m['covered'], m['faithful'], m['partial'], m['distorted'], m['absent'],
                        100 * m['strict'], 100 * m['strict_ci'][0], 100 * m['strict_ci'][1],
                        100 * m['broad'], 100 * m['broad_ci'][0], 100 * m['broad_ci'][1]))
    lines += ['', 'Strict = distorted / covered; broad = (distorted + partial) / covered.',
              '', '## Registration', '',
              'Registered as `strict_fidelity_new_models_pairs_v2` (prompt v2).' if v['passes'] else
              'Not registered. The four-model column stays on the v1 prompt; these v2 rates are reported as '
              'measured only.', '', '## Ledger', 'Spend $%.6f.' % v['spend_usd']]
    REPORT.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--run-par', action='store_true')
    ap.add_argument('--pairs', default=None, help='JSON list of pair_ids to run')
    ap.add_argument('--fresh-cap', action='store_true', help='cap applies to this invocation only')
    ap.add_argument('--score', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    x = ap.parse_args()
    if x.build:
        build()
    if x.run:
        run(x.cap_usd)
    if x.run_par:
        run_par(x.cap_usd, only=x.pairs, fresh=x.fresh_cap)
    if x.score:
        score()