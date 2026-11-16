"""LLM labeller: build the 150-trace validation set, run a 20-trace pilot.

The labeller reads one trace (question, gold, source contexts, gold support,
extraction pool, board, final answer) and calls DEFECT or CORRECT. Author
labels come from the E1 anchor (90 traces, two authors each) and the
Silo-Bench anchor (60 traces, two authors each). E1 author calls other than
`correct` (reached_but_unused, lost, exclude_partial, exclude_uncertain) map
to DEFECT.

No model call by default. `--execute` spends, logs every call, and stops at
`--cap-usd` (default 2.0). `--provider openrouter` uses the OpenRouter key in
`.env` with model `anthropic/claude-haiku-5.5`; the default provider is the
direct Anthropic adapter (`ANTHROPIC_API_KEY`). `--report` needs an existing
calls file.

    ./run.sh python -m scripts.pilot_llm_labeller --build
    ./run.sh python -m scripts.pilot_llm_labeller --execute --pilot 20 --provider openrouter --cap-usd 0.25
    ./run.sh python -m scripts.pilot_llm_labeller --report
"""
import argparse
import json
import math
import random
from pathlib import Path

from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
E1_RETURNS = ROOT / 'rebuttal/annotation/returns'
SB_RETURNS = ROOT / 'rebuttal/annotation/packets_20261110/returns/SB_anchor'
OUTDIR = ROOT / 'rebuttal/pilots/20261112_labeller'
MANIFEST = OUTDIR / 'validation_150.jsonl'
PILOT = OUTDIR / 'pilot_20.jsonl'
CALLS = OUTDIR / 'calls.jsonl'
REPORT = OUTDIR / 'pilot_report.md'
MODEL_CLAUDE = 'claude-haiku-5-5'
MODEL_OPENROUTER = 'anthropic/claude-haiku-5.5'
PRICE_IN = 0.10 / 1_000_000   # USD per prompt token
PRICE_OUT = 0.50 / 1_000_000  # USD per completion token
SEED = 42

SYSTEM = """You audit evidence flow in a multi-agent run.

Definitions, from the authors' labelling guide:
- A critical fact is a fact the gold answer cannot be reached without.
- A carrier is a pool or board unit that faithfully restates the fact. Faithful
  means entity, relation, value and qualifier are all preserved; shortening
  that keeps all four is faithful. A changed value, entity, date, relation or
  negation is distorted. A dropped qualifier is partial.
- CORRECT: the final answer is correct, even if some board unit is imperfect.
- DEFECT: the answer is wrong and a critical fact is absent or distorted at a
  checkpoint (never extracted = pool defect; extracted but not passed on =
  board defect), or the only loss is a partial detail.
- Use only the source texts. Do not add outside knowledge. Do not decide from
  the answer being wrong alone.
- Do not solve or recompute the task. Treat the gold answer as correct and
  compare the final answer to it; a paraphrase with the same meaning is
  CORRECT. If they differ, look for the checkpoint where a critical fact is
  absent or distorted.

Return strict JSON only:
{"verdict": "DEFECT" | "CORRECT",
 "checkpoint": "pool" | "board" | "none",
 "evidence_unit_ids": ["..."],
 "rationale": "one or two sentences"}"""


def e1_rows():
    out = {}
    for letter in 'ABCD':
        rows = json.loads((E1_RETURNS / f'E1anchor_{letter}_labelling-v1.0.json').read_text())
        for r in rows:
            key = 'E1:' + r['item_id']
            out.setdefault(key, {'task': 'E1', 'item_id': r['item_id'],
                                 'display': r.get('display_name', ''),
                                 'trace': r['trace'], 'authors': []})
            label = r['answers']['binary_call']
            out[key]['authors'].append({'annotator': letter, 'raw': label,
                                        'label': 'CORRECT' if label == 'correct' else 'DEFECT'})
    return list(out.values())


def sb_rows():
    out = {}
    for f in sorted(SB_RETURNS.glob('annotator_*.jsonl')):
        letter = f.stem.split('_')[-1]
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            key = 'SB:' + r['item_id']
            out.setdefault(key, {'task': 'SB', 'item_id': r['item_id'],
                                 'display': r['trace']['instance_id'],
                                 'trace': r['trace'], 'authors': []})
            label = r['answers']['binary_call']
            out[key]['authors'].append({'annotator': letter, 'raw': label,
                                        'label': 'CORRECT' if label == 'CORRECT' else 'DEFECT'})
    return list(out.values())


def cluster_of(row):
    if row['task'] == 'E1':
        return row['display'].split(' run ')[0]
    return row['trace']['instance_id']


