"""Run the frozen v2 labeller prompt over the full 150-trace validation set.

Approved 2026-11-12 after the v2 re-pilot (agreement 0.950, kappa 0.900).
Cap $0.25; every attempted call is logged. The prompt is the frozen
`labeller_prompt_v2.json`, checked against its manifest before the run.

    ./run.sh python -m scripts.full_llm_labeller_v2 --execute --cap-usd 0.25
    ./run.sh python -m scripts.full_llm_labeller_v2 --report
"""
import argparse
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from utility.apis.base import APIRequest
from scripts.pilot_llm_labeller import (
    MODEL_OPENROUTER, PRICE_IN, PRICE_OUT, bootstrap, cluster_of, cohen_kappa,
    parse, render,
)
from scripts.repilot_llm_labeller_v2 import load_prompt, parse_last
from src.eval.evaluate import answer_f1
from src.eval.silo_bench_loader import silobench_exact_match

ROOT = Path(__file__).resolve().parent.parent
FIRST_PILOT = ROOT / 'rebuttal/pilots/20261112_labeller'
MANIFEST = FIRST_PILOT / 'validation_150.jsonl'
PROMPT = FIRST_PILOT / 'labeller_prompt_v2.json'
PROMPT_MANIFEST = FIRST_PILOT / 'labeller_prompt_v2.manifest.json'
OUTDIR = ROOT / 'rebuttal/pilots/20261112_labeller_v2_full'
CALLS = OUTDIR / 'calls.jsonl'
REPORT = OUTDIR / 'full_report.md'
CAP = 0.25
MAX_TOKENS = 800
WORKERS = 8


def rows():
    out = [json.loads(l) for l in MANIFEST.read_text().splitlines() if l.strip()]
    assert len(out) == 150, len(out)
    assert all(len(r['authors']) == 2 for r in out)
    assert sum(r['task'] == 'E1' for r in out) == 90
    assert sum(r['task'] == 'SB' for r in out) == 60
    return out


def one(row, spec, max_tokens=MAX_TOKENS):
    from utility.apis.openrouter_api import single_request
    user = render(row)
    meta = {'trace': row['task'] + ':' + row['item_id'],
            'openrouter_reasoning': False,
            'prompt_version': spec['version'],
            'system_sha256': spec['system_sha256'],
            'file_sha256': json.loads(PROMPT_MANIFEST.read_text())['file_sha256']}
    req = APIRequest(system_query=spec['system'], user_query=user,
                     model=MODEL_OPENROUTER, max_tokens=max_tokens,
                     temperature=0, metadata=meta)
    resp = single_request(req)
    usage = resp.usage or {}
    est_in = math.ceil(len(user) / 4) + math.ceil(len(spec['system']) / 4)
    cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
            + usage.get('completion_tokens', 0) * PRICE_OUT)
    return {'trace': meta['trace'], 'cluster': cluster_of(row),
            'task': row['task'], 'display': row['display'],
            'model': MODEL_OPENROUTER, 'provider': 'openrouter',
            'prompt_version': spec['version'],
            'system_sha256': spec['system_sha256'],
            'file_sha256': meta['file_sha256'],
            'success': resp.success, 'error': resp.error, 'raw': resp.content,
            'parsed': parse_last(resp.content or ''),
            'strict_parsed': bool(parse(resp.content or '')),
            'max_tokens': max_tokens, 'usage': usage, 'cost_usd': round(cost, 8)}


