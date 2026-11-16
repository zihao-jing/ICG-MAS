"""Restore comparison on the 92 reference-gated held-out cases.

Rule: `rebuttal/pilots/20261113_restore_source/RESTORE_REFERENCE_SUBSET_RULE.md`,
frozen before any new call. 90 cases reuse the frozen full-run answer arms;
2 reference-only cases get four new aggregation calls under a $0.25 cap.

    ./run.sh python -m scripts.restore_reference_subset --build
    ./run.sh python -m scripts.restore_reference_subset --run --cap-usd 0.25
    ./run.sh python -m scripts.restore_reference_subset --report
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.confirmer_validation import parse as parse_ref
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.pilot_llm_labeller import MODEL_OPENROUTER, PRICE_IN, PRICE_OUT
from scripts.restore_source_pilot import (
    MAX_ANSWER, _AGGREGATION_SYSTEM, boards, load_cases, score,
)
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_restore_source'
RULE = OUT / 'RESTORE_REFERENCE_SUBSET_RULE.md'
CASES = OUT / 'reference_subset_cases.json'
MANIFEST = OUT / 'reference_subset_manifest.json'
CALLS = OUT / 'reference_subset_calls.jsonl'
RESULTS = OUT / 'reference_subset_results.json'
REPORT = OUT / 'reference_subset_report.md'
REF_CALLS = OUT / 'confirmer_reference_calls.jsonl'
CONF_CASES = OUT / 'confirmer_cases.json'
FULL_RESULTS = OUT / 'results.json'
SEED = 43
CAP = 0.25


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def gate():
    conf = {r['key']: r for r in json.loads(CONF_CASES.read_text())}
    ref = {}
    for l in REF_CALLS.read_text().splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        if r.get('event') != 'result':
            continue
        v = parse_ref(r.get('content'))
        if v:
            ref[r['key'].replace('ref/', '', 1)] = v
    keys = sorted(k for k, c in conf.items()
                  if c['verbatim'] and ref.get(k) == 'yes')
    assert len(keys) == 92, len(keys)
    full = {r['key']: r for r in
            json.loads(FULL_RESULTS.read_text())['cases']}
    rows = []
    for k in keys:
        c = conf[k]
        rows.append({'key': k, 'instance_id': c['instance_id'],
                     'model': c['model'], 'benchmark': c['benchmark'],
                     'verbatim': c['verbatim'],
                     'haiku_states': c['haiku_states'],
                     'haiku_confirmed': c['haiku_confirmed'],
                     'has_arms': 'restore' in full.get(k, {})})
    return rows


def build():
    rows = gate()
    CASES.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_sha256': file_sha(RULE),
        'cases_sha256': file_sha(CASES),
        'confirmer_cases_sha256': file_sha(CONF_CASES),
        'reference_calls_sha256': file_sha(REF_CALLS),
        'full_results_sha256': file_sha(FULL_RESULTS),
        'n': len(rows), 'reused_arms': sum(r['has_arms'] for r in rows),
        'new_cases': [r['key'] for r in rows if not r['has_arms']],
        'cap_usd': CAP, 'seed': SEED,
        'model': MODEL_OPENROUTER}, indent=1))
    print(json.dumps({'n': len(rows),
                      'reused': sum(r['has_arms'] for r in rows),
                      'new': [r['key'] for r in rows if not r['has_arms']],
                      'cases_sha256': file_sha(CASES)[:12]}, indent=1))


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def call(key, system, user, cap, total):
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * PRICE_IN + MAX_ANSWER * PRICE_OUT
    if total + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key,
                                'reason': 'cap', 'cost_usd': 0.0}) + '\n')
        return None, total
    cid = sha('|'.join([key, system, user, str(MAX_ANSWER)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid,
                            'model': MODEL_OPENROUTER,
                            'system_sha256': sha(system),
                            'user_sha256': sha(user),
                            'max_tokens': MAX_ANSWER,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=system, user_query=user,
                     model=MODEL_OPENROUTER, max_tokens=MAX_ANSWER,
                     temperature=0,
                     metadata={'pilot': 'restore_reference_subset',
                               'key': key, 'openrouter_reasoning': False})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
            + usage.get('completion_tokens', 0) * PRICE_OUT)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid,
                            'success': resp.success, 'error': resp.error,
                            'content': resp.content, 'usage': usage,
                            'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def run(cap):
    man = json.loads(MANIFEST.read_text())
    assert man['recorded_before_first_call']
    assert file_sha(CASES) == man['cases_sha256'], 'cases changed'
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    rows = json.loads(CASES.read_text())
    cs = {c['key']: c for c in load_cases()}
    need = [r for r in rows if not r['has_arms']]
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in
                json.loads(RESULTS.read_text())['items']}
    total = spent()
    for r in need:
        c = cs[r['key']]
        rec = done.get(r['key']) or {'key': r['key'],
                                     'instance_id': r['instance_id'],
                                     'model': r['model'],
                                     'reference_only': True}
        for arm, restore in (('control', False), ('restore', True)):
            if arm in rec:
                continue
            resp, total = call(f"{arm}/{r['key']}", _AGGREGATION_SYSTEM,
                               boards(c, restore), cap, total)
            if resp is None:
                print(json.dumps({'stopped': 'cap',
                                  'spent': round(total, 6)}))
                break
            rec[arm] = score(resp.content, c['gold'])
            rec[arm]['cost_usd'] = None
        done[r['key']] = rec
        RESULTS.write_text(json.dumps({'items': list(done.values())},
                                      indent=1, ensure_ascii=False))
        print(json.dumps({'key': r['key'], 'arms': int('restore' in rec),
                          'spent_usd': round(spent(), 6)}), flush=True)
    RESULTS.write_text(json.dumps({'items': list(done.values())}, indent=1,
                                  ensure_ascii=False))
    print(json.dumps({'new_cases': len(need), 'spent_usd':
                      round(spent(), 8)}, indent=1))


def report():
    man = json.loads(MANIFEST.read_text())
    assert file_sha(CASES) == man['cases_sha256']
    rows = json.loads(CASES.read_text())
    full = {r['key']: r for r in
            json.loads(FULL_RESULTS.read_text())['cases']}
    new = {}
    if RESULTS.exists():
        new = {r['key']: r for r in
                json.loads(RESULTS.read_text())['items']}
    pairs = []
    for r in rows:
        arm = new.get(r['key']) or full.get(r['key'])
        assert arm and 'control' in arm and 'restore' in arm, r['key']
        pairs.append((r, arm['control']['exact'], arm['restore']['exact']))
    n = len(pairs)
    kc = sum(c for _, c, _ in pairs)
    kr = sum(x for _, _, x in pairs)
    clo, chi = cp_ci(kc, n)
    rlo, rhi = cp_ci(kr, n)
    imp = sum(1 for _, c, x in pairs if x and not c)
    wor = sum(1 for _, c, x in pairs if c and not x)
    same = n - imp - wor
    diffs = [int(x) - int(c) for _, c, x in pairs]
    rng = random.Random(SEED)
    draws = []
    for _ in range(10000):
        d = [diffs[rng.randrange(n)] for _ in range(n)]
        draws.append(sum(d))
    draws.sort()
    dlo, dhi = (draws[int(.025 * len(draws))],
                draws[int(.975 * len(draws)) - 1])
    # separate the 90 reused and 2 reference-only cases
    ref_only = {r['key'] for r in rows if not r['has_arms']}
    ro = [(r, c, x) for r, c, x in pairs if r['key'] in ref_only]
    spend = spent()
    lines = [
        '# Restore comparison on the reference-gated subset\n',
        f"Rule `RESTORE_REFERENCE_SUBSET_RULE.md` (sha256 "
        f"`{file_sha(RULE)[:12]}`), frozen before any new call. Subset: the "
        f"**{n} held-out cases** where the Gemini 3.6 Flash reference says "
        f"`source_states_fact = yes` and the source sentence is verbatim "
        f"(92/144 from `confirmer_validation_report.md`). {n - len(ro)} cases "
        f"reuse the frozen full-run answer arms; {len(ro)} are reference-only "
        f"and were answered here (4 calls). Spend **${spend:.6f}**, cap "
        f"${CAP:.2f}. Stage: relay checkpoint (source restoration) and final "
        f"aggregation (the two arms).\n",
        f"Control exact **{kc}/{n} = {100 * kc / n:.1f}%** "
        f"({100 * clo:.1f}-{100 * chi:.1f}); restore exact **{kr}/{n} = "
        f"{100 * kr / n:.1f}%** ({100 * rlo:.1f}-{100 * rhi:.1f}); paired "
        f"difference **+{kr - kc}** ({imp} improved, {wor} worse, {same} "
        f"same), case-bootstrap 95% CI [{dlo}, {dhi}].\n",
        f"Reference-only cases ({len(ro)}): control "
        f"{sum(c for _, c, _ in ro)}/{len(ro)}, restore "
        f"{sum(x for _, _, x in ro)}/{len(ro)}.\n",
        'Beside the 132 figure: the confirmer gate gives 2/132 control and '
        '20/132 restore (15.2%, 9.5-22.4). The reference gate is a stricter '
        'positive set, so the two rates are not the same denominator; both '
        'stay on record.\n',
        '## Reading\n',
        ('The restore effect **holds** on the reference-gated subset: restore '
         'beats control by the same direction and a non-zero paired count.'
         if kr > kc else
         'The restore effect **does not hold** on the reference-gated subset: '
         'restore does not beat control here.'),
        'The reference is an LLM, not author ground truth; this subset is '
        'reference-gated, not author-validated. The 132 remains '
        'confirmer-gated, and the 90 reused arms come from the frozen full '
        'run (no new cost). The 2 reference-only cases enter on the '
        'reference call alone and are listed above.',
        '',
        '## Cases\n',
        '| key | instance | model | source | control | restore |',
        '| --- | --- | --- | --- | --- | --- |']
    for r, c, x in pairs:
        src = 'new' if r['key'] in ref_only else 'reused'
        lines.append(f"| `{r['key']}` | {r['instance_id']} | {r['model']} | "
                     f"{src} | {'exact' if c else 'wrong'} | "
                     f"{'exact' if x else 'wrong'} |")
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'n': n, 'control': kc, 'restore': kr,
                      'improved': imp, 'worse': wor, 'same': same,
                      'diff': kr - kc, 'diff_ci': [dlo, dhi],
                      'ref_only': len(ro), 'spent': round(spend, 8)},
                     indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    if a.build:
        build()
    if a.run:
        run(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()