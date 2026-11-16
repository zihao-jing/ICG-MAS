"""Answer-equivalence beside exact match for the direct-insertion and repair
answers, plus insertion paired with repair on the same 18 delivered cases.

Uses the frozen `answer-equiv-v1` prompt (`scripts/answer_equiv.py`). The
cohort here is MuSiQue (Stage 2), and answer-equivalence was validated on
Silo-Bench author labels only, so its counts here are labelled **not validated
on MuSiQue-style answers** and exact match stays the primary number.

    ./run.sh python -m scripts.answer_equiv_beside --run --cap-usd 0.50
    ./run.sh python -m scripts.answer_equiv_beside --report
"""
import argparse
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts.answer_equiv import load_prompt, parse, user_for
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.pilot_llm_labeller import MODEL_OPENROUTER, PRICE_IN, PRICE_OUT
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
PILOT = ROOT / 'rebuttal/pilots/20261112_missing_fact_repair'
OUT = ROOT / 'rebuttal/pilots/20261113_answer_equiv_beside'
CALLS = OUT / 'calls.jsonl'
LABELS = OUT / 'labels.json'
REPORT = OUT / 'report.md'
MAX_TOKENS = 300
WORKERS = 8


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def norm_model(m):
    return str(m).split('/')[-1]


def read_cases(path):
    d = json.loads(path.read_text())
    return d['cases'] if isinstance(d, dict) else d


def load_rows():
    rows = []
    di = PILOT / 'direct_insertion'
    di_cases = {c['instance_id']: c for c in read_cases(di / 'cases.json')}
    for line in (di / 'answers.jsonl').read_text().splitlines():
        if not line.strip():
            continue
        a = json.loads(line)
        c = di_cases[a['instance_id']]
        rows.append({
            'cohort': 'direct_insertion', 'instance_id': a['instance_id'],
            'model': norm_model(a['model']), 'arm': a['arm'],
            'question': c['question'], 'gold_answer': a['gold'],
            'answer_text': a['answer'], 'exact': a['exact'],
        })
    ef = PILOT / 'extraction_fix'
    ef_cases = {c['instance_id']: c for c in read_cases(ef / 'cases.json')}
    for line in (ef / 'answers.jsonl').read_text().splitlines():
        if not line.strip():
            continue
        a = json.loads(line)
        c = ef_cases[a['instance_id']]
        rows.append({
            'cohort': 'extraction_fix', 'instance_id': a['instance_id'],
            'model': norm_model(a['model']), 'arm': a['arm'],
            'question': c['question'], 'gold_answer': a['gold'],
            'answer_text': a['answer'], 'exact': a['exact'],
        })
    for r in rows:
        r['key'] = sha('|'.join([r['cohort'], r['instance_id'], r['model'],
                                 r['arm'], r['question'], r['gold_answer'],
                                 r['answer_text']]))[:24]
        r['pair'] = (r['cohort'], r['instance_id'], r['model'])
    return rows


def one(row, spec):
    from utility.apis.openrouter_api import single_request
    user = user_for({'question': row['question'], 'gold_answer': row['gold_answer'],
                     'answer_text': row['answer_text']})
    req = APIRequest(system_query=spec['system'], user_query=user,
                     model=MODEL_OPENROUTER, max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'answer_equiv_beside', 'key': row['key'],
                               'prompt_version': spec['version']})
    resp = single_request(req)
    usage = resp.usage or {}
    est_in = math.ceil(len(user) / 4) + math.ceil(len(spec['system']) / 4)
    cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
            + usage.get('completion_tokens', 0) * PRICE_OUT)
    return {'event': 'result', 'key': row['key'], 'cohort': row['cohort'],
            'instance_id': row['instance_id'], 'model': row['model'],
            'arm': row['arm'], 'success': resp.success, 'error': resp.error,
            'raw': resp.content, 'parsed': parse(resp.content or ''),
            'usage': usage, 'cost_usd': round(cost, 8),
            'prompt_version': spec['version'], 'model_used': MODEL_OPENROUTER}


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def run(cap):
    OUT.mkdir(parents=True, exist_ok=True)
    spec = load_prompt()
    rows = load_rows()
    done = {}
    if CALLS.exists():
        for l in CALLS.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                if r.get('event') == 'result' and r.get('parsed'):
                    done[r['key']] = r
    todo = [r for r in rows if r['key'] not in done]
    total = spent()
    print(json.dumps({'rows': len(rows), 'done': len(done), 'todo': len(todo),
                      'spent_usd': round(total, 6), 'cap': cap}), flush=True)
    with CALLS.open('a') as log:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {}
            for r in todo:
                est = 0.00012
                if total + 1.5 * est > cap:
                    print(json.dumps({'stop': 'cap', 'left': len(todo)}), flush=True)
                    break
                total += est
                futs[ex.submit(one, r, spec)] = r
            for f in as_completed(futs):
                rec = f.result()
                log.write(json.dumps(rec, ensure_ascii=False) + '\n')
                log.flush()
    OUT.mkdir(parents=True, exist_ok=True)
    print(json.dumps({'spent_usd': round(spent(), 6)}))