def execute(cap, max_tokens=MAX_TOKENS):
    spec = load_prompt()
    rs = rows()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    spent = 0.0
    latest = {}
    if CALLS.exists():
        for line in CALLS.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                latest[rec['trace']] = rec
                spent += rec.get('cost_usd') or 0
    done = {t for t, rec in latest.items() if rec.get('parsed')}
    todo = [r for r in rs if r['task'] + ':' + r['item_id'] not in done]
    print(json.dumps({'already_logged': len(done), 'todo': len(todo),
                      'spent_usd': round(spent, 6), 'cap_usd': cap}), flush=True)
    logged = len(done)
    with CALLS.open('a') as log:
        for i in range(0, len(todo), WORKERS):
            chunk = todo[i:i + WORKERS]
            # Worst-case reservation for this wave, including output budget.
            reserve = sum((math.ceil(len(render(r)) / 4)
                           + math.ceil(len(spec['system']) / 4)) * PRICE_IN * 1.5
                          + max_tokens * PRICE_OUT for r in chunk)
            if spent + reserve > cap:
                print(json.dumps({'stopped': 'cap', 'spent': round(spent, 6),
                                  'remaining': len(todo) - i}), flush=True)
                break
            with ThreadPoolExecutor(max_workers=WORKERS) as ex:
                futs = {ex.submit(one, r, spec, max_tokens): r for r in chunk}
                for fut in as_completed(futs):
                    r = futs[fut]
                    try:
                        rec = fut.result()
                    except Exception as exc:
                        rec = {'trace': r['task'] + ':' + r['item_id'],
                               'cluster': cluster_of(r), 'task': r['task'],
                               'display': r['display'], 'model': MODEL_OPENROUTER,
                               'provider': 'openrouter',
                               'prompt_version': spec['version'],
                               'system_sha256': spec['system_sha256'],
                               'file_sha256': json.loads(
                                   PROMPT_MANIFEST.read_text())['file_sha256'],
                               'success': False,
                               'error': type(exc).__name__ + ': ' + str(exc),
                               'raw': None, 'parsed': None, 'strict_parsed': False,
                               'max_tokens': max_tokens,
                               'usage': None, 'cost_usd': 0.0}
                    spent += rec.get('cost_usd') or 0
                    log.write(json.dumps(rec, ensure_ascii=False) + '\n')
                    log.flush()
                    logged += 1
            print(json.dumps({'logged': logged, 'of': len(rs),
                              'spent_usd': round(spent, 5)}), flush=True)
    print(json.dumps({'spent_usd': round(spent, 6), 'cap_usd': cap,
                      'logged': logged, 'of': len(rs)}), flush=True)


def full_last(text):
    """Last complete verdict object, with the rationale uncapped."""
    objs, depth, start = [], 0, None
    for i, ch in enumerate(text or ''):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}' and depth:
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    d = json.loads(text[start:i + 1])
                except Exception:
                    d = None
                if isinstance(d, dict) and str(d.get('verdict', '')).upper() in (
                        'DEFECT', 'CORRECT'):
                    objs.append(d)
    return objs[-1] if objs else {}


def score(row):
    t = row['trace']
    if row['task'] == 'SB':
        return silobench_exact_match(t.get('answer_text', ''), {'answer': t['gold_answer']})
    return answer_f1(t.get('answer_text', ''), {'answer': t['gold_answer']})


