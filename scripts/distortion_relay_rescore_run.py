"""Step 9b: re-score the Qwen-235B relay strict distortion with the validated label.

Same label as step 9 (`strict_fidelity_new_models_pairs`: prompt
`strict_fidelity_pair_prompt_v1.json`, Haiku 5.5, validated .992 / kappa .937 against Opus 5.5).
945 relay pairs from `results/distortion_audit_relay/distortion_results.json`; cap $1.0.

    ./run.sh python -m scripts.distortion_relay_rescore_run --build
    ./run.sh python -m scripts.distortion_relay_rescore_run --run
    ./run.sh python -m scripts.distortion_relay_rescore_run --score
"""
import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from scripts.answer_equiv import last_object
from scripts.distortion_rescore_run import parse as parse_label
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_relay_rescore'
PROMPT = ROOT / 'rebuttal/pilots/prereg/strict_fidelity_pair_prompt_v1.json'
OLD = ROOT / 'results/distortion_audit_relay/distortion_results.json'
PAIRS = OUT / 'population_pairs.json'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RATES = OUT / 'rates.json'
REPORT = OUT / 'report.md'
REGISTRY = ROOT / 'rebuttal/validations/registry.json'
HAIKU = 'anthropic/claude-haiku-5.5'
PRICE = (0.1 / 1e6, 0.5 / 1e6)
EST_OUT = 400
CAP = 1.0
MAX_TOKENS = 2500
LABEL = 'strict_fidelity_new_models_pairs'
WORKERS = 8
LOCK = Lock()


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check_frozen():
    man = json.loads(MANIFEST.read_text())
    assert file_sha(PROMPT) == man['prompt_sha256'], 'prompt changed'
    assert file_sha(PAIRS) == man['population_sha256'], 'population changed'
    reg = json.loads(REGISTRY.read_text())['validations']
    rec = [x for x in reg if x['label'] == LABEL and x['prompt_sha256'] == file_sha(PROMPT)]
    assert rec and rec[0]['passed'], 'label not registered for this prompt'
    return man, rec[0]


def build():
    from src.eval.silo_bench_loader import load_silobench
    old = json.loads(OLD.read_text())
    insts = {}
    for n in (5, 10):
        for i in load_silobench(n_agents_filter=n):
            insts[(f'n{n}', i['id'])] = i
    pairs = []
    for r in old['records']:
        inst = insts[(r['tier'], r['inst_id'])]
        gold = None
        for ac in inst['agent_configs']:
            if ac['agent_id'] == r['agent_id']:
                gold = str(ac['input_shard'])
                break
        assert gold is not None
        pairs.append({
            'pair_id': sha(f"relay|{r['protocol']}|{r['tier']}|{r['inst_id']}|{r['agent_id']}")[:16],
            'protocol': r['protocol'], 'tier': r['tier'], 'inst_id': r['inst_id'],
            'agent_id': r['agent_id'], 'coverage_score': r['coverage_score'],
            'old_label': r['label'], 'from_judge': r['from_judge'],
            'gold': gold, 'unit': r['best_unit'] or '',
        })
    assert len(pairs) == len({p['pair_id'] for p in pairs})
    OUT.mkdir(parents=True, exist_ok=True)
    PAIRS.write_text(json.dumps(pairs, ensure_ascii=False))
    man = {
        'recorded_before_any_call': True,
        'label': LABEL, 'prompt_sha256': file_sha(PROMPT),
        'old_source_sha256': file_sha(OLD), 'old_judge_model': old['judge_model'],
        'population_sha256': file_sha(PAIRS),
        'pairs': len(pairs), 'pairs_by_protocol': dict(Counter(p['protocol'] for p in pairs)),
        'old_label_counts': dict(Counter(p['old_label'] for p in pairs)),
        'labeller_model': HAIKU, 'cap_usd': CAP,
        'cap_estimator': f'output allowance {EST_OUT} tokens per call; hard stop on actual spend',
        'rendering': "question '(not shown)', gold[:2000], one unit[:2000] - same renderer as step 9",
    }
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def render(spec, pair):
    return spec['user'].format(question='(not shown)', gold=pair['gold'][:2000],
                               entries=f"[unit 1] {pair['unit'][:2000]}")


TOTAL = {'v': 0.0}


def call(key, spec, user, cap):
    pin, pout = PRICE
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    with LOCK:
        if TOTAL['v'] + est_in * pin + EST_OUT * pout > cap:
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                    'cost_usd': 0.0}) + '\n')
            return None
    call_id = sha('|'.join([key, spec['system'], user, str(MAX_TOKENS)]))
    with LOCK, CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': call_id,
                            'model': HAIKU, 'system_sha256': sha(spec['system']),
                            'user_sha256': sha(user), 'max_tokens': MAX_TOKENS,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=spec['system'], user_query=user, model=HAIKU,
                     max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'relay_rescore', 'key': key})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * pin + usage.get('completion_tokens', 0) * pout
    with LOCK:
        TOTAL['v'] += cost
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'result', 'key': key, 'call_id': call_id, 'model': HAIKU,
                                'success': resp.success, 'error': resp.error,
                                'content': resp.content, 'usage': usage,
                                'cost_usd': round(cost, 8)}) + '\n')
    return resp, cost


