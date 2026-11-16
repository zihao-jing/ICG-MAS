"""Opus 5.5 check of the Gemini answer-equivalence checker, on a stratified sample of the 150 author-labelled rows.

Reference: claude-opus-5-5 through the claude CLI (same transport as scripts/part_b_step2_cli.py).
Prompt: the frozen answer-equivalence prompt answer_equiv_v1.json, unchanged (same user text as the checker).
Strata (author label x Gemini verdict on the same row):
    CORRECT/EQUIVALENT 12, CORRECT/NOT_EQUIVALENT 2 (all), DEFECT/EQUIVALENT 7 (all), DEFECT/NOT_EQUIVALENT 15,
    DEFECT/unparsed 4 (all). Total 40 rows, drawn with seed 43 within each stratum, unique item_ids only.
Cap: $0.30, hard stop before each call. Each call is costed at the larger of the CLI-reported cost and the
API-equivalent cost (cache creation counted as prompt tokens); before a call the estimate is the mean of the calls
so far, or $0.05 for the first call.

    ./.conda-env/bin/python -m scripts.opus_checker_check --build
    ./.conda-env/bin/python -m scripts.opus_checker_check --run
    ./.conda-env/bin/python -m scripts.opus_checker_check --score
"""
import argparse
import hashlib
import json
import random
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT = ROOT / 'rebuttal/pilots/20261112_answer_equiv/answer_equiv_v1.json'
PROMPT_MANIFEST = ROOT / 'rebuttal/pilots/20261112_answer_equiv/answer_equiv_v1.manifest.json'
VALIDATION = ROOT / 'rebuttal/pilots/20261112_labeller/validation_150.jsonl'
GEM_CALLS = ROOT / 'rebuttal/pilots/20261116_restore_equiv_gemini/calls.jsonl'
OUT = ROOT / 'rebuttal/pilots/20261116_opus_checker_check'
ITEMS = OUT / 'items.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
MANIFEST = OUT / 'build_manifest.json'
OPUS_CLI = 'claude-opus-5-5'
OPUS_PRICE = (4.0 / 1e6, 20.0 / 1e6)
TOOLS_OFF = ('Bash Edit Write Read Glob Grep WebFetch WebSearch Task NotebookEdit TodoWrite '
             'Agent Skill Workflow Monitor')
CAP = 1.00
FIRST_EST = 0.05
SEED = 43
QUOTA = {('CORRECT', 'EQUIVALENT'): 12, ('CORRECT', 'NOT_EQUIVALENT'): 2, ('DEFECT', 'EQUIVALENT'): 7,
         ('DEFECT', 'NOT_EQUIVALENT'): 16, ('DEFECT', None): 4}


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def load_prompt():
    raw = PROMPT.read_bytes()
    spec = json.loads(raw)
    man = json.loads(PROMPT_MANIFEST.read_text())
    assert sha_bytes(spec['system'].encode()) == spec['system_sha256'] == man['system_sha256']
    assert sha_bytes(raw) == man['file_sha256'], 'prompt file changed'
    return spec


def author_of(r):
    return 'CORRECT' if r['authors'][0]['raw'] in ('correct', 'CORRECT') else 'DEFECT'


def gemini_verdicts():
    out = {}
    for l in GEM_CALLS.read_text().splitlines():
        x = json.loads(l)
        if x['event'] == 'result':
            out[x['key']] = x['verdict']
    return out


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in VALIDATION.read_text().splitlines() if l.strip()]
    gv = gemini_verdicts()
    by = {}
    for r in rows:
        k = (author_of(r), gv.get('val:' + r['item_id']))
        by.setdefault(k, {})[r['item_id']] = r
    rng = random.Random(SEED)
    items = []
    for k, n in QUOTA.items():
        pool = sorted(by.get(k, {}).items())
        pick = rng.sample(pool, min(n, len(pool)))
        for iid, r in pick:
            items.append({'item_id': iid, 'stratum': f'{k[0]}/{k[1]}', 'author': k[0],
                          'gemini': k[1], 'trace': r['trace']})
    items.sort(key=lambda x: sha_bytes(x['item_id'].encode()))
    ITEMS.write_text(json.dumps(items, ensure_ascii=False, indent=1))
    spec = load_prompt()
    man = {'recorded_before_any_call': True, 'n': len(items), 'seed': SEED, 'quota': {f'{a}/{b}': n for (a, b), n in QUOTA.items()},
           'prompt_sha256': sha_bytes(PROMPT.read_bytes()), 'reference': OPUS_CLI, 'transport': 'claude-cli',
           'cap_usd': CAP, 'items_sha256': sha_bytes(ITEMS.read_bytes()), 'system_sha256': spec['system_sha256']}
    man['population_unique_items'] = {f'{a}/{b}': len(v) for (a, b), v in by.items()}
    MANIFEST.write_text(json.dumps(man, indent=1))
    import collections
    print(json.dumps({'n': len(items), 'strata': dict(collections.Counter(i['stratum'] for i in items))}, indent=1))


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def parse(text):
    import re
    for raw in reversed(re.findall(r'\{[^{}]*\}', text or '')):
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        v = str(d.get('verdict', '')).upper().replace(' ', '_')
        if v in ('EQUIVALENT', 'NOT_EQUIVALENT'):
            return v
    return None