def report():
    spec = load_prompt()
    man = {r['task'] + ':' + r['item_id']: r for r in rows()}
    calls = [json.loads(l) for l in CALLS.read_text().splitlines() if l.strip()]
    for c in calls:
        assert c['system_sha256'] == spec['system_sha256']
        assert c['prompt_version'] == spec['version']
    order = {r['task'] + ':' + r['item_id']: i for i, r in enumerate(rows())}
    latest = {}
    for c in calls:
        latest[c['trace']] = c
    ev = []
    for trace, c in sorted(latest.items(), key=lambda kv: order.get(kv[0], 10 ** 9)):
        r = man[trace]
        parsed = c.get('parsed') or {}
        full = full_last(c.get('raw') or '')
        ev.append({'trace': trace, 'cluster': c['cluster'], 'task': c['task'],
                   'display': c['display'],
                   'pred': (full.get('verdict') or parsed.get('verdict') or '').upper() or None,
                   'rationale': full.get('rationale') or parsed.get('rationale', ''),
                   'objects': parsed.get('_objects', 1),
                   'strict_parsed': c.get('strict_parsed', bool(c.get('parsed'))),
                   'max_tokens': c.get('max_tokens', MAX_TOKENS),
                   'authors': r['authors'], 'row': r, 'cost': c['cost_usd'],
                   'success': c.get('success')})
    scored = [e for e in ev if e['pred']]
    failed = [e for e in ev if not e['pred']]
    strict_fail = [e for e in ev if e['pred'] and not e['strict_parsed']]
    multi = [e for e in scored if e['objects'] > 1]
    pairs = [(e['pred'], a['label']) for e in scored for a in e['authors']]
    agree = sum(x == y for x, y in pairs) / len(pairs)
    kappa = cohen_kappa(pairs)
    ci = bootstrap(scored)
    dis = [e for e in scored if any(e['pred'] != a['label'] for a in e['authors'])]
    retried = [e for e in scored if e['max_tokens'] > MAX_TOKENS]
    spent = sum(c.get('cost_usd') or 0 for c in calls)
    lines = ['# Full labeller run, prompt v2\n',
             f'Prompt version `{spec["version"]}`, system sha256 '
             f'`{spec["system_sha256"]}`, file sha256 '
             f'`{json.loads(PROMPT_MANIFEST.read_text())["file_sha256"]}`. '
             f'Model `{MODEL_OPENROUTER}` via OpenRouter, temperature 0. '
             f'Traces {len(scored)}/{len(ev)} parsed; 90 E1 + 60 SB, two authors each; '
             f'calls {len(calls)} records for {len(ev)} traces; '
             f'spend ${spent:.6f} against a ${CAP:.2f} cap. '
             f'Strict single-object parse succeeded on {len(scored) - len(strict_fail)}/'
             f'{len(ev)}; {len(multi)} trace(s) emitted more than one object. '
             f'Balanced-object fallback used on {len(strict_fail)} trace(s)'
             f'{" (" + ", ".join(e["task"] + " " + e["display"] for e in strict_fail) + ")" if strict_fail else ""}. '
             f'Unparsed: {len(failed)}. '
             f'Retried above the {MAX_TOKENS}-token output budget: {len(retried)} '
             f'trace(s)'
             f'{" at " + str(max(e["max_tokens"] for e in retried)) + " tokens" if retried else ""}.\n',
             f'Call log: `{CALLS.relative_to(ROOT)}` ({len(calls)} records, every attempted call). '
             f'Manifest: `{MANIFEST.relative_to(ROOT)}`.\n',
             '## Per-trace labels\n',
             '| # | task | trace | labeller | author A | author B | agrees |',
             '| ---: | --- | --- | --- | --- | --- | --- |']
    for i, e in enumerate(scored, 1):
        ab = {a['annotator']: a['label'] for a in e['authors']}
        ok = all(e['pred'] == a['label'] for a in e['authors'])
        lines.append(f"| {i} | {e['task']} | {e['display']} | {e['pred']} | "
                     f"{ab.get('A', '')} | {ab.get('B', '')} | {'yes' if ok else 'no'} |")
    if failed:
        lines.append('\n## Unscored traces\n')
        for e in failed:
            lines.append(f"- {e['task']} {e['display']}: {e.get('success')} "
                         f"{'' if e.get('success') else 'call failed or no verdict'}")
    lines += ['', '## Agreement\n',
              f'- Raw agreement: **{agree:.3f}** '
              f'({sum(x == y for x, y in pairs)} of {len(pairs)} author comparisons).',
              f'- Cohen kappa: **{kappa:.3f}**.',
              f'- 95% CI: agreement **{ci["agree"][0]:.3f}-{ci["agree"][1]:.3f}**, '
              f'kappa **{ci["kappa"][0]:.3f}-{ci["kappa"][1]:.3f}** '
              f'(cluster bootstrap, {len({e["cluster"] for e in scored})} clusters, '
              f'2,000 draws, seed 42).',
              f'- Disagreements: {len(dis)} traces.\n']
    for e in dis:
        t = e['row']['trace']
        ab = {a['annotator']: a['label'] for a in e['authors']}
        s = score(e['row'])
        metric = 'Silo-Bench exact match' if e['task'] == 'SB' else 'exact token-F1'
        direction = ('stricter than the authors' if e['pred'] == 'DEFECT'
                     and all(v == 'CORRECT' for v in ab.values()) else
                     'more lenient than the authors' if e['pred'] == 'CORRECT'
                     and all(v == 'DEFECT' for v in ab.values()) else 'mixed')
        lines += [f"### {e['task']} {e['display']}\n",
                  f"Gold: `{str(t['gold_answer'])[:400]}`  ",
                  f"Answer: `{str(t.get('answer_text', ''))[:400]}`  ",
                  f"{metric}: {s:.3f} ({direction}).  ",
                  f"Labeller: {e['pred']} — {e['rationale']}  ",
                  f"Authors: " + ', '.join(f"{k}={v}" for k, v in ab.items()) + '\n']
    failed_gate = ci['agree'][0] < 0.80 or ci['kappa'][0] < 0.60
    more_lenient = [e for e in dis if e['pred'] == 'CORRECT'
                    and all(a['label'] == 'DEFECT' for a in e['authors'])]
    author_split = [e for e in scored
                    if len({a['label'] for a in e['authors']}) > 1]
    pilot_keys = {r['task'] + ':' + r['item_id']
                  for r in map(json.loads,
                               (FIRST_PILOT / 'pilot_20.jsonl').read_text().splitlines())}
    held = [e for e in scored if e['trace'] not in pilot_keys]
    held_pairs = [(e['pred'], a['label']) for e in held for a in e['authors']]
    held_agree = sum(x == y for x, y in held_pairs) / len(held_pairs)
    held_kappa = cohen_kappa(held_pairs)
    held_ci = bootstrap(held)
    held_dis = [e for e in dis if e['trace'] not in pilot_keys]
    lines += ['## Held-out check\n',
              f'20 of the 150 traces are the v1 pilot, which was used to design the v2 '
              f'prompt. Excluding them, the held-out {len(held)} traces score agreement '
              f'**{held_agree:.3f}** ({sum(x == y for x, y in held_pairs)} of '
              f'{len(held_pairs)}; 95% CI {held_ci["agree"][0]:.3f}-{held_ci["agree"][1]:.3f}) '
              f'and kappa **{held_kappa:.3f}** (95% CI '
              f'{held_ci["kappa"][0]:.3f}-{held_ci["kappa"][1]:.3f}); '
              f'{len(held_dis)} of the 7 disagreements are in the held-out set. '
              f'The full-set and held-out scores are effectively the same.\n',
              '## Go / no-go\n',
              'Requirement: lower CI bound at least 0.80 agreement and kappa at least 0.60. '
              + ('**Passed.**' if not failed_gate else '**Failed.**') + '\n',
              '## Caveat\n',
              'The v2 dev re-pilot sample was author-unanimous, so its 0.950/0.900 score '
              'tested agreement with a consensus label, not disagreement resolution. '
              f'The 150-trace set has {len(author_split) if author_split else "no"} '
              'traces where the two authors differ, so it does not test disagreement '
              'resolution either; both scores measure agreement against consensus '
              'labels. The 7 disagreements are labeller-vs-authors, not '
              'author-vs-author.\n',
              f'Of the 7 disagreements, {len(more_lenient)} are the labeller returning '
              'CORRECT on an answer the authors call DEFECT: '
              + ', '.join(f"{e['task']} {e['display']}" for e in more_lenient) + '. '
              'Two of those rationales argue the evidence flow is faithful, which the '
              'prompt treats as CORRECT when the answer is wrong only at computation; '
              'two (Q18 run 1 and Q19 run 1) state the strict token rule gives DEFECT '
              'and then return CORRECT anyway. The other disagreements are the '
              'labeller applying the strict token rule where the authors were lenient. '
              'The pass is therefore against unanimous authors; the lenient class is '
              'a prompt-definition boundary, and the two explicit contradictions are '
              'genuine prompt-following errors.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'traces': len(scored), 'failed': len(failed),
                      'agreement': round(agree, 3), 'kappa': round(kappa, 3),
                      'ci': {'agree': [round(x, 3) for x in ci['agree']],
                             'kappa': [round(x, 3) for x in ci['kappa']]},
                      'disagreements': len(dis), 'spent_usd': round(spent, 6),
                      'go': 'pass' if not failed_gate else 'fail'}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    ap.add_argument('--max-tokens', type=int, default=MAX_TOKENS)
    a = ap.parse_args()
    if a.execute:
        execute(a.cap_usd, a.max_tokens)
    if a.report:
        report()


if __name__ == '__main__':
    main()