def done_keys():
    out = {}
    if CALLS.exists():
        for l in CALLS.read_text().splitlines():
            if not l.strip():
                continue
            e = json.loads(l)
            if e.get('event') == 'result' and e.get('success') and parse_label(e.get('content')):
                out[e['key']] = parse_label(e['content'])
    return out


def run(cap):
    man, _ = check_frozen()
    spec = json.loads(PROMPT.read_text())
    pairs = json.loads(PAIRS.read_text())
    done = done_keys()
    TOTAL['v'] = spent()
    total = TOTAL['v']
    todo = [p for p in pairs if f"labh/{p['pair_id']}" not in done]
    print(json.dumps({'todo': len(todo), 'already': len(done),
                      'spent': round(total, 6)}), flush=True)

    def one(p):
        key = f"labh/{p['pair_id']}"
        user = render(spec, p)
        for attempt in (1, 2):
            r = call(key, spec, user, cap)
            if r is None:
                return {'key': key, 'ok': False, 'stop': 'cap'}
            resp, cost = r
            ok = resp.success and parse_label(resp.content) is not None
            if ok or attempt == 2:
                return {'key': key, 'ok': ok, 'cost': cost}
        return {'key': key, 'ok': False}

    stopped = False
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(one, p): p for p in todo}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            if r.get('stop'):
                stopped = True
            if i % 25 == 0 or i == len(todo):
                print(json.dumps({'done': i, 'of': len(todo),
                                  'spent': round(spent(), 6)}), flush=True)
    print(json.dumps({'stopped': stopped, 'spent': round(spent(), 6)}))


def cp(k, n):
    if n == 0:
        return 0.0, 1.0

    def cdf(p, upto):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(upto + 1))

    def solve(fn, target):
        lo, hi = 0.0, 1.0
        for _ in range(90):
            mid = (lo + hi) / 2
            if fn(mid) > target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    lo = 0.0 if k == 0 else solve(lambda p: cdf(p, k - 1), 0.975)
    hi = 1.0 if k == n else solve(lambda p: cdf(p, k), 0.025)
    return lo, hi


def score():
    man, reg = check_frozen()
    pairs = json.loads(PAIRS.read_text())
    got = done_keys()
    rows = []
    for p in pairs:
        lab = got.get(f"labh/{p['pair_id']}")
        if not lab:
            continue
        rows.append((p, lab['fidelity']))
    by = {}
    for prot in ('random_relay', 'score_ranked_relay', 'redundancy_aware_relay', 'pooled'):
        sel = [x for x in rows if prot == 'pooled' or x[0]['protocol'] == prot]
        old_cov = [p for p, f in sel if p['old_label'] != 'NO_MATCH']
        old_dis = [p for p in old_cov if p['old_label'] == 'DISTORTED']
        old_broad = [p for p in old_cov if p['old_label'] in ('DISTORTED', 'PARTIAL')]
        cov = [(p, f) for p, f in sel if f != 'absent']
        dis = [p for p, f in cov if f == 'distorted']
        par = [p for p, f in cov if f == 'partial']
        by[prot] = {
            'pairs': len(sel), 'old_covered': len(old_cov),
            'old_strict': len(old_dis) / len(old_cov) if old_cov else None,
            'old_strict_ci': list(cp(len(old_dis), len(old_cov))) if old_cov else None,
            'old_broad': len(old_broad) / len(old_cov) if old_cov else None,
            'old_broad_ci': list(cp(len(old_broad), len(old_cov))) if old_cov else None,
            'old_counts': dict(Counter(p['old_label'] for p, f in sel)),
            'new_covered': len(cov), 'new_absent': len(sel) - len(cov),
            'new_faithful': sum(1 for _, f in cov if f == 'faithful'),
            'new_partial': len(par), 'new_distorted': len(dis),
            'new_strict': len(dis) / len(cov) if cov else None,
            'new_strict_ci': list(cp(len(dis), len(cov))) if cov else None,
            'new_broad': (len(dis) + len(par)) / len(cov) if cov else None,
            'new_broad_ci': list(cp(len(dis) + len(par), len(cov))) if cov else None,
            'new_strict_eligible': len(dis) / len(sel) if sel else None,
            'new_strict_eligible_ci': list(cp(len(dis), len(sel))) if sel else None,
            'cross': {f'{o}->{f}': c for (o, f), c in Counter(
                (p['old_label'], f) for p, f in sel).items()},
        }
    out = {'label': LABEL, 'prompt_sha256': file_sha(PROMPT),
           'validation': {k: reg.get(k) for k in ('agreement', 'kappa', 'n_valid')},
           'rows_scored': len(rows), 'by_protocol': by,
           'spend_usd': round(spent(), 8), 'cap_usd': CAP}
    RATES.write_text(json.dumps(out, indent=1))
    write_report(out)
    print(json.dumps(out, indent=1))


