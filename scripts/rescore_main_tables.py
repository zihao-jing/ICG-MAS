"""Re-score the paper's main-table cells with the validated v2 labeller (pilot).

Pilot scope and rules are frozen in
`rebuttal/pilots/20261112_rescore/SCORING_RULE.md`: Qwen-235B, both benchmarks,
the four protocols that have a trace package, 608 traces, $2.00 cap.

The lexical cells and the paper's original cells stay on record; the labeller
cells are written beside them. Every call is logged (intent before dispatch,
result after). No paper file is read or changed.

    ./run.sh python -m scripts.rescore_main_tables --plan
    ./run.sh python -m scripts.rescore_main_tables --run --cap-usd 2.00
    ./run.sh python -m scripts.rescore_main_tables --report
"""
import argparse
import hashlib
import json
import math
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from utility.apis.base import APIRequest
from scripts.pilot_llm_labeller import (
    MODEL_OPENROUTER, PRICE_IN, PRICE_OUT, cohen_kappa, parse, render,
)
from scripts.repilot_llm_labeller_v2 import load_prompt
from src.audit.critical_fact_validation import build_trace_packages
from src.eval.evaluate import answer_f1
from src.eval.silo_bench_loader import silobench_exact_match

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261112_rescore'
CASES = OUT / 'cases.jsonl'
CALLS = OUT / 'calls.jsonl'
REPORT = OUT / 'rescore_report.md'
SUMMARY = OUT / 'rescore_summary.json'
PRICES = ROOT / 'rebuttal/pilots/20261108_preflight/pricing.json'
CAP = 2.0
MAX_TOKENS = 2000
RETRY_TOKENS = 3000
WORKERS = 8
SEED = 42
PROTOCOLS = ['summary_exchange', 'random_relay', 'score_ranked_relay',
             'redundancy_aware_relay']
MODEL_RUNS = {'qwen235b': {
    'SB': [('results/run_qwen235b_n5', 5), ('results/run_qwen235b_n10', 10)],
    'MQ': [('results/run_qwen235b_musique', None)],
}}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def original_acc(run, protocol):
    r = json.loads((ROOT / run / 'results.json').read_text())
    return float(r['table'][protocol]['acc']), int(r['table'][protocol]['n'])


def build_rows():
    spec = load_prompt()
    rows = []
    for model, parts in MODEL_RUNS.items():
        for bench, runs in parts.items():
            for run, n_agents in runs:
                for protocol in PROTOCOLS:
                    pk = build_trace_packages(
                        dataset='silobench' if bench == 'SB' else 'musique',
                        run_dir=ROOT / run, protocol=protocol,
                        source_id=f'rescore_{model}_{bench}', n_agents=n_agents)
                    for p in pk:
                        pred = str(p['baseline_prediction'])
                        gold = p['gold_answer']
                        if bench == 'SB':
                            lex = float(silobench_exact_match(pred, {'answer': gold}))
                            f1 = lex
                        else:
                            f1 = float(answer_f1(pred, {'answer': gold}))
                            lex = float(f1 >= 1.0)
                        trace = dict(p, answer_text=pred)
                        rows.append({
                            'key': '|'.join([model, bench, run, protocol, p['instance_id']]),
                            'model': model, 'benchmark': bench, 'run': run,
                            'protocol': protocol, 'instance_id': p['instance_id'],
                            'question': p['question'], 'gold_answer': gold,
                            'answer_text': pred, 'lexical_correct': lex, 'f1': round(f1, 6),
                            'trace': trace})
    assert len(rows) == 608, len(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    with CASES.open('w') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    chars = [len(render(r)) for r in rows]
    by_cell = {}
    for r in rows:
        by_cell.setdefault((r['benchmark'], r['protocol']), 0)
        by_cell[(r['benchmark'], r['protocol'])] += 1
    print(json.dumps({
        'traces': len(rows), 'cells': {f'{b}|{p}': n for (b, p) in by_cell for n in [by_cell[(b, p)]]},
        'mean_chars': round(sum(chars) / len(chars)),
        'p90_chars': sorted(chars)[int(.9 * len(chars))],
        'est_input_usd': round(sum(math.ceil(c / 4) for c in chars) * PRICE_IN, 4),
        'est_usd_with_output': round(sum(math.ceil(c / 4) for c in chars) * PRICE_IN
                                     + len(rows) * 200 * PRICE_OUT, 4),
        'cases_sha256': sha(CASES), 'prompt_version': spec['version']}, indent=1))


def render_case(row):
    return render({'trace': row['trace']})


def one(row, spec, max_tokens):
    from utility.apis.openrouter_api import single_request
    user = render_case(row)
    man = json.loads((ROOT / 'rebuttal/pilots/20261112_labeller/'
                      'labeller_prompt_v2.manifest.json').read_text())
    meta = {'case': row['key'], 'prompt_version': spec['version'],
            'system_sha256': spec['system_sha256'], 'file_sha256': man['file_sha256'],
            'openrouter_reasoning': False}
    req = APIRequest(system_query=spec['system'], user_query=user,
                     model=MODEL_OPENROUTER, max_tokens=max_tokens,
                     temperature=0, metadata=meta)
    resp = single_request(req)
    usage = resp.usage or {}
    est_in = math.ceil(len(user) / 4) + math.ceil(len(spec['system']) / 4)
    cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
            + usage.get('completion_tokens', 0) * PRICE_OUT)
    parsed = parse(resp.content or '')
    return {'event': 'result', 'case': row['key'], 'benchmark': row['benchmark'],
            'protocol': row['protocol'], 'run': row['run'],
            'instance_id': row['instance_id'],
            'prompt_version': spec['version'], 'system_sha256': spec['system_sha256'],
            'file_sha256': man['file_sha256'], 'max_tokens': max_tokens,
            'success': resp.success, 'error': resp.error, 'raw': resp.content,
            'parsed': parsed, 'verdict': (parsed or {}).get('verdict'),
            'usage': usage, 'cost_usd': round(cost, 8)}


