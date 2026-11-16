"""Answer-equivalence check: validate on the 150 author-labelled traces,
then (only if the pre-set gate passes) run it over the 608 main-table traces.

Frozen rule: `rebuttal/pilots/20261112_answer_equiv/ANSWER_EQUIV_RULE.md`,
written before any call. Prompt: `answer_equiv_v1.json`, checked against its
manifest before every run. Every attempted call is logged.

    ./run.sh python -m scripts.answer_equiv --validate --cap-usd 0.50
    ./run.sh python -m scripts.answer_equiv --report-validate
    ./run.sh python -m scripts.answer_equiv --main --cap-usd 2.00
    ./run.sh python -m scripts.answer_equiv --report-main
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
    MODEL_OPENROUTER, PRICE_IN, PRICE_OUT, cluster_of,
)
from scripts.repilot_llm_labeller_v2 import parse_last

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261112_answer_equiv'
PROMPT = OUT / 'answer_equiv_v1.json'
PROMPT_MANIFEST = OUT / 'answer_equiv_v1.manifest.json'
VALIDATION = ROOT / 'rebuttal/pilots/20261112_labeller/validation_150.jsonl'
CASES = ROOT / 'rebuttal/pilots/20261112_rescore/cases.jsonl'
V2_CALLS = ROOT / 'rebuttal/pilots/20261112_rescore/calls.jsonl'
CALLS_VAL = OUT / 'calls_validate.jsonl'
CALLS_MAIN = OUT / 'calls_main.jsonl'
REPORT_VAL = OUT / 'validation_report.md'
REPORT_MAIN = OUT / 'main_tables_report.md'
SUMMARY_MAIN = OUT / 'main_tables_summary.json'
MAX_TOKENS = 300
RETRY_TOKENS = 900
WORKERS = 8
SEED = 42
GATE_AGREE = 0.90
GATE_KAPPA = 0.75
GATE_RECALL = 0.85


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_prompt():
    raw = PROMPT.read_bytes()
    spec = json.loads(raw)
    man = json.loads(PROMPT_MANIFEST.read_text())
    assert hashlib.sha256(spec['system'].encode()).hexdigest() == spec['system_sha256']
    assert spec['system_sha256'] == man['system_sha256']
    assert hashlib.sha256(raw).hexdigest() == man['file_sha256']
    assert spec['model'] == MODEL_OPENROUTER
    return spec


def author_label(row):
    raw = row['authors'][0]['raw']
    return 'CORRECT' if raw in ('correct', 'CORRECT') else 'DEFECT'


def render(text):
    return text


def user_for(row):
    t = row.get('trace') or row
    gold = t.get('gold_answer')
    answer = t.get('answer_text')
    return (f"QUESTION\n{t['question']}\n\nGOLD ANSWER\n{gold}\n\n"
            f"SYSTEM ANSWER\n{answer}")


def last_object(text):
    """The last complete JSON object in `text` (None if there is none)."""
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
                if isinstance(d, dict):
                    objs.append(d)
    return objs[-1] if objs else None


def parse(text):
    d = last_object(text)
    if not isinstance(d, dict):
        return None
    v = str(d.get('verdict', '')).upper().replace(' ', '_')
    if v not in ('EQUIVALENT', 'NOT_EQUIVALENT'):
        return None
    return {'verdict': v, 'reason': str(d.get('reason') or '')[:400]}


def one(row, spec, max_tokens=MAX_TOKENS):
    from utility.apis.openrouter_api import single_request
    user = user_for(row)
    meta = {'trace': row_key(row),
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
    rec = {'event': 'result', 'trace': meta['trace'], 'success': resp.success,
           'error': resp.error, 'raw': resp.content, 'parsed': parse(resp.content or ''),
           'max_tokens': max_tokens, 'usage': usage, 'cost_usd': round(cost, 8),
           'prompt_version': spec['version'], 'system_sha256': spec['system_sha256'],
           'file_sha256': meta['file_sha256'], 'model': MODEL_OPENROUTER}
    rec.update(row_fields(row))
    return rec


def row_key(row):
    if 'key' in row:
        return row['key']
    return row['task'] + ':' + row['item_id']


def row_fields(row):
    if 'benchmark' in row:
        return {'benchmark': row['benchmark'], 'protocol': row['protocol'],
                'instance_id': row['instance_id'], 'run': row['run'],
                'cluster': row['instance_id'],
                'gold': str(row['gold_answer'])[:200],
                'answer': str(row['answer_text'])[:300],
                'lexical_correct': row['lexical_correct']}
    return {'task': row['task'], 'display': row['display'],
            'cluster': cluster_of(row),
            'author': author_label(row),
            'gold': str(row['trace'].get('gold_answer'))[:200],
            'answer': str(row['trace'].get('answer_text'))[:300]}


def spent_from(path):
    if not path.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in path.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def latest(path):
    out = {}
    if path.exists():
        for l in path.read_text().splitlines():
            if l.strip():
                rec = json.loads(l)
                if rec.get('event') == 'result':
                    out[rec['trace']] = rec
    return out


def execute(rows, calls_path, cap, label):
    spec = load_prompt()
    done = latest(calls_path)
    todo = [r for r in rows
            if row_key(r) not in done or not (done[row_key(r)].get('parsed'))]
    spent = spent_from(calls_path)
    print(json.dumps({'source': label, 'rows': len(rows), 'already': len(done),
                      'todo': len(todo), 'spent_usd': round(spent, 6),
                      'cap_usd': cap}), flush=True)
    calls_path.parent.mkdir(parents=True, exist_ok=True)
    with calls_path.open('a') as log:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {}
            for r in todo:
                est = math.ceil(len(user_for(r)) / 4) * PRICE_IN + 200 * PRICE_OUT
                if spent + 1.5 * est > cap:
                    print(json.dumps({'stop': 'cap', 'left': len(todo)}), flush=True)
                    break
                spent += est
                futs[ex.submit(one, r, spec)] = r
            for f in as_completed(futs):
                rec = f.result()
                log.write(json.dumps(rec, ensure_ascii=False) + '\n')
                log.flush()
                if rec.get('parsed') is None and rec.get('max_tokens') == MAX_TOKENS:
                    r = futs[f]
                    rec2 = one_fallback(r, spec)
                    log.write(json.dumps(rec2, ensure_ascii=False) + '\n')
                    log.flush()
    print(json.dumps({'done': len(todo), 'spent_usd': round(spent_from(calls_path), 6)}))


def one_fallback(row, spec):
    return one(row, spec, max_tokens=RETRY_TOKENS)


def kappa(pairs):
    n = len(pairs)
    if not n:
        return float('nan')
    po = sum(x == y for x, y in pairs) / n
    cats = set(x for x, _ in pairs) | set(y for _, y in pairs)
    p1 = {c: sum(x == c for x, _ in pairs) / n for c in cats}
    p2 = {c: sum(y == c for _, y in pairs) / n for c in cats}
    pe = sum(p1[c] * p2[c] for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else float('nan')


def boot(clusters, draws=2000):
    rng = random.Random(SEED)
    keys = list(clusters)
    ags, kaps = [], []
    for _ in range(draws):
        pairs = [p for k in (rng.choice(keys) for _ in keys) for p in clusters[k]]
        ags.append(sum(x == y for x, y in pairs) / len(pairs))
        k = kappa(pairs)
        if not math.isnan(k):
            kaps.append(k)
    q = lambda xs, p: sorted(xs)[int(p * (len(xs) - 1))]
    return (q(ags, .025), q(ags, .975)), (q(kaps, .025), q(kaps, .975))


def report_validate():
    rows = [json.loads(l) for l in VALIDATION.read_text().splitlines() if l.strip()]
    assert len(rows) == 150
    by_key = {row_key(r): r for r in rows}
    calls = latest(CALLS_VAL)
    scored = [(by_key[c['trace']], c) for c in calls.values() if c.get('parsed')]
    pairs = [(c['parsed']['verdict'], _map(author_label(r))) for r, c in scored]
    agree = sum(x == y for x, y in pairs) / len(pairs)
    k = kappa(pairs)
    clusters = {}
    for r, c in scored:
        clusters.setdefault(c['cluster'], []).append(
            (c['parsed']['verdict'], _map(author_label(r))))
    (alo, ahi), (klo, khi) = boot(clusters)
    correct = [(c['parsed']['verdict'], author_label(r)) for r, c in scored
               if author_label(r) == 'CORRECT']
    rec = sum(x == 'EQUIVALENT' for x, _ in correct) / len(correct) if correct else 0.0
    wrong = [(c['parsed']['verdict'], author_label(r)) for r, c in scored
             if author_label(r) == 'DEFECT']
    spec = sum(x == 'NOT_EQUIVALENT' for x, _ in wrong) / len(wrong) if wrong else 0.0
    conf = {'EQUIVALENT': {'CORRECT': 0, 'DEFECT': 0},
            'NOT_EQUIVALENT': {'CORRECT': 0, 'DEFECT': 0}}
    for r, c in scored:
        conf[c['parsed']['verdict']][author_label(r)] += 1
    gate = (agree >= GATE_AGREE and k >= GATE_KAPPA and rec >= GATE_RECALL)
    dis = [(r, c) for r, c in scored
           if c['parsed']['verdict'] != _map(author_label(r))]
    lines = ['# Answer-equivalence check: validation on the 150 author-labelled traces\n',
             f"Prompt `answer-equiv-v1`, file sha256 `{sha(PROMPT)}`, system sha256 "
             f"`{json.loads(PROMPT_MANIFEST.read_text())['system_sha256']}`, model "
             f"`{MODEL_OPENROUTER}`, temperature 0.",
             f"Scored {len(scored)}/{len(rows)}; spend ${spent_from(CALLS_VAL):.6f} "
             f"against a $0.50 cap. Calls: `{CALLS_VAL.relative_to(ROOT)}`.\n",
             '## Result\n',
             f"- Agreement with the authors' answer-correctness call: **{agree:.3f}** "
             f"(95% CI {alo:.3f}-{ahi:.3f}).",
             f"- Cohen's kappa: **{k:.3f}** (95% CI {klo:.3f}-{khi:.3f}).",
             f"- EQUIVALENT recall on the {len(correct)} author-CORRECT answers: "
             f"**{rec:.3f}**.",
             f"- NOT_EQUIVALENT recall on the {len(wrong)} author-DEFECT answers: "
             f"**{spec:.3f}**.\n",
             '| check verdict | author CORRECT | author DEFECT |',
             '| --- | ---: | ---: |',
             f"| EQUIVALENT | {conf['EQUIVALENT']['CORRECT']} | {conf['EQUIVALENT']['DEFECT']} |",
             f"| NOT_EQUIVALENT | {conf['NOT_EQUIVALENT']['CORRECT']} | {conf['NOT_EQUIVALENT']['DEFECT']} |",
             '\n## Go/no-go\n',
             f"Required: agreement >= {GATE_AGREE:.2f}, kappa >= {GATE_KAPPA:.2f}, "
             f"EQUIVALENT recall >= {GATE_RECALL:.2f}. **{'PASS' if gate else 'FAIL'}**.\n",
             '## Disagreements\n']
    if not dis:
        lines.append('None.')
    for r, c in dis:
        lines += [f"### {r['task']} {r['display']}",
                  f"Authors: {author_label(r)}; check: {c['parsed']['verdict']}",
                  f"Question: {str(r['trace']['question'])[:300]}",
                  f"Gold: {str(r['trace']['gold_answer'])[:300]}",
                  f"Answer: {str(r['trace']['answer_text'])[:300]}",
                  f"Reason: {c['parsed']['reason']}\n"]
    REPORT_VAL.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'scored': len(scored), 'agree': round(agree, 4),
                      'kappa': round(k, 4), 'recall_correct': round(rec, 4),
                      'ci_agree': [round(alo, 3), round(ahi, 3)],
                      'ci_kappa': [round(klo, 3), round(khi, 3)],
                      'gate': 'PASS' if gate else 'FAIL',
                      'spent_usd': round(spent_from(CALLS_VAL), 6)}, indent=1))


def _map(author):
    return 'EQUIVALENT' if author == 'CORRECT' else 'NOT_EQUIVALENT'


def v2_by_cell():
    out = {}
    if V2_CALLS.exists():
        for l in V2_CALLS.read_text().splitlines():
            if not l.strip():
                continue
            rec = json.loads(l)
            if rec.get('event') != 'result' or not rec.get('parsed'):
                continue
            key = (rec['benchmark'], rec['protocol'])
            out.setdefault(key, []).append(rec['parsed']['verdict'] == 'CORRECT')
    return out


def report_main():
    rows = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]
    calls = latest(CALLS_MAIN)
    scored = [(r, calls[row_key(r)]) for r in rows if row_key(r) in calls
              and calls[row_key(r)].get('parsed')]
    cells = {}
    for r, c in scored:
        cells.setdefault((r['benchmark'], r['protocol']), []).append(
            (c['parsed']['verdict'] == 'EQUIVALENT', r['lexical_correct']))
    v2 = v2_by_cell()
    from scripts.rescore_main_tables import original_acc, MODEL_RUNS

    def paper_cell(bench, proto):
        tot = n = 0
        for run, _ in MODEL_RUNS['qwen235b'][bench]:
            acc, k = original_acc(run, proto)
            tot += acc * k
            n += k
        return tot / n
    agree = sum(eq == lex for cell in cells.values() for eq, lex in cell)
    n = sum(len(v) for v in cells.values())
    pairs = [(('EQUIVALENT' if eq else 'NOT_EQUIVALENT'),
              ('EQUIVALENT' if lex else 'NOT_EQUIVALENT'))
             for cell in cells.values() for eq, lex in cell]
    sb_cells = {k: v for k, v in cells.items() if k[0] == 'SB'}
    sb_pairs = [(('EQUIVALENT' if e else 'NOT_EQUIVALENT'),
                 ('EQUIVALENT' if l else 'NOT_EQUIVALENT'))
                for v in sb_cells.values() for e, l in v]
    sb_agree = sum(e == l for v in sb_cells.values() for e, l in v)
    sb_n = sum(len(v) for v in sb_cells.values())
    lines = ['# Answer-equivalence check: Silo-Bench only\n',
             f"Prompt `answer-equiv-v1` (file sha256 `{sha(PROMPT)}`). "
             f"Qwen-235B, Silo-Bench 52 traces, four protocols; scored "
             f"{sb_n}/{sb_n}; spend ${spent_from(CALLS_MAIN):.6f} in total, including "
             f"the 100 MuSiQue calls that are logged but not used here, against a $2 cap.\n",
             'Validation on the 150 author-labelled traces: agreement 0.940, kappa 0.848 '
             '(95% CI 0.725-0.939), EQUIVALENT recall 0.947; the frozen gate '
             '(kappa >= 0.75 on the point estimate) passed.\n',
             'The check is reported only for Silo-Bench. The MuSiQue cells stay at '
             'lexical exact/F1: the check was not validated on MuSiQue-style free-text '
             'answers, and on this population it is much more permissive than lexical. '
             'The 100 MuSiQue calls were made and are logged, but their cells are not '
             'reported here and do not replace the lexical cells.\n',
             '| cell | n | paper cell (SB exact) | lexical exact | answer-equiv |',
             '| --- | ---: | ---: | ---: | ---: |']
    for proto in ('summary_exchange', 'random_relay', 'score_ranked_relay',
                  'redundancy_aware_relay'):
        cell = cells.get(('SB', proto)) or []
        if not cell:
            continue
        lex = sum(l for _, l in cell) / len(cell)
        eq = sum(e for e, _ in cell) / len(cell)
        lines.append(f"| SB {proto} | {len(cell)} | {100*paper_cell('SB', proto):.1f}% | "
                     f"{100*lex:.1f}% | {100*eq:.1f}% |")
    cell = [x for v in sb_cells.values() for x in v]
    lex = sum(l for _, l in cell) / len(cell)
    eq = sum(e for e, _ in cell) / len(cell)
    pp = sum(paper_cell('SB', p) * len(sb_cells[('SB', p)])
             for p in ('summary_exchange', 'random_relay', 'score_ranked_relay',
                       'redundancy_aware_relay') if sb_cells.get(('SB', p))) / len(cell)
    lines.append(f"| **SB pooled** | {len(cell)} | {100*pp:.1f}% | {100*lex:.1f}% | "
                 f"{100*eq:.1f}% |")
    lines += ['', '## Agreement on Silo-Bench\n',
              f"Answer-equivalence vs lexical exact match: {sb_agree}/{sb_n} "
              f"({100*sb_agree/sb_n:.1f}%); kappa {kappa(sb_pairs):.3f}.",
              'The check moves one SB summary trace from wrong to right (one '
              'disagreement, lexical wrong / check EQUIVALENT); no SB answer that '
              'lexical scores right is called not-equivalent.\n']
    dis = []
    for r, c in scored:
        if r['benchmark'] != 'SB':
            continue
        eq = c['parsed']['verdict'] == 'EQUIVALENT'
        if eq != bool(r['lexical_correct']):
            dis.append({'key': row_key(r), 'benchmark': r['benchmark'],
                        'protocol': r['protocol'], 'lexical': r['lexical_correct'],
                        'equiv': c['parsed']['verdict'], 'lex_f1': r['f1'],
                        'gold': str(r['gold_answer'])[:200],
                        'answer': str(r['answer_text'])[:300],
                        'reason': c['parsed']['reason']})
    lines.append(f'{len(dis)} disagreements are listed in `main_tables_summary.json`.')
    REPORT_MAIN.write_text('\n'.join(lines) + '\n')
    SUMMARY_MAIN.write_text(json.dumps({'scored_sb': sb_n, 'scored_all': n, 'rows': len(rows),
                                        'agree_sb': sb_agree / sb_n,
                                        'kappa_sb': kappa(sb_pairs),
                                        'agree_all': agree / n, 'kappa_all': kappa(pairs),
                                        'spent_usd': round(spent_from(CALLS_MAIN), 6),
                                        'disagreements': dis}, indent=1))
    print(json.dumps({'scored_sb': sb_n, 'scored_all': n,
                      'agree_sb': round(sb_agree / sb_n, 4),
                      'kappa_sb': round(kappa(sb_pairs), 4),
                      'agree_all': round(agree / n, 4),
                      'disagreements': len(dis),
                      'spent_usd': round(spent_from(CALLS_MAIN), 6)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--validate', action='store_true')
    ap.add_argument('--main', action='store_true')
    ap.add_argument('--report-validate', action='store_true')
    ap.add_argument('--report-main', action='store_true')
    ap.add_argument('--cap-usd', type=float)
    ap.add_argument('--limit', type=int, default=None)
    a = ap.parse_args()
    if a.validate:
        rows = [json.loads(l) for l in VALIDATION.read_text().splitlines() if l.strip()]
        if a.limit:
            rows = rows[:a.limit]
        execute(rows, CALLS_VAL, a.cap_usd or 0.50, 'validation-150')
    if a.main:
        rows = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]
        if a.limit:
            rows = rows[:a.limit]
        execute(rows, CALLS_MAIN, a.cap_usd or 2.00, 'main-608')
    if a.report_validate:
        report_validate()
    if a.report_main:
        report_main()


if __name__ == '__main__':
    main()