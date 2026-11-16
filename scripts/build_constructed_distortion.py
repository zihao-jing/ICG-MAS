"""Constructed distortion cases (option C).

Take a trace whose answer is correct and whose board carries the critical fact
faithfully. Have the labeller choose one verbatim source span that contradicts
that fact, then have it confirm the contradiction. A case is accepted only if
the span is verbatim in the trace's sources, the confirmation says the span
contradicts the fact, and the span is not the question, a header or a refusal.

The constructed case is a controlled intervention: the accepted span replaces
the faithful unit, creating a distorted board; the base board is the control.
Every output labels the case "constructed".

    ./run.sh python -m scripts.build_constructed_distortion --cases
    ./run.sh python -m scripts.build_constructed_distortion --run --limit 10 --cap-usd 0.20
    ./run.sh python -m scripts.build_constructed_distortion --report
    ./run.sh python -m scripts.build_constructed_distortion --sample 10
"""
import argparse
import hashlib
import json
import math
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from utility.apis.base import APIRequest
from scripts.pilot_llm_labeller import MODEL_OPENROUTER, PRICE_IN, PRICE_OUT
from src.audit.e4_fix_gates import content, recall, toks
from src.protocols.base import is_refusal

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261112_constructed_distortion'
CONSTRUCT = OUT / 'construct_prompt_v1.json'
CONSTRUCT_MANIFEST = OUT / 'construct_prompt_v1.manifest.json'
CONFIRM = OUT / 'confirm_prompt_v1.json'
CONFIRM_MANIFEST = OUT / 'confirm_prompt_v1.manifest.json'
CASES = OUT / 'candidate_cases.jsonl'
ACCEPTED = OUT / 'cases.jsonl'
CALLS = OUT / 'calls.jsonl'
REPORT = OUT / 'report.md'
MAX_TOKENS = 500
WORKERS = 8


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(spec_path, man_path):
    raw = spec_path.read_bytes()
    spec = json.loads(raw)
    man = json.loads(man_path.read_text())
    assert hashlib.sha256(spec['system'].encode()).hexdigest() == spec['system_sha256']
    assert spec['system_sha256'] == man['system_sha256']
    assert hashlib.sha256(raw).hexdigest() == man['file_sha256']
    assert spec['model'] == MODEL_OPENROUTER
    return spec


def digest(parts):
    return hashlib.sha256('|'.join(map(str, parts)).encode()).hexdigest()


# ------------------------------------------------------------------ candidates
def candidates(limit=None):
    from scripts.run_expansion_stage2 import packages
    recs = []
    for p in sorted((ROOT / 'rebuttal/results/batch1/expansion_stage2/matcher').glob('*.json')):
        recs.append(json.loads(p.read_text()))
    pk = {}
    out, seen = [], set()
    for rec in recs:
        if rec.get('diagnosis') != 'correct_control':
            continue
        model, inst = rec['model'], rec['instance_id']
        if inst in seen:
            continue
        if model not in pk:
            pk[model] = packages(model)
        p = pk[model].get(inst)
        if not p:
            continue
        board = p['checkpoints']['board']
        unit_by_id = {u['unit_id']: u for u in board}
        gold = p['gold_answer']
        facts = {f['fact_id']: f['text'] for f in rec['facts']['facts']}
        gtok = content(str(gold))
        best = None
        for c in rec['carriers']['facts']:
            fid = c['fact_id']
            if fid not in facts:
                continue
            for u in c.get('board') or []:
                if u.get('fidelity') != 'faithful':
                    continue
                for uid in u.get('unit_ids') or []:
                    unit = unit_by_id.get(uid)
                    if not unit or not unit.get('text'):
                        continue
                    text = unit['text']
                    share = (len(gtok & content(text)) / len(gtok)) if gtok else 0.0
                    score = (share, len(content(text) & content(facts[fid])))
                    if best is None or score > best[0]:
                        best = (score, fid, uid, unit)
        if not best:
            continue
        _, fid, uid, unit = best
        contexts = p['source_contexts']
        row = {'key': digest(['constructed', inst, model, uid]),
               'instance_id': inst, 'model': model,
               'question': p['question'], 'gold_answer': gold,
               'fact_id': fid, 'fact': facts[fid],
               'unit_id': uid, 'unit_text': unit['text'],
               'unit_agent': unit.get('agent_id'),
               'contexts': [{'agent_id': c.get('agent_id'), 'text': c['text']}
                            for c in contexts]}
        out.append(row)
        seen.add(inst)
        if limit and len(out) >= limit:
            break
    OUT.mkdir(parents=True, exist_ok=True)
    with CASES.open('w') as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    chars = [len(render_construct(r)) for r in out]
    print(json.dumps({'candidates': len(out), 'mean_chars': round(sum(chars) / max(1, len(chars))),
                      'est_usd': round(sum(math.ceil(c / 4) for c in chars) * PRICE_IN
                                       + len(out) * 0.0003, 4),
                      'cases_sha256': sha(CASES)}, indent=1))
    return out