def render(row):
    t = row['trace']
    lines = [f"QUESTION\n{t['question']}", f"\nGOLD ANSWER\n{t['gold_answer']}", "\nSOURCES"]
    for c in t.get('source_contexts') or []:
        lines.append(f"[agent-{c['agent_id']}]\n{c['text'][:8000]}")
    supports = t.get('source_supports') or []
    if supports:
        lines.append("\nGOLD SUPPORTING FACTS")
        for s in supports:
            lines.append(f"[{s.get('support_id') or s.get('agent_id')}] {s['text'][:2000]}")
    lines.append("\nEXTRACTION POOL")
    for u in (t.get('checkpoints') or {}).get('extraction') or []:
        lines.append(f"{u['unit_id']} [agent={u['agent_id']}]: {u['text'][:1000]}")
    lines.append("\nBOARD")
    for u in (t.get('checkpoints') or {}).get('board') or []:
        lines.append(f"{u['unit_id']} [agent={u['agent_id']}]: {u['text'][:1000]}")
    lines.append(f"\nFINAL ANSWER\n{t.get('answer_text', '')}")
    return '\n'.join(lines)


def build():
    rows = e1_rows() + sb_rows()
    counts = {'E1': sum(r['task'] == 'E1' for r in rows), 'SB': sum(r['task'] == 'SB' for r in rows),
              'two_authors': sum(len(r['authors']) == 2 for r in rows)}
    assert len(rows) == 150, len(rows)
    assert counts['two_authors'] == 150, counts
    OUTDIR.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open('w') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    rng = random.Random(SEED)
    e1 = sorted([r for r in rows if r['task'] == 'E1'], key=lambda r: r['item_id'])
    sb = sorted([r for r in rows if r['task'] == 'SB'], key=lambda r: r['item_id'])
    sample = rng.sample(e1, 12) + rng.sample(sb, 8)
    with PILOT.open('w') as f:
        for r in sample:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    chars = [len(render(r)) for r in rows]
    pchars = [len(render(r)) for r in sample]
    est = [math.ceil(c / 4) for c in chars]
    print(json.dumps({'traces': len(rows), 'counts': counts,
                      'clusters': len({cluster_of(r) for r in rows}),
                      'pilot': {'E1': sum(r['task'] == 'E1' for r in sample),
                                'SB': sum(r['task'] == 'SB' for r in sample)},
                      'chars_mean': round(sum(chars) / len(chars)),
                      'chars_p90': sorted(chars)[int(.9 * len(chars))],
                      'tokens_est_mean': round(sum(est) / len(est)),
                      'tokens_est_p90': sorted(est)[int(.9 * len(est))],
                      'pilot_chars_mean': round(sum(pchars) / len(pchars)),
                      'pilot_est_cost_usd': round(sum(math.ceil(c / 4) for c in pchars)
                                                  * PRICE_IN, 4)}), flush=True)


def parse(text):
    try:
        s = text[text.index('{'):text.rindex('}') + 1]
        d = json.loads(s)
        v = d.get('verdict', '').upper()
        if v not in ('DEFECT', 'CORRECT'):
            return None
        return {'verdict': v, 'checkpoint': d.get('checkpoint'),
                'evidence_unit_ids': d.get('evidence_unit_ids') or [],
                'rationale': (d.get('rationale') or '')[:500]}
    except Exception:
        return None


def execute(pilot_n, cap, provider='claude'):
    if provider == 'openrouter':
        from utility.apis.openrouter_api import single_request
        model = MODEL_OPENROUTER
    else:
        from utility.apis.claude_api import single_request
        model = MODEL_CLAUDE
    rows = [json.loads(l) for l in PILOT.read_text().splitlines()][:pilot_n]
    spent = 0.0
    OUTDIR.mkdir(parents=True, exist_ok=True)
    with CALLS.open('a') as log:
        for r in rows:
            user = render(r)
            meta = {'trace': r['task'] + ':' + r['item_id']}
            if provider == 'openrouter':
                # Haiku 5.5 spends the whole output budget on reasoning
                # otherwise, leaving an empty content field.
                meta['openrouter_reasoning'] = False
            req = APIRequest(system_query=SYSTEM, user_query=user, model=model,
                             max_tokens=800, temperature=0, metadata=meta)
            est_in = math.ceil(len(user) / 4) + math.ceil(len(SYSTEM) / 4)
            if spent + est_in * PRICE_IN * 1.5 > cap:
                print(json.dumps({'stopped': 'cap', 'spent': round(spent, 6)}))
                break
            try:
                resp = single_request(req)
            except Exception as exc:
                print(json.dumps({'error': type(exc).__name__ + ': ' + str(exc),
                                  'trace': r['task'] + ':' + r['item_id']}), flush=True)
                break
            usage = resp.usage or {}
            cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
                    + usage.get('completion_tokens', 0) * PRICE_OUT)
            spent += cost
            rec = {'trace': r['task'] + ':' + r['item_id'], 'cluster': cluster_of(r),
                   'model': model, 'provider': provider, 'success': resp.success, 'error': resp.error,
                   'raw': resp.content, 'parsed': parse(resp.content or ''),
                   'usage': usage, 'cost_usd': round(cost, 8)}
            log.write(json.dumps(rec, ensure_ascii=False) + '\n')
            log.flush()
            print(json.dumps({'trace': rec['trace'], 'success': resp.success,
                              'verdict': (rec['parsed'] or {}).get('verdict'),
                              'spent': round(spent, 5)}), flush=True)
    print(json.dumps({'spent_usd': round(spent, 6), 'cap_usd': cap}))


