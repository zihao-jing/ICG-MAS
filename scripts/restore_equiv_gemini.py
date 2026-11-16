"""Answer-equivalence re-score of the restore-source reference subset (92 cases), with a paper-model labeller.

Instrument: the frozen answer-equivalence prompt `rebuttal/pilots/20261112_answer_equiv/answer_equiv_v1.json`, unchanged.
Labeller: google/gemini-3.6-flash (paper model). The validated checker in `scripts/answer_equiv.py` runs on
claude-haiku-5.5, which may not be called for new labelling, so the same prompt is run on Gemini 3.6 Flash and
must pass the same go/no-go gate on the 150 author-labelled traces before it scores the restore subset.

    ./.conda-env/bin/python -m scripts.restore_equiv_gemini --validate
    ./.conda-env/bin/python -m scripts.restore_equiv_gemini --restore      # only after the validation gate passes
    ./.conda-env/bin/python -m scripts.restore_equiv_gemini --report
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from scripts.missing_fact_repair_pilot import price
from src.protocols.base import extract_answer
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
PROMPT = ROOT / 'rebuttal/pilots/20261112_answer_equiv/answer_equiv_v1.json'
PROMPT_MANIFEST = ROOT / 'rebuttal/pilots/20261112_answer_equiv/answer_equiv_v1.manifest.json'
VALIDATION = ROOT / 'rebuttal/pilots/20261112_labeller/validation_150.jsonl'
RESTORE = ROOT / 'rebuttal/pilots/20261113_restore_source'
OUT = ROOT / 'rebuttal/pilots/20261116_restore_equiv_gemini'
MODEL = 'google/gemini-3.6-flash'
MAX_TOKENS = 400
CAP = 0.50
GATE_AGREE, GATE_KAPPA, GATE_RECALL = 0.90, 0.75, 0.85
CALLS = OUT / 'calls.jsonl'


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def load_prompt():
    raw = PROMPT.read_bytes()
    spec = json.loads(raw)
    man = json.loads(PROMPT_MANIFEST.read_text())
    assert sha_bytes(spec['system'].encode()) == spec['system_sha256'] == man['system_sha256']
    assert sha_bytes(raw) == man['file_sha256'], 'prompt file changed'
    return spec


def parse(text):
    objs = re.findall(r'\{[^{}]*\}', text or '')
    for raw in reversed(objs):
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        v = str(d.get('verdict', '')).upper().replace(' ', '_')
        if v in ('EQUIVALENT', 'NOT_EQUIVALENT'):
            return v
    return None


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def call(key, question, gold, answer, spec, total):
    user = f"QUESTION\n{question}\n\nGOLD ANSWER\n{gold}\n\nSYSTEM ANSWER\n{answer}"
    pin, pout = price(MODEL)
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    est = est_in * pin + MAX_TOKENS * pout
    if total + est > CAP:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap', 'estimate_usd': est}) + '\n')
        return None, total
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'model': MODEL, 'max_tokens': MAX_TOKENS}) + '\n')
    req = APIRequest(system_query=spec['system'], user_query=user, model=MODEL, max_tokens=MAX_TOKENS,
                     temperature=0, metadata={'pilot': 'restore_equiv_gemini', 'key': key})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * pin + usage.get('completion_tokens', 0) * pout
    rec = {'event': 'result', 'key': key, 'success': resp.success, 'error': resp.error,
           'content': resp.content, 'verdict': parse(resp.content if resp.success else ''),
           'cost_usd': round(cost, 8)}
    with CALLS.open('a') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    return rec, total + cost


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    labels = {x for p in pairs for x in p}
    pe = sum((sum(1 for a, _ in pairs if a == l) / n) * (sum(1 for _, b in pairs if b == l) / n) for l in labels)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def summarise(rows, res):
    """Score the validation from the stored verdicts. Rows that share an item_id share one verdict (as in the
    Haiku validation); unparsed verdicts count as disagreement."""
    pairs = []
    for r in rows:
        author = 'CORRECT' if r['authors'][0]['raw'] in ('correct', 'CORRECT') else 'DEFECT'
        v = res.get('val:' + r['item_id'])
        pairs.append((author, v))
    n = len(pairs)
    agree = sum(1 for a, v in pairs if v is not None and (a == 'CORRECT') == (v == 'EQUIVALENT'))
    lab = [('CORRECT' if a == 'CORRECT' else 'DEFECT', 'CORRECT' if v == 'EQUIVALENT' else 'DEFECT') for a, v in pairs]
    k = kappa(lab)
    corr = [v for a, v in pairs if a == 'CORRECT' and v]
    defect = [v for a, v in pairs if a == 'DEFECT' and v]
    rec_eq = sum(v == 'EQUIVALENT' for v in corr) / len(corr)
    rec_ne = sum(v == 'NOT_EQUIVALENT' for v in defect) / len(defect)
    gate = agree / n >= GATE_AGREE and k >= GATE_KAPPA and rec_eq >= GATE_RECALL
    summary = {'n_rows': n, 'unique_items': len(res), 'unparsed': sum(1 for a, v in pairs if v is None),
               'agree': agree, 'agreement': round(agree / n, 3), 'kappa': round(k, 3),
               'equivalent_recall_on_author_correct': round(rec_eq, 3),
               'not_equivalent_recall_on_author_defect': round(rec_ne, 3), 'gate_pass': gate,
               'spend_total_usd': round(spent(), 6), 'model': MODEL,
               'prompt_sha256': sha_bytes(PROMPT.read_bytes())}
    (OUT / 'validation_summary.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


def validate():
    OUT.mkdir(parents=True, exist_ok=True)
    spec = load_prompt()
    rows = [json.loads(l) for l in VALIDATION.read_text().splitlines() if l.strip()]
    total = spent()
    res = {}
    for r in rows:
        key = 'val:' + r['item_id']
        t = r['trace']
        author = 'CORRECT' if r['authors'][0]['raw'] in ('correct', 'CORRECT') else 'DEFECT'
        rec, total = call(key, t['question'], t.get('gold_answer'), t.get('answer_text'), spec, total)
        if rec is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        res[key] = rec['verdict']
    summarise(rows, res)


def restore_cases():
    """The 92 reference-gated cases: gold, question, and the stored control and restore answers."""
    cases = json.loads((RESTORE / 'cases.json').read_text())
    ci = {(c['instance_id'], c['model']): c for c in cases}
    keys = [x['key'] for x in json.loads((RESTORE / 'reference_subset_cases.json').read_text())]
    res = {r['key']: r for r in json.loads((RESTORE / 'results.json').read_text())['cases']}
    raw = {}
    for l in (RESTORE / 'calls.jsonl').read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            if r.get('event') == 'result':
                raw[r['key']] = r['content']
    out = []
    for k in keys:
        r = res[k]
        c = ci[(r['instance_id'], r['model'])]
        out.append({'key': k, 'question': c['question'], 'gold': c['gold'],
                    'control': extract_answer(raw.get('control/' + k) or ''),
                    'restore': extract_answer(raw.get('restore/' + k) or '')})
    return out


def restore():
    OUT.mkdir(parents=True, exist_ok=True)
    spec = load_prompt()
    summary = json.loads((OUT / 'validation_summary.json').read_text())
    if not summary['gate_pass']:
        raise SystemExit('validation gate failed; restore subset not scored')
    cases = restore_cases()
    done = set()
    if (OUT / 'restore_results.jsonl').exists():
        done = {json.loads(l)['key'] for l in (OUT / 'restore_results.jsonl').read_text().splitlines() if l.strip()}
    total = spent()
    for c in cases:
        for arm in ('control', 'restore'):
            key = f"{arm}:{c['key']}"
            if key in done:
                continue
            ans = c[arm]
            rec, total = call(key, c['question'], c['gold'], ans if ans.strip() else '(empty)', spec, total)
            if rec is None:
                print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
                return
            with (OUT / 'restore_results.jsonl').open('a') as f:
                f.write(json.dumps({'key': c['key'], 'arm': arm, 'answer': ans, 'verdict': rec['verdict'],
                                    'gold': c['gold']}, ensure_ascii=False) + '\n')
    print(json.dumps({'spent': round(spent(), 6)}))


def report():
    rows = [json.loads(l) for l in (OUT / 'restore_results.jsonl').read_text().splitlines() if l.strip()]
    n = len({r['key'] for r in rows})
    eq = {arm: sum(1 for r in rows if r['arm'] == arm and r['verdict'] == 'EQUIVALENT') for arm in ('control', 'restore')}
    pairs = {}
    for r in rows:
        pairs.setdefault(r['key'], {})[r['arm']] = r['verdict'] == 'EQUIVALENT'
    improved = sum(1 for p in pairs.values() if p['restore'] and not p['control'])
    worse = sum(1 for p in pairs.values() if p['control'] and not p['restore'])
    print(json.dumps({'n': n, 'control_equiv': eq['control'], 'restore_equiv': eq['restore'],
                      'improved': improved, 'worse': worse, 'unparsed': sum(1 for r in rows if r['verdict'] is None)},
                     indent=1))


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--validate', action='store_true')
    g.add_argument('--restore', action='store_true')
    g.add_argument('--report', action='store_true')
    a = ap.parse_args()
    if a.validate:
        validate()
    elif a.restore:
        restore()
    else:
        report()


if __name__ == '__main__':
    main()