def render_construct(row):
    docs = []
    for c in row['contexts']:
        docs.append(f"[agent-{c['agent_id']}]\n{c['text'][:6000]}")
    return ('\n'.join([
        f"QUESTION\n{row['question']}",
        f"\nGOLD ANSWER\n{row['gold_answer']}",
        f"\nCRITICAL FACT ({row['fact_id']})\n{row['fact']}",
        f"\nFAITHFUL BOARD UNIT THAT WILL BE REPLACED\n{row['unit_text']}",
        "\nSOURCE DOCUMENTS\n" + '\n\n'.join(docs),
    ]))


def render_confirm(row, span):
    return ('\n'.join([
        f"QUESTION\n{row['question']}",
        f"\nGOLD ANSWER\n{row['gold_answer']}",
        f"\nCRITICAL FACT ({row['fact_id']})\n{row['fact']}",
        f"\nFAITHFUL BOARD UNIT\n{row['unit_text']}",
        f"\nCANDIDATE SPAN\n{span}",
    ]))


# ----------------------------------------------------------------------- gate
def norm_ws(s):
    return ' '.join(unicodedata.normalize('NFKC', s).split())


def verbatim(span, contexts):
    """Exact substring, else a whitespace-insensitive match returning the
    original text. Returns (found, source_text)."""
    for text in contexts:
        if span and span in text:
            return True, span
    want = norm_ws(span)
    for text in contexts:
        i = norm_ws(text).find(want)
        if want and i >= 0:
            # return the span as it appears, normalised only for whitespace
            words = want.split(' ')
            raw = text.split()
            for j in range(len(raw)):
                if norm_ws(' '.join(raw[j:j + len(words)])) == want:
                    return True, ' '.join(raw[j:j + len(words)])
    return False, None


def gate(row, span, confirmed, found, reason):
    checks = {}
    checks['span'] = bool(span)
    checks['verbatim'] = bool(found)
    checks['not_question'] = bool(span) and norm_ws(span) not in norm_ws(row['question'])
    checks['not_header'] = bool(span) and not span.lstrip().startswith('[Document:')
    checks['not_unit'] = bool(span) and norm_ws(span) != norm_ws(row['unit_text'])
    checks['not_refusal'] = bool(span) and not is_refusal(span)
    checks['confirmed'] = bool(confirmed)
    checks['long_enough'] = bool(span) and len(toks(span)) >= 8
    ok = checks['span'] and checks['verbatim'] and checks['confirmed'] and \
        checks['not_question'] and checks['not_header'] and checks['not_unit'] and \
        checks['not_refusal'] and checks['long_enough']
    return {'ok': ok, 'checks': checks, 'reason': None if ok else reason}


# ------------------------------------------------------------------ execution
def call(spec, user, meta):
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=spec['system'], user_query=user,
                     model=MODEL_OPENROUTER, max_tokens=MAX_TOKENS,
                     temperature=0, metadata=meta)
    resp = single_request(req)
    usage = resp.usage or {}
    est_in = math.ceil(len(user) / 4) + math.ceil(len(spec['system']) / 4)
    cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
            + usage.get('completion_tokens', 0) * PRICE_OUT)
    return resp, round(cost, 8)


def last_object(text):
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


def already():
    done, acc = set(), {}
    if CALLS.exists():
        for l in CALLS.read_text().splitlines():
            if not l.strip():
                continue
            r = json.loads(l)
            if r.get('event') == 'accept':
                acc[r['key']] = r
            if r.get('event') == 'reject':
                done.add(r['key'])
    return done | set(acc), acc


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines() if l.strip())