def cohen_kappa(pairs):
    n = len(pairs)
    if not n:
        return float('nan')
    a = sum(x == y for x, y in pairs) / n
    p1 = sum(x == 'DEFECT' for x, _ in pairs) / n
    p2 = sum(y == 'DEFECT' for _, y in pairs) / n
    pe = p1 * p2 + (1 - p1) * (1 - p2)
    return (a - pe) / (1 - pe) if pe < 1 else float('nan')


def bootstrap(rows, draws=2000):
    rng = random.Random(SEED)
    clusters = {}
    for r in rows:
        pairs = [(r['pred'], a['label']) for a in r['authors'] if r['pred']]
        clusters.setdefault(r['cluster'], []).extend(pairs)
    keys = list(clusters)
    ags, kaps = [], []
    for _ in range(draws):
        picked = [clusters[rng.choice(keys)] for _ in keys]
        pairs = [p for g in picked for p in g]
        ags.append(sum(x == y for x, y in pairs) / len(pairs))
        kaps.append(cohen_kappa(pairs))
    kaps = [k for k in kaps if not math.isnan(k)]
    q = lambda xs, p: sorted(xs)[int(p * (len(xs) - 1))]
    return {'agree': (q(ags, .025), q(ags, .975)), 'kappa': (q(kaps, .025), q(kaps, .975))}


def report():
    calls = [json.loads(l) for l in CALLS.read_text().splitlines()]
    rows = [json.loads(l) for l in MANIFEST.read_text().splitlines()]
    by_key = {r['task'] + ':' + r['item_id']: r for r in rows}
    evald = []
    for c in calls:
        r = by_key[c['trace']]
        p = (c.get('parsed') or {}).get('verdict')
        if p:
            evald.append({'cluster': c['cluster'], 'pred': p, 'authors': r['authors'],
                          'display': r['display'], 'task': r['task']})
    pairs = [(e['pred'], a['label']) for e in evald for a in e['authors']]
    agree = sum(x == y for x, y in pairs) / len(pairs) if pairs else float('nan')
    kappa = cohen_kappa(pairs)
    ci = bootstrap(evald)
    dis = [e for e in evald if any(e['pred'] != a['label'] for a in e['authors'])]
    lines = ['# LLM labeller pilot\n',
             f'Models: {", ".join(sorted({c["model"] for c in calls}))}. '
             f'Traces: {len(calls)}; parsed: {len(evald)}; '
             f'invalid: {len(calls) - len(evald)}.\n',
             f'Raw agreement: {agree:.3f} (95% CI {ci["agree"][0]:.3f}-{ci["agree"][1]:.3f}). '
             f'Cohen kappa: {kappa:.3f} (95% CI {ci["kappa"][0]:.3f}-{ci["kappa"][1]:.3f}).\n',
             '## Disagreements\n',
             '| trace | labeller | author A | author B |',
             '| --- | --- | --- | --- |']
    for e in dis:
        ab = {a['annotator']: a['label'] for a in e['authors']}
        lines.append(f"| {e['display']} | {e['pred']} | {ab.get('A', ab.get('C', ''))} | "
                     f"{ab.get('B', ab.get('D', ''))} |")
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'agreement': round(agree, 3), 'kappa': round(kappa, 3),
                      'ci': {'agree': [round(x, 3) for x in ci['agree']],
                             'kappa': [round(x, 3) for x in ci['kappa']]},
                      'traces': len(calls), 'disagreements': len(dis)}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--pilot', type=int, default=20)
    ap.add_argument('--cap-usd', type=float, default=2.0)
    ap.add_argument('--provider', choices=('claude', 'openrouter'), default='claude')
    a = ap.parse_args()
    if a.build:
        build()
    if a.execute:
        execute(a.pilot, a.cap_usd, a.provider)
    if a.report:
        report()
    if not (a.build or a.execute or a.report):
        build()


if __name__ == '__main__':
    main()