def ci(k, n):
    lo, hi = cp_ci(k, n)
    return f'{lo:.3f}-{hi:.3f}'


def report():
    rows = load_rows()
    lab = {}
    if CALLS.exists():
        for l in CALLS.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                if r.get('parsed'):
                    lab[r['key']] = r['parsed']['verdict']
    for r in rows:
        r['equiv'] = lab.get(r['key'])
        r['equiv_ok'] = r['exact'] == 1 or r['equiv'] == 'EQUIVALENT'
    lines = ['# Answer-equivalence beside exact match\n',
             'Prompt `answer-equiv-v1` (frozen; see '
             '`rebuttal/pilots/20261112_answer_equiv/`). **Not validated on '
             'MuSiQue-style answers**: the validation set was Silo-Bench author '
             'labels, and both cohorts here are MuSiQue (Stage 2). Exact match '
             'stays the primary number; the equivalence counts are descriptive '
             'and flagged wherever they differ.\n']
    for cohort, label in (('direct_insertion', 'Direct insertion (59 cases)'),
                          ('extraction_fix', 'Extraction fix (33 present cases)')):
        sub = [r for r in rows if r['cohort'] == cohort]
        lines += [f'## {label}\n',
                  '| arm | n | exact | 95% CI | exact or equivalent | 95% CI | equivalent-only |',
                  '| --- | ---: | ---: | --- | ---: | --- | ---: |']
        for arm in sorted({r['arm'] for r in sub}):
            a = [r for r in sub if r['arm'] == arm]
            e = sum(r['exact'] == 1 for r in a)
            q = sum(r['equiv_ok'] for r in a)
            o = sum(r['equiv_ok'] and r['exact'] != 1 for r in a)
            lines.append(f'| {arm} | {len(a)} | {e} | {ci(e, len(a))} | {q} | '
                         f'{ci(q, len(a))} | {o} |')
        extra = [r for r in sub if r['equiv_ok'] and r['exact'] != 1]
        if extra:
            lines += ['', f'Right content under equivalence, exact-match miss ({len(extra)}):\n',
                      '| case | model | arm | gold | answer | equivalence |',
                      '| --- | --- | --- | --- | --- | --- |']
            for r in extra:
                lines.append(f"| {r['instance_id']} | {r['model']} | {r['arm']} | "
                             f"{str(r['gold_answer'])[:40]} | {str(r['answer_text'])[:45]} | "
                             f"{r['equiv']} |")
        lines.append('')
    # Insertion and repair on the same 18 delivered instances.
    rep = {r['pair'] for r in rows
           if r['cohort'] == 'extraction_fix' and r['arm'] == 'repair'}
    ins = {(r['instance_id'], r['model']): r for r in rows
           if r['cohort'] == 'direct_insertion' and r['arm'] == 'insert'}
    ctl = {(r['instance_id'], r['model']): r for r in rows
           if r['cohort'] == 'direct_insertion' and r['arm'] == 'control'}
    repairs = {(r['instance_id'], r['model']): r for r in rows
               if r['cohort'] == 'extraction_fix' and r['arm'] == 'repair'}
    ctl_b = {(r['instance_id'], r['model']): r for r in rows
             if r['cohort'] == 'extraction_fix' and r['arm'] == 'board_only'}
    keys = sorted({(i, m) for (_, i, m) in rep})
    missing = [k for k in keys if k not in ins]
    n = len(keys)
    def cnt(d, field):
        return int(round(sum(d[k][field] for k in keys if k in d)))
    lines += ['## Insertion and repair on the same 18 delivered cases\n',
              f'{n} cases where the extraction-fix repair was delivered and an '
              f'insertion answer exists ({len(missing)} without an insertion '
              f'answer). Denominator is the same for both.\n',
              '| arm | n | exact | 95% CI | exact or equivalent |',
              '| --- | ---: | ---: | --- | ---: |']
    for d, name in ((ins, 'insert'), (repairs, 'repair'),
                    (ctl, 'insertion control'), (ctl_b, 'board-only control')):
        e = cnt(d, 'exact')
        q = sum(1 for k in keys if k in d and d[k]['equiv_ok'])
        lines.append(f'| {name} | {n} | {e} | {ci(e, n)} | {q} |')
    lines += ['', 'Reading: this paired table is the like-for-like comparison. '
              'The 19/33 insertion figure counts present cases the repair gate '
              'delivered only 18 of; 0/18 of the repair-paired control answers '
              'are exact.']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'paired_n': n, 'missing_insertion': missing,
                      'spent_usd': round(spent(), 6)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=0.50)
    a = ap.parse_args()
    if a.run:
        run(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()