def run(rows, cap, target):
    cspec, fspec = load(CONSTRUCT, CONSTRUCT_MANIFEST), load(CONFIRM, CONFIRM_MANIFEST)
    done, acc = already()
    todo = [r for r in rows if r['key'] not in done]
    total = spent()
    print(json.dumps({'candidates': len(rows), 'already': len(done), 'accepted': len(acc),
                      'todo': len(todo), 'target': target, 'spent_usd': round(total, 6),
                      'cap_usd': cap}), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    log = CALLS.open('a')
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {}
        for r in todo:
            if len(acc) >= target:
                break
            est = math.ceil(len(render_construct(r)) / 4) * PRICE_IN + 0.0006
            if total + est > cap:
                print(json.dumps({'stop': 'cap', 'accepted': len(acc)}), flush=True)
                break
            total += est
            futs[ex.submit(construct_one, r, cspec)] = r
        for f in as_completed(futs):
            row, span, rec1 = f.result()
            log.write(json.dumps(rec1, ensure_ascii=False) + '\n')
            log.flush()
            if not span:
                log.write(json.dumps({'event': 'reject', 'key': row['key'],
                                      'stage': 'construct', 'reason': rec1.get('reason'),
                                      'cost_usd': 0.0}, ensure_ascii=False) + '\n')
                log.flush()
                continue
            found, source = verbatim(span, [c['text'] for c in row['contexts']])
            if not found:
                log.write(json.dumps({'event': 'reject', 'key': row['key'],
                                      'stage': 'verbatim', 'span': span,
                                      'cost_usd': 0.0}, ensure_ascii=False) + '\n')
                log.flush()
                continue
            resp, cost2 = none_confirm(row, source, fspec)
            parsed = last_object(resp.content or '') or {}
            confirmed = parsed.get('contradicts') is True
            log.write(json.dumps({'event': 'confirm', 'key': row['key'],
                                  'span': source, 'parsed': parsed,
                                  'success': resp.success, 'cost_usd': cost2,
                                  'raw': resp.content}, ensure_ascii=False) + '\n')
            log.flush()
            g = gate(row, source, confirmed, True, reason_for(parsed, confirmed))
            if g['ok']:
                accrec = dict(row, span=source, slot=rec1.get('slot'),
                              contradiction=rec1.get('contradicts'),
                              confirm_reason=parsed.get('reason'),
                              gate=g['checks'], constructed=True)
                with ACCEPTED.open('a') as af:
                    af.write(json.dumps(accrec, ensure_ascii=False) + '\n')
                log.write(json.dumps({'event': 'accept', 'key': row['key'],
                                      'instance_id': row['instance_id'],
                                      'model': row['model'], 'cost_usd': 0.0},
                                     ensure_ascii=False) + '\n')
                log.flush()
                acc[row['key']] = accrec
            else:
                log.write(json.dumps({'event': 'reject', 'key': row['key'],
                                      'stage': 'gate', 'gate': g['checks'],
                                      'reason': g['reason'], 'cost_usd': 0.0},
                                     ensure_ascii=False) + '\n')
                log.flush()
    log.close()
    print(json.dumps({'accepted': len(acc), 'spent_usd': round(spent(), 6)}))


def reason_for(parsed, confirmed):
    if not confirmed:
        return 'confirmation did not confirm the contradiction'
    return 'gate'


def construct_one(row, spec):
    resp, cost = call(spec, render_construct(row), {'case': row['key'],
                                                    'stage': 'construct',
                                                    'prompt_version': spec['version']})
    d = last_object(resp.content or '') or {}
    span = d.get('span') if isinstance(d.get('span'), str) else None
    rec = {'event': 'construct', 'key': row['key'], 'instance_id': row['instance_id'],
           'model': row['model'], 'span': span, 'parsed': d, 'success': resp.success,
           'cost_usd': cost, 'raw': resp.content,
           'reason': None if span else 'no span'}
    return row, span, rec


def none_confirm(row, span, spec):
    return call(spec, render_confirm(row, span), {'case': row['key'],
                                                  'stage': 'confirm',
                                                  'prompt_version': spec['version']})


# ------------------------------------------------------------------- outputs
def report():
    accs = [json.loads(l) for l in ACCEPTED.read_text().splitlines() if l.strip()] if ACCEPTED.exists() else []
    rej = [json.loads(l) for l in CALLS.read_text().splitlines()
           if l.strip() and json.loads(l).get('event') == 'reject']
    reasons = {}
    for r in rej:
        k = r.get('stage') + ': ' + str(r.get('reason'))
        reasons[k] = reasons.get(k, 0) + 1
    lines = ['# Constructed distortion cases\n',
             'Every case here is **constructed**: a faithful board unit is replaced by a '
             'verbatim source span that the labeller selected and confirmed to contradict '
             'the fact the unit carries. The base board is the control. This is a '
             'controlled intervention, not an observed model behaviour.\n',
             f"Candidates: {len([l for l in CASES.read_text().splitlines() if l.strip()])}; "
             f"accepted: **{len(accs)}**; spend ${spent():.6f}.\n",
             '| instance | model | fact | replaced unit | constructed span |',
             '| --- | --- | --- | --- | --- |']
    for a in accs:
        lines.append(f"| {a['instance_id']} | {a['model']} | {a['fact_id']} | "
                     f"{a['unit_text'][:120]} | {a['span'][:160]} |")
    lines += ['\n## Rejections\n']
    for k, n in sorted(reasons.items(), key=lambda x: -x[1]):
        lines.append(f'- {n}x {k}')
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'accepted': len(accs), 'rejections': reasons,
                      'spent_usd': round(spent(), 6)}, indent=1))