def execute(cap, max_tokens=MAX_TOKENS):
    spec = load_prompt()
    rows = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]
    OUT.mkdir(parents=True, exist_ok=True)
    spent = 0.0
    latest = {}
    if CALLS.exists():
        for line in CALLS.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec.get('event') == 'result':
                    latest[rec['case']] = rec
                    spent += rec.get('cost_usd') or 0
    done = {k for k, v in latest.items() if v.get('verdict')}
    todo = [r for r in rows if r['key'] not in done]
    print(json.dumps({'cases': len(rows), 'already_logged': len(done),
                      'todo': len(todo), 'spent_usd': round(spent, 6),
                      'cap_usd': cap}), flush=True)
    by_key = {r['key']: r for r in rows}
    retry = []

    def budget_ok(chunk, mt):
        reserve = sum((math.ceil(len(render_case(r)) / 4)
                       + math.ceil(len(spec['system']) / 4)) * PRICE_IN * 1.5
                      + mt * PRICE_OUT for r in chunk)
        return spent + reserve <= cap, reserve

    def wave(chunk, mt):
        nonlocal spent
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(one, r, spec, mt): r for r in chunk}
            for fut in as_completed(futs):
                r = futs[fut]
                try:
                    rec = fut.result()
                except Exception as exc:
                    rec = {'event': 'result', 'case': r['key'], 'benchmark': r['benchmark'],
                           'protocol': r['protocol'], 'run': r['run'],
                           'instance_id': r['instance_id'], 'prompt_version': spec['version'],
                           'system_sha256': spec['system_sha256'],
                           'max_tokens': mt, 'success': False,
                           'error': type(exc).__name__ + ': ' + str(exc),
                           'raw': None, 'parsed': None, 'verdict': None,
                           'usage': None, 'cost_usd': 0.0}
                spent += rec.get('cost_usd') or 0
                latest[r['key']] = rec
                with CALLS.open('a') as log:
                    log.write(json.dumps(rec, ensure_ascii=False) + '\n')
                print(json.dumps({'logged': len(latest), 'of': len(rows),
                                  'usd': round(spent, 4)}), flush=True)
                if not rec.get('verdict'):
                    retry.append(r)

    with CALLS.open('a') as log:
        for i in range(0, len(todo), WORKERS):
            chunk = todo[i:i + WORKERS]
            ok, reserve = budget_ok(chunk, max_tokens)
            if not ok:
                print(json.dumps({'stopped': 'cap', 'spent': round(spent, 6),
                                  'remaining': len(todo) - i}), flush=True)
                break
            for r in chunk:
                log.write(json.dumps({'event': 'intent', 'case': r['key'],
                                      'prompt_version': spec['version'],
                                      'system_sha256': spec['system_sha256'],
                                      'max_tokens': max_tokens},
                                     ensure_ascii=False) + '\n')
            log.flush()
            wave(chunk, max_tokens)
    # one retry pass at a larger output budget, for traces with no verdict
    for i in range(0, len(retry), WORKERS):
        chunk = retry[i:i + WORKERS]
        ok, _ = budget_ok(chunk, RETRY_TOKENS)
        if not ok:
            print(json.dumps({'stopped': 'cap_retry', 'spent': round(spent, 6),
                              'remaining': len(retry) - i}), flush=True)
            break
        with CALLS.open('a') as log:
            for r in chunk:
                log.write(json.dumps({'event': 'intent', 'retry': True, 'case': r['key'],
                                      'prompt_version': spec['version'],
                                      'system_sha256': spec['system_sha256'],
                                      'max_tokens': RETRY_TOKENS},
                                     ensure_ascii=False) + '\n')
        wave(chunk, RETRY_TOKENS)
    print(json.dumps({'spent_usd': round(spent, 6), 'cap_usd': cap,
                      'with_verdict': sum(1 for r in rows
                                          if (latest.get(r['key']) or {}).get('verdict'))}),
          flush=True)