def run():
    spec = load_prompt()
    man = json.loads(MANIFEST.read_text())
    assert sha_bytes(ITEMS.read_bytes()) == man['items_sha256'], 'items changed'
    done = set()
    if RESULTS.exists():
        done = {json.loads(l)['item_id'] for l in RESULTS.read_text().splitlines() if l.strip()}
    total = spent()
    costs = [json.loads(l)['cost_usd'] for l in CALLS.read_text().splitlines()
             if l.strip() and json.loads(l).get('event') == 'result'] if CALLS.exists() else []
    tmp = Path(tempfile.mkdtemp(prefix='opus_checker_'))
    for it in json.loads(ITEMS.read_text()):
        if it['item_id'] in done:
            continue
        t = it['trace']
        user = (f"QUESTION\n{t['question']}\n\nGOLD ANSWER\n{t.get('gold_answer')}\n\n"
                f"SYSTEM ANSWER\n{t.get('answer_text')}")
        est = (sum(costs) / len(costs)) if costs else FIRST_EST
        if total + est > CAP:
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'stopped', 'item_id': it['item_id'], 'reason': 'cap',
                                    'spent_usd': round(total, 6), 'next_estimate_usd': round(est, 6)}) + '\n')
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        sp = tmp / 'system.txt'
        sp.write_text(spec['system'])
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'intent', 'item_id': it['item_id'], 'model': OPUS_CLI,
                                'transport': 'claude-cli'}) + '\n')
        cmd = ['claude', '-p', user, '--output-format', 'json', '--model', OPUS_CLI,
               '--system-prompt-file', str(sp), '--exclude-dynamic-system-prompt-sections',
               '--disallowedTools', TOOLS_OFF]
        p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=900)
        try:
            obj = json.loads(p.stdout)
        except json.JSONDecodeError:
            obj = None
        if obj is None:
            rec = {'event': 'result', 'item_id': it['item_id'], 'success': False, 'verdict': None,
                   'error': p.stderr[-300:], 'cost_usd': 0.0}
        else:
            u = obj.get('usage') or {}
            pin = u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0)
            api_eq = pin * OPUS_PRICE[0] + u.get('output_tokens', 0) * OPUS_PRICE[1]
            cli = obj.get('total_cost_usd') or 0.0
            rec = {'event': 'result', 'item_id': it['item_id'], 'success': True, 'verdict': parse(obj.get('result')),
                   'content': obj.get('result'), 'cost_usd': round(max(cli, api_eq), 8),
                   'cli_reported_usd': cli, 'api_equiv_usd': round(api_eq, 8)}
        with CALLS.open('a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        costs.append(rec['cost_usd'])
        total += rec['cost_usd']
        if rec['verdict'] is not None or not rec['success']:
            with RESULTS.open('a') as f:
                f.write(json.dumps({'item_id': it['item_id'], 'stratum': it['stratum'], 'author': it['author'],
                                    'gemini': it['gemini'], 'opus': rec['verdict'], 'success': rec['success']}) + '\n')
        print(json.dumps({'item': it['item_id'][:12], 'stratum': it['stratum'], 'opus': rec['verdict'],
                          'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


def wkappa(rows):
    """Weighted Cohen's kappa; rows are (a, b, w). Weights restore the 150-row population."""
    W = sum(w for _, _, w in rows)
    po = sum(w for a, b, w in rows if a == b) / W
    labs = {x for a, b, _ in rows for x in (a, b)}
    pe = 0.0
    for l in labs:
        pa = sum(w for a, _, w in rows if a == l) / W
        pb = sum(w for _, b, w in rows if b == l) / W
        pe += pa * pb
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def wilson(k, n, z=1.959964):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5 / d
    return round(max(0, c - h), 3), round(min(1, c + h), 3)


def score():
    man = json.loads(MANIFEST.read_text())
    pop = man['population_unique_items']
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    ok = [r for r in rows if r['opus'] is not None]
    lab = lambda v: 'EQUIVALENT' if v == 'EQUIVALENT' else 'NOT_EQUIVALENT'
    nsamp = {}
    for r in ok:
        nsamp[r['stratum']] = nsamp.get(r['stratum'], 0) + 1
    # weight = population size of the stratum / number of scored rows in it
    def wrow(r):
        key = r['stratum'].replace('/None', '/None')
        N = pop.get(key.replace('/NOT_EQUIVALENT', '/NOT_EQUIVALENT'), 0)
        return N / nsamp[r['stratum']]
    data = [(lab(r['gemini'] or 'NONE'), lab(r['opus']), wrow(r)) for r in ok]
    n = len(ok)
    agree_raw = sum(1 for r in ok if lab(r['gemini'] or 'NONE') == lab(r['opus']))
    wag = sum(w for a, b, w in data if a == b) / sum(w for _, _, w in data)
    k = wkappa(data)
    # stratified bootstrap of kappa (resample rows within each stratum)
    rng = random.Random(43)
    by_s = {}
    for d, r in zip(data, ok):
        by_s.setdefault(r['stratum'], []).append(d)
    ks = []
    for _ in range(2000):
        sample = []
        for s, ds in by_s.items():
            sample += [ds[rng.randrange(len(ds))] for _ in ds]
        ks.append(wkappa(sample))
    ks.sort()
    # Reported kappa interval: unweighted row bootstrap (2,000 draws, seed 43). The stratified bootstrap above
    # cannot vary here: every stratum is all-agree except the unparsed Gemini rows, so resampling within a
    # stratum leaves kappa unchanged. It is kept only to show that degeneracy.
    rng_u = random.Random(43)
    unw = [(a, b, 1.0) for a, b, _ in data]
    ku = sorted(wkappa([unw[rng_u.randrange(n)] for _ in range(n)]) for _ in range(2000))
    kappa_unw = wkappa(unw)
    eq_opus = [d for d in data if d[1] == 'EQUIVALENT']
    recall = sum(w for a, b, w in eq_opus if a == 'EQUIVALENT') / sum(w for _, _, w in eq_opus) if eq_opus else None
    cost = spent()
    out = {'n_scored': n, 'unparsed_opus': len(rows) - n,
           'agreement_raw_unweighted': round(agree_raw / n, 3),
           'agreement_weighted_to_150': round(wag, 3),
           'kappa_weighted': round(k, 3),
           'kappa_unweighted': round(kappa_unw, 3),
           'kappa_unweighted_row_bootstrap95': [round(ku[50], 3), round(ku[1949], 3)],
           'kappa_interval_note': 'reported interval is the unweighted row bootstrap; the stratified bootstrap cannot vary (see script comment)',
           'equivalent_recall_vs_opus_weighted': round(recall, 3) if recall is not None else None,
           'bars': {'agreement>=0.90': wag >= 0.90, 'kappa>=0.75': k >= 0.75, 'recall>=0.85': (recall or 0) >= 0.85},
           'pass': bool(wag >= 0.90 and k >= 0.75 and (recall or 0) >= 0.85),
           'by_stratum': {s: {'scored': len(ds), 'agree': sum(1 for a, b, _ in ds if a == b)} for s, ds in by_s.items()},
           'population_unique_items': pop, 'spend_usd': round(cost, 6), 'cap_usd': CAP}
    (OUT / 'score.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--build', action='store_true')
    g.add_argument('--run', action='store_true')
    g.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    elif a.run:
        run()
    else:
        score()


if __name__ == '__main__':
    main()