def split_sentences(text):
    out = []
    for part in re.split(r'(?<=[.!?])\s+|\n+', text):
        s = ' '.join(part.split())
        if 40 <= len(s) <= 500:
            out.append(s)
    return out


def substitution(row):
    """A verbatim sentence for a different statement, to replace the faithful
    unit (option A, constructed substitution). Prefers the same agent, then a
    sentence that shares question content, then the least overlap with the
    critical fact."""
    q = content(row['question'])
    best = []
    for c in row['contexts']:
        for s in split_sentences(c['text']):
            if s == row['unit_text'] or s in row['question']:
                continue
            if s.lower().startswith(('question:', 'you hold the following evidence')):
                continue
            if norm_ws(row['question']) in norm_ws(s):
                continue
            if s.lstrip().startswith('[Document:') or is_refusal(s) or len(toks(s)) < 8:
                continue
            r = recall(s, row['fact'])
            if r > 0.25:
                continue
            same = int(c['agent_id'] == row['unit_agent'])
            qov = len(content(s) & q)
            best.append(((same, qov, -r, len(toks(s))), s, c['agent_id'], r))
    if not best:
        return None
    best.sort(key=lambda x: x[0], reverse=True)
    _, s, agent, r = best[0]
    return {'span': s, 'agent_id': agent, 'fact_recall': round(r, 3),
            'question_overlap': len(content(s) & q)}


def show_subs(n):
    rows = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()] if CASES.exists() else candidates()
    shown = []
    for row in rows:
        sub = substitution(row)
        if not sub:
            continue
        shown.append(dict(row, substitution=sub, constructed_substitution=True))
        if len(shown) >= n:
            break
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'substitution_candidates.jsonl').write_text(
        ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in shown))
    lines = ['# Option A: constructed substitution candidates\n',
             '**Every case here is a constructed substitution.** A faithful board unit that '
             'carries the critical fact is replaced by a verbatim sentence for a different '
             'statement. The substitution is not a contradiction found in the sources; the '
             'corpus scan found only four genuine same-subject, different-value pairs, below '
             'the threshold of 30. Do not describe these as observed distortions.\n',
             f"Candidates available: {len(rows)}; shown: {len(shown)}.\n"]
    for j, r in enumerate(shown, 1):
        s = r['substitution']
        lines += [f"## {j}. {r['instance_id']} / {r['model'].split('/')[-1]} "
                  f"(constructed substitution)",
                  f"Question: {r['question']}",
                  f"Gold: {r['gold_answer']}",
                  f"Critical fact ({r['fact_id']}): {r['fact']}",
                  f"Replaced faithful unit ({r['unit_id']}, agent {r['unit_agent']}): "
                  f"{r['unit_text']}",
                  f"Substitute span (agent {s['agent_id']}, fact recall {s['fact_recall']}, "
                  f"question-token overlap {s['question_overlap']}): {s['span']}",
                  '']
    (OUT / 'substitution_candidates.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'candidates': len(rows), 'shown': len(shown),
                      'out': str((OUT / 'substitution_candidates.md').relative_to(ROOT))}, indent=1))


def sample(n):
    accs = [json.loads(l) for l in ACCEPTED.read_text().splitlines() if l.strip()]
    for a in accs[:n]:
        print('=' * 100)
        print(f"{a['instance_id']} / {a['model']} / unit {a['unit_id']} / fact {a['fact_id']}")
        print('QUESTION:', a['question'])
        print('GOLD:', a['gold_answer'])
        print('FACT:', a['fact'])
        print('REPLACED FAITHFUL UNIT:', a['unit_text'])
        print('CONSTRUCTED SPAN:', a['span'])
        print('WHY (construct):', a.get('contradiction'))
        print('WHY (confirm):', a.get('confirm_reason'))
        idx = -1
        for c in a['contexts']:
            if a['span'] in c['text']:
                t = c['text']
                i = t.find(a['span'])
                print('SOURCE [agent-%s]: ...%s...' % (c['agent_id'],
                                                       t[max(0, i - 300):i + len(a['span']) + 200]))
                break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--sample', type=int, default=0)
    ap.add_argument('--substitutions', type=int, default=0)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--target', type=int, default=30)
    ap.add_argument('--cap-usd', type=float, default=1.00)
    a = ap.parse_args()
    if a.cases:
        candidates(a.limit)
    if a.run:
        rows = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]
        run(rows, a.cap_usd, a.target)
    if a.report:
        report()
    if a.sample:
        sample(a.sample)
    if a.substitutions:
        show_subs(a.substitutions)


if __name__ == '__main__':
    main()