def cluster_bootstrap(items, draws=2000):
    """items: list of (cluster, labeller, lexical)."""
    rng = random.Random(SEED)
    groups = {}
    for cluster, a, b in items:
        groups.setdefault(cluster, []).append((a, b))
    keys = list(groups)
    ags, kaps = [], []
    for _ in range(draws):
        picked = [groups[rng.choice(keys)] for _ in keys]
        pairs = [p for g in picked for p in g]
        ags.append(sum(x == y for x, y in pairs) / len(pairs))
        kaps.append(cohen_kappa(pairs))
    kaps = [k for k in kaps if not math.isnan(k)]
    q = lambda xs, p: sorted(xs)[int(p * (len(xs) - 1))]
    return {'agree': (q(ags, .025), q(ags, .975)),
            'kappa': (q(kaps, .025), q(kaps, .975))}


def report():
    spec = load_prompt()
    rows = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]
    calls = [json.loads(l) for l in CALLS.read_text().splitlines() if l.strip()]
    for c in calls:
        if c.get('event') == 'result':
            assert c['system_sha256'] == spec['system_sha256']
    latest = {}
    for c in calls:
        if c.get('event') == 'result':
            latest[c['case']] = c
    spent = sum(c.get('cost_usd') or 0 for c in calls if c.get('event') == 'result')
    ev = []
    for r in rows:
        c = latest.get(r['key'])
        v = (c or {}).get('verdict')
        ev.append(dict(r, verdict=v, rationale=((c or {}).get('parsed') or {}).get('rationale', ''),
                       labeller_cost=(c or {}).get('cost_usd', 0.0),
                       retried=(c or {}).get('max_tokens') == RETRY_TOKENS))
    scored = [e for e in ev if e['verdict']]
    failed = [e for e in ev if not e['verdict']]
    cells = {}
    for e in scored:
        key = (e['benchmark'], e['protocol'])
        groups = cells.setdefault(key, {'n': 0, 'lab': 0, 'lex': 0, 'f1': 0.0})
        groups['n'] += 1
        groups['lab'] += e['verdict'] == 'CORRECT'
        groups['lex'] += e['lexical_correct'] >= 1.0
        groups['f1'] += e['f1']
    orig = {}
    for model, parts in MODEL_RUNS.items():
        for bench, runs in parts.items():
            for protocol in PROTOCOLS:
                nums = [original_acc(run, protocol) for run, _ in runs]
                orig[(bench, protocol)] = sum(a * n for a, n in nums) / sum(n for _, n in nums)
    pooled = {}
    for bench in ('SB', 'MQ'):
        g = [e for e in scored if e['benchmark'] == bench]
        pairs = [(e['verdict'], 'CORRECT' if e['lexical_correct'] else 'DEFECT') for e in g]
        ci = cluster_bootstrap([(e['instance_id'], e['verdict'],
                                 'CORRECT' if e['lexical_correct'] else 'DEFECT') for e in g])
        pooled[bench] = {'n': len(g),
                         'lab': sum(e['verdict'] == 'CORRECT' for e in g) / len(g),
                         'lex': sum(e['lexical_correct'] >= 1.0 for e in g) / len(g),
                         'agree': sum(a == b for a, b in pairs) / len(pairs),
                         'kappa': cohen_kappa(pairs), 'ci': ci}
    all_pairs = [(e['verdict'], 'CORRECT' if e['lexical_correct'] else 'DEFECT') for e in scored]
    all_ci = cluster_bootstrap([(e['instance_id'], e['verdict'],
                                 'CORRECT' if e['lexical_correct'] else 'DEFECT')
                                for e in scored])
    lenient = [e for e in scored if e['verdict'] == 'CORRECT' and e['lexical_correct'] < 1.0]
    strict = [e for e in scored if e['verdict'] == 'DEFECT' and e['lexical_correct'] >= 1.0]
    lines = ['# Main-table re-score pilot: Qwen-235B\n',
             f'Rule frozen before the first call: `{OUT.relative_to(ROOT)}/SCORING_RULE.md`. '
             f'Prompt `{spec["version"]}`, file sha256 '
             f'`{json.loads((ROOT / "rebuttal/pilots/20261112_labeller/labeller_prompt_v2.manifest.json").read_text())["file_sha256"]}`, '
             f'system sha256 `{spec["system_sha256"]}`, model `{MODEL_OPENROUTER}`. '
             f'Traces {len(scored)}/{len(rows)} scored; calls {sum(1 for c in calls if c.get("event") == "result")}; '
             f'spend **${spent:.6f}** against a ${CAP:.2f} cap. '
             f'Retried once at {RETRY_TOKENS} tokens: {sum(e["retried"] for e in ev)} traces.\n',
             f'Call log: `{CALLS.relative_to(ROOT)}`; case list: `{CASES.relative_to(ROOT)}` '
             f'({sha(CASES)}). Original numbers are unchanged; this file sits beside them.\n',
             '## Side by side by cell\n',
             'The labeller column is the **v2 verdict CORRECT rate**, which is the label the '
             'prompt defines: the answer is correct and no critical fact is absent or distorted. '
             'It is not yet an answer-accuracy estimate (see "What the labeller column means").\n',
             '| benchmark | protocol | n | paper cell | lexical acc | v2 CORRECT | delta | agreement | kappa |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for (bench, protocol) in [(b, p) for b in ('SB', 'MQ') for p in PROTOCOLS]:
        g = cells[(bench, protocol)]
        pairs = [(e['verdict'], 'CORRECT' if e['lexical_correct'] else 'DEFECT')
                 for e in scored if e['benchmark'] == bench and e['protocol'] == protocol]
        lab = g['lab'] / g['n']
        lex = g['lex'] / g['n']
        o = orig[(bench, protocol)]
        paper = f'{100 * o:.1f}% EM' if bench == 'SB' else f'{100 * o:.1f} F1'
        lines.append(f'| {bench} | {protocol} | {g["n"]} | {paper} | {100 * lex:.1f}% | '
                     f'{100 * lab:.1f}% | {100 * (lab - lex):+.1f} | '
                     f'{sum(a == b for a, b in pairs) / len(pairs):.3f} | '
                     f'{cohen_kappa(pairs):.3f} |')
    lines += ['', '## Pooled\n',
              '| benchmark | n | v2 CORRECT | lexical acc | agreement | kappa [95% CI] |',
              '| --- | ---: | ---: | ---: | ---: | --- |']
    for bench, v in pooled.items():
        lines.append(f'| {bench} | {v["n"]} | {100 * v["lab"]:.1f}% | {100 * v["lex"]:.1f}% | '
                     f'{v["agree"]:.3f} | {v["kappa"]:.3f} '
                     f'[{v["ci"]["kappa"][0]:.3f}, {v["ci"]["kappa"][1]:.3f}] |')
    lines += [f'| **all** | **{len(scored)}** | '
              f'**{100 * sum(e["verdict"] == "CORRECT" for e in scored) / len(scored):.1f}%** | '
              f'**{100 * sum(e["lexical_correct"] >= 1.0 for e in scored) / len(scored):.1f}%** | '
              f'**{sum(a == b for a, b in all_pairs) / len(all_pairs):.3f}** | '
              f'**{cohen_kappa(all_pairs):.3f} '
              f'[{all_ci["kappa"][0]:.3f}, {all_ci["kappa"][1]:.3f}]** |\n',
              '## Where the two rules disagree\n',
              f'- Labeller CORRECT, lexical wrong: **{len(lenient)}** traces.',
              f'- Labeller DEFECT, lexical correct: **{len(strict)}** traces.\n']
    for name, group in (('lenient', lenient), ('strict', strict)):
        if not group:
            continue
        lines += [f'### Labeller {name}\n',
                  '| benchmark | protocol | instance | gold | answer | F1 | labeller rationale |',
                  '| --- | --- | --- | --- | --- | ---: | --- |']
        for e in group:
            lines.append(f"| {e['benchmark']} | {e['protocol']} | {e['instance_id']} | "
                         f"`{str(e['gold_answer'])[:80]}` | `{e['answer_text'][:80]}` | "
                         f"{e['f1']:.3f} | {e['rationale'][:160]} |")
        lines.append('')
    if failed:
        lines += ['## Unscored traces\n', '| benchmark | protocol | instance |', '| --- | --- | --- |']
        for e in failed:
            lines.append(f"| {e['benchmark']} | {e['protocol']} | {e['instance_id']} |")
        lines.append('')
    def bucket(e):
        ra = (e['rationale'] or '').lower()
        if any(s in ra for s in ('no checkpoint', 'no critical fact is absent',
                                 'cannot be localized', 'faithfully restated',
                                 'faithfully carried', 'no pool or board',
                                 'not at any checkpoint')):
            return 'wrong answer, but no checkpoint defect'
        if any(s in ra for s in ('extra', 'adds', 'added', 'framing',
                                 'contains the gold', 'names the gold')):
            return 'contains the gold plus extra words'
        return 'other'

    mech = {}
    for e in lenient:
        mech[(e['benchmark'], bucket(e))] = mech.get((e['benchmark'], bucket(e)), 0) + 1
    lines += ['## What the labeller column means\n',
              'The v2 prompt defines DEFECT as **answer wrong and a critical fact absent or '
              'distorted at a checkpoint**. A wrong answer whose evidence is faithful at every '
              'checkpoint (a computation or aggregation error) falls outside both labels, and '
              'the model resolves it to CORRECT. It also resolves some exact-token mismatches '
              'to CORRECT when the gold entity is present. Both behaviours were present in the '
              'validation set (4 of the 7 disagreements); this population has many more such '
              'traces. The 89 lenient cases split as follows:\n',
              '| benchmark | mechanism | traces |', '| --- | --- | ---: |']
    for (b, m), n in sorted(mech.items()):
        lines.append(f'| {b} | {m} | {n} |')
    n_extra = mech.get(('MQ', 'contains the gold plus extra words'), 0)
    n_nocheck = (mech.get(('SB', 'wrong answer, but no checkpoint defect'), 0)
                 + mech.get(('MQ', 'wrong answer, but no checkpoint defect'), 0))
    lines += ['',
              f'Of the {len(lenient)}, **{n_extra}** are answers that contain the gold entity '
              'plus extra words, which the prompt\'s own normalization rule calls DEFECT, and '
              f'**{n_nocheck}** are wrong answers with faithful evidence (computation or '
              'aggregation errors, plus a few near-miss values). The remaining '
              f'{len(lenient) - n_extra - n_nocheck} include explicit self-contradictions '
              'that state the strict rule gives DEFECT and then return CORRECT. The CORRECT '
              'rate therefore overstates answer accuracy by **+20.3 points on MQ** (44.1% '
              'against 23.8% exact) and **+3.4 points on SB** (19.7% against 16.3%). The MQ '
              'number is close to the paper\'s mean-F1 cell (46.7), but it is not the same '
              'quantity: mean F1 gives partial credit, while the labeller is a binary '
              'evidence-flow label.\n',
              '## Reading\n',
              'This pilot does **not** support re-scoring the main-table task scores with the '
              f'v2 labeller as it stands. {len(lenient)} of {len(scored)} wrong answers are '
              'called CORRECT, and the two mechanisms above are systematic, not noise. The '
              'original lexical cells and the paper numbers are unchanged. A defensible '
              're-score needs either (a) a separate answer-equivalence prompt validated on '
              'the same 150 traces before any full run, or (b) reporting the v2 label only as '
              'an evidence-flow quantity beside the lexical cells, not as accuracy. No full '
              'run was started.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    SUMMARY.write_text(json.dumps({
        'traces': len(scored), 'failed': len(failed),
        'spent_usd': round(spent, 6),
        'cells': {f'{b}|{p}': {'n': v['n'], 'v2_correct': round(v['lab'] / v['n'], 4),
                               'lexical_acc': round(v['lex'] / v['n'], 4)}
                  for (b, p), v in cells.items()},
        'pooled': {b: {'n': v['n'], 'v2_correct': round(v['lab'], 4),
                       'lexical_acc': round(v['lex'], 4), 'agree': round(v['agree'], 4),
                       'kappa': round(v['kappa'], 4),
                       'kappa_ci': [round(x, 4) for x in v['ci']['kappa']]}
                   for b, v in pooled.items()},
        'lenient': len(lenient), 'strict': len(strict),
    }, indent=1) + '\n')
    print(json.dumps({'scored': len(scored), 'failed': len(failed),
                      'spent_usd': round(spent, 6),
                      'pooled': {b: {'lab': round(v['lab'], 3), 'lex': round(v['lex'], 3),
                                     'kappa': round(v['kappa'], 3)}
                                 for b, v in pooled.items()},
                      'lenient': len(lenient), 'strict': len(strict)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    if a.plan:
        build_rows()
    if a.run:
        execute(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()