def write_report(out):
    b = out['by_protocol']
    def pct(x):
        return '—' if x is None else f'{100 * x:.1f}'
    def iv(v):
        return '' if not v else f'[{100 * v[0]:.1f}, {100 * v[1]:.1f}]'
    lines = [
        '# Qwen-235B relay strict distortion under the validated label',
        '',
        '2026-11-15. Same label and prompt as step 9 (`strict_fidelity_new_models_pairs`, prompt '
        '`strict_fidelity_pair_prompt_v1.json`, Haiku 5.5, validated .992 / kappa .937 against '
        'Opus 5.5 on 120 pairs). 945 relay pairs from `results/distortion_audit_relay/`; '
        f"spend **${out['spend_usd']:.6f}**, cap $1.0.",
        '',
        '| protocol | pairs | old covered | old strict | old broad | new covered | absent | new strict | new broad |',
        '| --- | ---: | ---: | --- | --- | ---: | ---: | --- | --- |',
    ]
    for prot in ('random_relay', 'score_ranked_relay', 'redundancy_aware_relay', 'pooled'):
        x = b[prot]
        lines.append(
            f"| {prot} | {x['pairs']} | {x['old_covered']} | {pct(x['old_strict'])}% "
            f"{iv(x['old_strict_ci'])} | {pct(x['old_broad'])}% {iv(x['old_broad_ci'])} | "
            f"{x['new_covered']} | {x['new_absent']} | **{pct(x['new_strict'])}% "
            f"{iv(x['new_strict_ci'])}** | {pct(x['new_broad'])}% {iv(x['new_broad_ci'])} |")
    lines += [
        '',
        'Strict = distorted / covered; broad = (distorted + partial) / covered; 95% Clopper-Pearson.',
        'Old covered = pairs the Qwen judge did not mark NO_MATCH (it marks NO_MATCH on any unit with '
        'no gold number, so a unit carrying one value counts as covered). New covered = pairs the '
        'label does not call absent (the full shard claim is checked). The new label calls absent on '
        f"{b['pooled']['new_absent']} of 945 pairs against {b['pooled']['pairs'] - b['pooled']['old_covered']} "
        'old NO_MATCH, so the denominators differ; the rate over all eligible pairs is reported '
        'below for that reason.',
        '',
        'Fixed-denominator strict (distorted / all pairs): ' + ', '.join(
            f"{prot} {pct(b[prot]['new_strict_eligible'])}% {iv(b[prot]['new_strict_eligible_ci'])}"
            for prot in ('random_relay', 'score_ranked_relay', 'redundancy_aware_relay', 'pooled')),
        '',
        '## Which figure the text will use',
        '',
        'The validated label\'s rates (new strict). The Qwen-235B judge figures stay on record as '
        'unvalidated and are reported beside them.',
        '',
        '## Cross-tab, pooled (old label → new label)',
        '',
        '| old \\ new | faithful | partial | distorted | absent |',
        '| --- | ---: | ---: | ---: | ---: |',
    ]
    c = b['pooled']['cross']
    for old in ('EXACT', 'PARAPHRASE', 'PARTIAL', 'DISTORTED', 'NO_MATCH'):
        vals = [c.get(f'{old}->{fid}', 0)
                for fid in ('faithful', 'partial', 'distorted', 'absent')]
        lines.append(f'| {old} | ' + ' | '.join(str(v) for v in vals) + ' |')
    lines += [
        '',
        'The old judge saw only the shard\'s key numbers and a 600-character unit; the validated '
        'label reads the full shard and the full unit. That difference is part of the comparison.',
        '',
        f"Of the {sum(v for k, v in b['pooled']['cross'].items() if k.startswith('DISTORTED->'))} "
        f"pairs the old judge called DISTORTED, {b['pooled']['cross'].get('DISTORTED->faithful', 0)} "
        f"are faithful under the validated label; {b['pooled']['cross'].get('EXACT->distorted', 0)} "
        'units it called EXACT are distorted.',
        '',
        '## Ledger',
        f"Spend this step ${out['spend_usd']:.6f}.",
    ]
    REPORT.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    for f in ('build', 'run', 'score'):
        ap.add_argument('--' + f, action='store_true', dest=f)
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    if a.build:
        build()
    if a.run:
        run(a.cap_usd)
    if a.score:
        score()