"""Injected distortion: corrupt one faithful board unit, labeller-confirm the
contradiction, restore it, and compare with a volume-matched faithful control.

Rule: `rebuttal/pilots/20261113_injected_distortion/INJECTED_DISTORTION_RULE_V2.md`,
frozen before any answer call. Every label says "injected distortion".

    ./run.sh python -m scripts.injected_distortion_pilot --cases
    ./run.sh python -m scripts.injected_distortion_pilot --preview --cap-usd 0.50
    ./run.sh python -m scripts.injected_distortion_pilot --pilot --cap-usd 5
    ./run.sh python -m scripts.injected_distortion_pilot --expand 30 --cap-usd 5
    ./run.sh python -m scripts.injected_distortion_pilot --report
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from scripts.missing_fact_repair_pilot import cp_ci, price
from scripts.pilot_llm_labeller import MODEL_OPENROUTER, PRICE_IN, PRICE_OUT
from scripts.answer_equiv import last_object
from scripts.run_expansion_stage2 import MODELS, MATCHER_DIR, packages
from src.audit.e4_fix_gates import covers
from src.audit.pilot_common import digest
from src.eval.evaluate import answer_f1, normalize
from src.protocols.base import extract_answer, is_refusal
from src.protocols.relay import _AGGREGATION_SYSTEM, _build_evidence_board_prompt
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_injected_distortion'
RULE = OUT / 'INJECTED_DISTORTION_RULE_V2.md'
RULE_V1 = OUT / 'INJECTED_DISTORTION_RULE.md'
CONTROL_PROMPT = OUT / 'control_prompt_v3.json'
CLASS_PROMPT = OUT / 'class_prompt_v2.json'
CLASS_MATCH = OUT / 'class_match_prompt_v2.json'
CLASS_CACHE = OUT / 'class_cache_v2.json'
CLASS_V1 = OUT / 'class_prompt_v1.json'
CLASS_MATCH_V1 = OUT / 'class_match_prompt_v1.json'
CONTROL_V2 = OUT / 'control_prompt_v2.json'
CONTROL_V1 = OUT / 'control_prompt_v1.json'
LABEL_PROMPT = OUT / 'contradiction_prompt_v1.json'
CASES = OUT / 'candidates.json'
ACCEPTED = OUT / 'accepted.json'
MANIFEST = OUT / 'prompt_manifest.json'
CALLS = OUT / 'calls.jsonl'
ANSWERS = OUT / 'answers.jsonl'
PREVIEW = OUT / 'preview.md'
REPORT = OUT / 'report.md'
EXPANSION = OUT / 'EXPANSION_30.md'
SEED = 43
MAX_UNITS = 3
ANSWER_TOKENS = 1024
LABEL_TOKENS = 300
EDIT_TOKENS = 400
EDIT_ATTEMPTS = 4
PREVIEW_N = 10
MAX_ATTEMPTS = 80
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December')

# Review round 2 (2026-11-13): five cases replaced by hand.  Cases 8 and 10
# were implausible (a politician as the career-hits holder; a school described
# as a Gothic Revival mansion), and cases 1, 2 and 6 used a person who never
# held the office the sentence names.  Each forced value is a real holder of
# that role, or a real baseball player / Toronto mansion, and still has to pass
# the same class, shape, word-count and labeller checks before acceptance.
FORCED = {
    ('3hop1__275261_443779_52195', 'gemma31b', 'board:a2:u0'): 'Xanana Gusmão',
    ('3hop1__488744_443779_52195', 'gemma31b', 'board:a2:u0'): 'Xanana Gusmão',
    ('2hop__804417_126089', 'gpt4omini', 'board:a1:u0'): 'Harry Borghouts',
    ('3hop1__617062_127905_80286', 'gemma31b', 'board:a1:u0'): 'Babe Ruth',
    ('3hop1__254856_400692_51423', 'gemma31b', 'board:a0:u0'): 'Spadina House',
}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def words(s):
    return len(str(s).split())


def ntok(s):
    return len(normalize(s))


def kind(g):
    gs = str(g).strip()
    if re.search(r'\b(' + '|'.join(MONTHS) + r')\b', gs):
        return 'date'
    if re.search(r'\d', gs):
        return 'num'
    return 'text'


def shape(g):
    """Value shape: digit runs, separators, capitalization."""
    gs = str(g)
    m = re.search(r'\d[\d,]*(?:\.\d+)?', gs)
    pre = gs[:m.start()].strip().lower() if m else ''
    post = gs[m.end():].strip().lower() if m else ''
    return (tuple(len(x) for x in re.findall(r'\d+', gs)), ',' in gs,
            '.' in gs, pre, post, gs[:1].isupper(), gs.isupper())


def numval(g):
    m = re.search(r'\d[\d,]*(?:\.\d+)?', str(g))
    return float(m.group(0).replace(',', '')) if m else None


def load_spec(path):
    spec = json.loads(path.read_text())
    assert spec['model'] == MODEL_OPENROUTER
    return spec


def build_candidates():
    recs = [json.loads(p.read_text()) for p in MATCHER_DIR.glob('*.json')]
    pk = {m: packages(m) for m in MODELS}
    rows, seen = [], set()
    for r in recs:
        if r.get('status') != 'ok':
            continue
        p = pk[r['model']][r['instance_id']]
        if not p.get('answer_correct'):
            continue
        gold = str(p['gold_answer'])
        board = p['checkpoints']['board']
        hits = [u for u in board if gold in u['text']]
        if len(hits) != 1:
            continue
        u = hits[0]
        faithful = any(b.get('fidelity') == 'faithful'
                       and u['unit_id'] in (b.get('unit_ids') or [])
                       for c in r['carriers']['facts']
                       for b in c.get('board') or [])
        if not faithful:
            continue
        key = (r['instance_id'], r['model'], u['unit_id'])
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'instance_id': r['instance_id'], 'model': r['model'],
            'unit_id': u['unit_id'], 'agent_id': u['agent_id'],
            'question': p['question'], 'gold': gold,
            'aliases': p.get('answer_aliases') or [],
            'base_answer': p['baseline_prediction'],
            'base_exact': float(p['answer_f1'] == 1.0),
            'board': [{'unit_id': x['unit_id'], 'agent_id': x['agent_id'],
                       'text': x['text']} for x in board],
            'kind': kind(gold), 'gold_tokens': ntok(gold),
            'gold_words': words(gold), 'gold_shape': shape(gold),
            'key': digest([SEED, r['instance_id'], r['model'], u['unit_id']]),
        })
    golds = sorted({str(p['gold_answer']) for m in MODELS for p in pk[m].values()})
    by_kind = {}
    for g in golds:
        by_kind.setdefault((kind(g), ntok(g), words(g), shape(g)), []).append(g)
    for row in rows:
        # Same surface type, same value shape, same normalized token count, and
        # same raw word count, so the corruption cannot change the unit's word
        # count and stays in the same value family.
        pool = [g for g in by_kind.get((row['kind'], row['gold_tokens'],
                                        row['gold_words'], row['gold_shape']), [])
                if ' '.join(normalize(g)) != ' '.join(normalize(row['gold']))]
        row['distractors'] = sorted(
            pool, key=lambda g: digest([SEED, row['instance_id'], row['model'],
                                        row['unit_id'], g]))
    rows.sort(key=lambda r: r['key'])
    OUT.mkdir(parents=True, exist_ok=True)
    assert not ANSWERS.exists(), 'refusing to rebuild after answer calls exist'
    CASES.write_text(json.dumps({
        'pool': 'expansion_stage2 all 2400 traces',
        'seed': SEED,
        'candidates': rows,
        'counts': {'candidates': len(rows),
                   'unique_instances': len({r['instance_id'] for r in rows}),
                   'with_distractor': sum(bool(r['distractors']) for r in rows)},
    }, indent=1, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_v1_sha256': file_sha(RULE_V1),
        'rule_v2_sha256': file_sha(RULE),
        'control_v1_file_sha256': file_sha(CONTROL_V1),
        'control_v1_system_sha256': sha(load_spec(CONTROL_V1)['system']),
        'control_v2_file_sha256': file_sha(CONTROL_V2),
        'control_v2_system_sha256': sha(load_spec(CONTROL_V2)['system']),
        'control_v2_note_sha256': file_sha(OUT / 'CONTROL_V2_NOTE.md'),
        'control_v3_file_sha256': file_sha(CONTROL_PROMPT),
        'control_v3_system_sha256': sha(load_spec(CONTROL_PROMPT)['system']),
        'labeller_file_sha256': file_sha(LABEL_PROMPT),
        'labeller_system_sha256': sha(load_spec(LABEL_PROMPT)['system']),
        'class_v1_file_sha256': file_sha(CLASS_V1),
        'class_v2_file_sha256': file_sha(CLASS_PROMPT),
        'class_v2_system_sha256': sha(load_spec(CLASS_PROMPT)['system']),
        'class_match_v1_file_sha256': file_sha(CLASS_MATCH_V1),
        'class_match_v2_file_sha256': file_sha(CLASS_MATCH),
        'class_match_v2_system_sha256': sha(load_spec(CLASS_MATCH)['system']),
        'class_match_note_sha256': file_sha(OUT / 'CLASS_MATCH_NOTE.md'),
        'class_match_note_v2_sha256': file_sha(OUT / 'CLASS_MATCH_NOTE_V2.md'),
        'model': MODEL_OPENROUTER, 'temperature': 0,
        'cases_sha256': file_sha(CASES), 'seed': SEED,
    }, indent=1))
    print(json.dumps({'candidates': len(rows),
                      'unique_instances': len({r['instance_id'] for r in rows}),
                      'with_distractor': sum(bool(r['distractors']) for r in rows),
                      'cases_sha256': file_sha(CASES)}, indent=1))


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') in ('result', 'skipped'))


def log(rec):
    with CALLS.open('a') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        f.flush()


def price_for(model):
    if model == MODEL_OPENROUTER:
        return PRICE_IN, PRICE_OUT
    return price(model)


def call(key, model, system, user, max_tokens, cap, total, phase):
    api_model = MODELS.get(model, model)
    pin, pout = price_for(api_model)
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * pin + max_tokens * pout
    if total + est > cap:
        log({'event': 'skipped', 'key': key, 'reason': 'cap', 'cost_usd': 0.0,
             'phase': phase})
        return None, total
    call_id = sha('|'.join([key, api_model, sha(system), sha(user), str(max_tokens)]))
    log({'event': 'intent', 'key': key, 'call_id': call_id, 'model': model,
         'api_model': api_model,
         'phase': phase, 'system_sha256': sha(system), 'user_sha256': sha(user),
         'max_tokens': max_tokens, 'temperature': 0})
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=system, user_query=user, model=api_model,
                     max_tokens=max_tokens, temperature=0,
                     metadata={'pilot': 'injected_distortion', 'key': key,
                               'phase': phase, 'openrouter_reasoning': False})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * pin
            + usage.get('completion_tokens', 0) * pout)
    log({'event': 'result', 'key': key, 'call_id': call_id, 'model': model,
         'api_model': api_model,
         'phase': phase, 'success': resp.success, 'error': resp.error,
         'content': resp.content, 'usage': usage, 'cost_usd': round(cost, 8)})
    return resp, total + cost


def gold_span(text, gold):
    """First whole-token occurrence of gold, or None."""
    i = text.find(gold)
    while i >= 0:
        j = i + len(gold)
        left = text[i - 1] if i else ' '
        right = text[j] if j < len(text) else ' '
        if not left.isalnum() and not right.isalnum():
            return i
        i = text.find(gold, i + 1)
    return None


CLASSES = ('person', 'organization', 'place', 'building', 'country',
           'university', 'language', 'work', 'role', 'event', 'award', 'year',
           'quantity', 'other')
_class_cache = None


def classify(value, context, cap, total):
    """Entity class of an answer value in its claim context; cached."""
    global _class_cache
    if _class_cache is None:
        _class_cache = json.loads(CLASS_CACHE.read_text()) if CLASS_CACHE.exists() else {}
    ck = sha(f"{value}\u0000{context}")
    if ck in _class_cache:
        return _class_cache[ck], total
    spec = load_spec(CLASS_PROMPT)
    resp, total = call(f"class/{ck[:16]}", spec['model'], spec['system'],
                       f"Claim: {context}\nValue: {value}", 120, cap, total,
                       'preview_class')
    if resp is None:
        return None, total
    d = last_object(resp.content or '')
    c = str((d or {}).get('class', '')).strip().lower()
    c = c if c in CLASSES else 'other'
    _class_cache[ck] = c
    CLASS_CACHE.write_text(json.dumps(_class_cache, indent=1, ensure_ascii=False))
    return c, total


def class_match(gold, second, cap, total):
    spec = load_spec(CLASS_MATCH)
    resp, total = call(f"classmatch/{sha(gold + '|' + second)[:16]}", spec['model'],
                       spec['system'],
                       f"First value: {gold}\nSecond value: {second}",
                       160, cap, total, 'preview_classmatch')
    if resp is None:
        return None, total
    d = last_object(resp.content or '') or {}
    ok = d.get('same_class')
    if isinstance(ok, str):
        ok = ok.strip().lower() == 'true'
    return {'same_class': ok is True,
            'gold_class': str(d.get('gold_class') or '')[:40],
            'second_class': str(d.get('second_class') or '')[:40],
            'reason': str(d.get('reason') or '')[:300]}, total


def edit_user(case, attempt):
    extra = ''
    if attempt:
        extra = (f"\nYour previous rewrite was: {case['prev']}\n"
                 f"It failed the checks: {case['why']}. Include the gold "
                 f"answer exactly as given, change no fact, and use different "
                 f"wording from the original.")
    return (f"Question: {case['question']}\n\nGold answer: {case['gold']}\n\n"
            f"Evidence sentence: {case['unit_text']}\n\n"
            f"Rewrite the evidence sentence in different words so that it "
            f"states exactly the same thing.{extra}")


def label_user(original, edited):
    return f"Original: {original}\n\nEdited: {edited}"


def verdict(raw):
    d = last_object(raw or '')
    if not isinstance(d, dict):
        return None, None
    v = str(d.get('verdict', '')).upper().replace(' ', '_')
    if v not in ('CONTRADICTION', 'NO_CONTRADICTION', 'UNCLEAR'):
        return None, None
    return v, str(d.get('reason') or '')[:300]


def make_case(cand, cap, total):
    """Paraphrase, corrupt the paraphrase, and label both; return (case, total, rejects)."""
    if not cand['distractors']:
        return None, total, [('no distractor', 'no same-type, same-length value')]
    original = next(u['text'] for u in cand['board'] if u['unit_id'] == cand['unit_id'])
    if gold_span(original, cand['gold']) is None:
        return None, total, [('gold not replaceable',
                              'no whole-token exact occurrence in the original')]
    cs = load_spec(CONTROL_PROMPT)
    reject = []
    control = None
    ucase = {**cand, 'unit_text': original, 'prev': '', 'why': ''}
    for attempt in range(EDIT_ATTEMPTS):
        resp, total = call(f"control/{cand['instance_id']}/{cand['unit_id']}/{attempt}",
                           cs['model'], cs['system'], edit_user(ucase, attempt),
                           EDIT_TOKENS, cap, total, 'preview_control')
        if resp is None:
            reject.append(('cap', 'control call skipped'))
            break
        text = None
        d = last_object(resp.content or '')
        if isinstance(d, dict) and isinstance(d.get('sentence'), str):
            text = d['sentence'].strip().strip('"').strip()
        if not text:
            text = (resp.content or '').strip().split('\n')[0].strip().strip('"')
        why = None
        if not text:
            why = 'it was empty'
        elif gold_span(text, cand['gold']) is None:
            why = 'the gold answer was missing or altered'
        elif not covers(text, cand['gold']):
            why = 'the gold answer was missing or altered'
        elif text == original:
            why = 'it copied the original wording instead of paraphrasing'
        if why is None:
            control = text
            break
        ucase['prev'], ucase['why'] = text, why
        reject.append(('control failed checks', why))
    if control is None:
        return None, total, reject or [('control rejected', '')]
    D = corrupt = cm = None
    at = gold_span(control, cand['gold'])
    if at is None:
        return None, total, reject + [('no distractor in control',
                                       'gold span missing from the control')]
    order = list(cand['distractors'])
    if cand['kind'] in ('num', 'date'):
        gv = numval(cand['gold'])
        if gv is not None:
            order.sort(key=lambda d: (abs((numval(d) if numval(d) is not None
                                           else 1e18) - gv), digest([SEED, d])))
    gold_class, total = classify(cand['gold'], original, cap, total)
    if gold_class is None:
        return None, total, reject + [('cap', 'class call skipped')]
    for d in order:
        if ' '.join(normalize(d)) in ' '.join(normalize(control)):
            continue
        dclass, total = classify(d, f"{original} [value: {d}]", cap, total)
        if dclass is None:
            return None, total, reject + [('cap', 'class call skipped')]
        if dclass != gold_class:
            continue
        text = control[:at] + d + control[at + len(cand['gold']):]
        if words(text) != words(control):
            continue
        cm, total = class_match(cand['gold'], d, cap, total)
        if cm is None:
            return None, total, reject + [('cap', 'class-match call skipped')]
        if not cm['same_class']:
            continue
        D, corrupt = d, text
        break
    if corrupt is None:
        return None, total, reject + [('no same-class distractor',
                                       f'gold class {gold_class}')]
    ls = load_spec(LABEL_PROMPT)
    resp, total = call(f"label-control/{cand['instance_id']}/{cand['unit_id']}",
                       ls['model'], ls['system'], label_user(original, control),
                       LABEL_TOKENS, cap, total, 'preview_label')
    if resp is None:
        return None, total, reject + [('cap', 'control label skipped')]
    nv, nreason = verdict(resp.content)
    if nv != 'NO_CONTRADICTION':
        return None, total, reject + [('control not confirmed', str(nv))]
    resp, total = call(f"label-corrupt/{cand['instance_id']}/{cand['unit_id']}",
                       ls['model'], ls['system'], label_user(control, corrupt),
                       LABEL_TOKENS, cap, total, 'preview_label')
    if resp is None:
        return None, total, reject + [('cap', 'corrupt label skipped')]
    cv, creason = verdict(resp.content)
    if cv != 'CONTRADICTION':
        return None, total, reject + [('corrupt not confirmed', str(cv))]
    return {
        'instance_id': cand['instance_id'], 'model': cand['model'],
        'unit_id': cand['unit_id'], 'agent_id': cand['agent_id'],
        'question': cand['question'], 'gold': cand['gold'],
        'aliases': cand['aliases'], 'base_answer': cand['base_answer'],
        'base_exact': cand['base_exact'], 'board': cand['board'],
        'original': original, 'corrupt': corrupt, 'control': control,
        'distractor': D, 'kind': cand['kind'],
        'gold_class': gold_class, 'distractor_class': cm['second_class'] or dclass,
        'class_match': True, 'class_reason': cm['reason'],
        'corrupt_verdict': cv, 'corrupt_reason': creason,
        'control_verdict': nv, 'control_reason': nreason,
        'key': cand['key'],
    }, total, reject


def accept(n_target, cap):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(CASES) == man['cases_sha256'], 'candidates changed'
    cands = json.loads(CASES.read_text())['candidates']
    data = json.loads(ACCEPTED.read_text()) if ACCEPTED.exists() else \
        {'accepted': [], 'rejected': []}
    have = {a['key'] for a in data['accepted']}
    start = len(data['rejected'])
    total = spent()
    attempts = 0
    for cand in cands:
        if len(data['accepted']) >= n_target or attempts >= MAX_ATTEMPTS:
            break
        if cand['key'] in have:
            continue
        attempts += 1
        case, total, rejects = make_case(cand, cap, total)
        for reason, detail in rejects:
            data['rejected'].append({'key': cand['key'],
                                     'instance_id': cand['instance_id'],
                                     'model': cand['model'], 'reason': reason,
                                     'detail': detail})
        if case is not None:
            data['accepted'].append(case)
            have.add(case['key'])
    data['attempts'] = data.get('attempts', 0) + attempts
    ACCEPTED.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    return data, total


def refix(cap):
    """Replace the distractor on the five reviewed cases, keeping their control."""
    data = json.loads(ACCEPTED.read_text())
    total = spent()
    for case in data['accepted']:
        k = (case['instance_id'], case['model'], case['unit_id'])
        if k not in FORCED:
            continue
        d = FORCED[k]
        control = case['control']
        at = gold_span(control, case['gold'])
        if at is None:
            raise SystemExit(f'gold span missing from control: {k}')
        text = control[:at] + d + control[at + len(case['gold']):]
        if words(text) != words(control):
            raise SystemExit(f'word count changed: {k} {words(text)} != {words(control)}')
        gold_class, total = classify(case['gold'], case['original'], cap, total)
        dclass, total = classify(d, f"{case['original']} [value: {d}]", cap, total)
        if gold_class is None or dclass is None:
            raise SystemExit(f'class call skipped: {k}')
        cm, total = class_match(case['gold'], d, cap, total)
        if cm is None:
            raise SystemExit(f'class-match call skipped: {k}')
        if dclass != gold_class or not cm['same_class']:
            raise SystemExit(f'class mismatch: {k} {gold_class} vs {dclass} {cm}')
        ls = load_spec(LABEL_PROMPT)
        resp, total = call(f"label-corrupt/{case['instance_id']}/{case['unit_id']}/forced",
                           ls['model'], ls['system'], label_user(control, text),
                           LABEL_TOKENS, cap, total, 'preview_label')
        if resp is None:
            raise SystemExit(f'label call skipped: {k}')
        cv, creason = verdict(resp.content)
        if cv != 'CONTRADICTION':
            raise SystemExit(f'forced distractor not confirmed: {k} {cv} {creason}')
        case.update({'distractor': d, 'corrupt': text, 'forced': True,
                     'gold_class': gold_class,
                     'distractor_class': cm['second_class'] or dclass,
                     'class_reason': cm['reason'],
                     'corrupt_verdict': cv, 'corrupt_reason': creason})
    ACCEPTED.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    write_preview(data)
    return data, total


def write_preview(data):
    lines = ['# Injected distortion: preview of accepted cases\n',
             'Rule: `INJECTED_DISTORTION_RULE_V2.md`; every case is an **injected '
             'distortion**. The control is a faithful paraphrase of the original '
             'unit; the corruption replaces the gold value inside that paraphrase '
             'with a wrong value of the same entity class, shape, and length, so '
             'control and corruption have identical length and differ in one '
             'span. Both were confirmed by the frozen labeller before any answer '
             'call, and the class match is confirmed separately.\n',
             f"Accepted {len(data['accepted'])} cases from "
             f"{len({c['instance_id'] for c in data['accepted']})} unique "
             f"instances; rejected {len(data['rejected'])} attempts so far. "
             f"Cases 3 and 9 are the same fact (`3hop1__773623`) on two traces "
             f"(qwen235b and gpt4omini) and are counted once in every instance "
             f"count. No answer call has been made.\n"]
    for i, c in enumerate(data['accepted'], 1):
        lines += [f"## {i}. {c['instance_id']} / {c['model']} / {c['unit_id']} "
                  f"({c['kind']})\n",
                  f"**Question:** {c['question']}",
                  f"**Gold:** {c['gold']} (base answer: {c['base_answer']})",
                  f"**Original verbatim unit:** {c['original']}",
                  f"**Corrupted (injected distortion):** {c['corrupt']}",
                  f"**Control (volume-matched faithful edit):** {c['control']}",
                  f"*Class match:* `{c['gold_class']}` -> "
                  f"`{c['distractor_class']}` — labeller confirms same class "
                  f"({c['class_reason']}).",
                  f"*Labeller:* corruption `{c['corrupt_verdict']}` — "
                  f"{c['corrupt_reason']}; control `{c['control_verdict']}` — "
                  f"{c['control_reason']}.\n"]
    if data['rejected']:
        lines += ['## Rejected attempts\n',
                  '| case | model | reason | detail |',
                  '| --- | --- | --- | --- |']
        for r in data['rejected'][:40]:
            lines.append(f"| {r['instance_id']} | {r['model']} | {r['reason']} | "
                         f"{str(r['detail'])[:80]} |")
    PREVIEW.write_text('\n'.join(lines) + '\n')


def board_user(case, board):
    n_agents = max(int(u['agent_id']) for u in board) + 1
    grouped = [[] for _ in range(n_agents)]
    for u in board:
        grouped[int(u['agent_id'])].append(str(u['text']))
    return _build_evidence_board_prompt(grouped, case['question'])


def answer_arms(cap):
    assert PREVIEW.exists(), 'run --preview first'
    data = json.loads(ACCEPTED.read_text())
    done = set()
    if ANSWERS.exists():
        for l in ANSWERS.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                done.add((r['instance_id'], r['model'], r['unit_id'], r['arm']))
    total = spent()
    for case in data['accepted']:
        for arm in ('corrupt', 'control', 'repair'):
            key = (case['instance_id'], case['model'], case['unit_id'], arm)
            if key in done:
                continue
            text = {'corrupt': case['corrupt'], 'control': case['control'],
                    'repair': case['original']}[arm]
            board = [dict(u) for u in case['board']]
            for u in board:
                if u['unit_id'] == case['unit_id']:
                    u['text'] = text
            resp, total = call(f"{case['instance_id']}/{case['model']}/"
                               f"{case['unit_id']}/{arm}", case['model'],
                               _AGGREGATION_SYSTEM, board_user(case, board),
                               ANSWER_TOKENS, cap, total, 'answer')
            if resp is None:
                continue
            ans = extract_answer(resp.content or '')
            f1 = answer_f1(ans, {'answer': case['gold'],
                                 'answer_aliases': case['aliases']})
            with ANSWERS.open('a') as f:
                f.write(json.dumps({
                    'instance_id': case['instance_id'], 'model': case['model'],
                    'unit_id': case['unit_id'], 'arm': arm, 'gold': case['gold'],
                    'answer': ans, 'refusal': is_refusal(ans),
                    'f1': round(f1, 6), 'exact': float(f1 == 1.0),
                    'raw': resp.content, 'success': resp.success,
                }, ensure_ascii=False) + '\n')
                f.flush()
    print(json.dumps({'answered': len(done), 'spent_usd': round(spent(), 8)}, indent=1))


def _ci(k, n):
    lo, hi = cp_ci(k, n)
    return f'{lo:.3f}-{hi:.3f}'


def report():
    data = json.loads(ACCEPTED.read_text())
    ans = [json.loads(l) for l in ANSWERS.read_text().splitlines() if l.strip()] \
        if ANSWERS.exists() else []
    by = {(a['instance_id'], a['model'], a['unit_id'], a['arm']): a for a in ans}
    cases = data['accepted']
    base = int(sum(c['base_exact'] for c in cases))
    lines = ['# Injected distortion: pilot report\n',
             'Rule: `INJECTED_DISTORTION_RULE_V2.md`. All cases are **injected '
             'distortions**: one faithful board unit was corrupted in place with '
             'a same-type, same-length wrong value, confirmed by the frozen '
             'labeller; the control is a volume-matched faithful rewrite, also '
             'labeller-confirmed. This is not observed distortion and not a '
             'constructed substitution.\n',
             f"Accepted {len(cases)} cases from the Stage 2 pool; "
             f"{len(data['rejected'])} candidate attempts rejected. "
             f"Spend ${spent():.6f} against the cap. "
             + (f"This is the approved ≥30-case set ({len(cases)} cases).\n"
                if len(cases) >= 30 else
                f"This is a {len(cases)}-case **pilot**, below the ≥30-case "
                f"target; it is not the full set.\n"),
             '## Exact answers by arm\n',
             '| arm | exact | n | 95% CI |',
             '| --- | ---: | ---: | --- |',
             f'| base (recorded, no call) | {base} | {len(cases)} | {_ci(base, len(cases))} |']
    for arm in ('corrupt', 'control', 'repair'):
        rows = [by[(c['instance_id'], c['model'], c['unit_id'], arm)]
                for c in cases if (c['instance_id'], c['model'], c['unit_id'],
                                   arm) in by]
        k = int(sum(a['exact'] for a in rows))
        lines.append(f'| {arm} | {k} | {len(rows)} | {_ci(k, len(rows))} |')
    lines += ['', 'Paired comparisons:\n',
              '| pair | better | worse | same |',
              '| --- | ---: | ---: | ---: |']
    for a1, a2 in (('repair', 'corrupt'), ('control', 'corrupt'),
                   ('repair', 'control')):
        b = w = s = 0
        for c in cases:
            x = by.get((c['instance_id'], c['model'], c['unit_id'], a1))
            y = by.get((c['instance_id'], c['model'], c['unit_id'], a2))
            if x is None or y is None:
                continue
            if x['exact'] > y['exact']:
                b += 1
            elif x['exact'] < y['exact']:
                w += 1
            else:
                s += 1
        lines.append(f'| {a1} vs {a2} | {b} | {w} | {s} |')
    lines += ['', '## Per case\n',
              '| case | model | gold | original unit | corrupted unit | control unit | base | corrupt | control | repair |',
              '| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |']
    for c in cases:
        def ex(arm):
            a = by.get((c['instance_id'], c['model'], c['unit_id'], arm))
            return a['exact'] if a else 0
        lines.append(f"| {c['instance_id']} | {c['model'].split('/')[-1]} | "
                     f"{str(c['gold'])[:35]} | {c['original'][:55]} | "
                     f"{c['corrupt'][:55]} | {c['control'][:55]} | "
                     f"{c['base_exact']:.0f} | {ex('corrupt'):.0f} | "
                     f"{ex('control'):.0f} | {ex('repair'):.0f} |")
    lines += ['', '## Cost by stage\n']
    stages = {}
    if CALLS.exists():
        for l in CALLS.read_text().splitlines():
            r = json.loads(l)
            if r.get('event') == 'result':
                stages[r['phase']] = stages.get(r['phase'], 0.0) + r.get('cost_usd', 0.0)
    for k, v in sorted(stages.items()):
        lines.append(f'- {k}: ${v:.6f}')
    lines += ['', '## Reading\n',
              'A drop from base/repair to corrupt with the control near base is '
              'the injected-distortion effect. A corrupt answer that stays exact '
              'means the answerer did not use the corrupted unit.\n',
              'One case (3hop1__254856_400692_51423, Casa Loma) refused '
              '("Insufficient information") on all three arms, control and '
              'repair included, although its base answered correctly. Its '
              'corrupt failure is therefore an edit/volume effect on that trace, '
              'not evidence that the corruption changed the answer; read the '
              f'arms on the other {len(cases) - 1} cases for the '
              'injected-distortion effect.']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'accepted': len(cases), 'base': base,
                      'spent_usd': round(spent(), 8)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', action='store_true')
    ap.add_argument('--preview', action='store_true')
    ap.add_argument('--refix', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--expand', type=int, default=0)
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=5.0)
    a = ap.parse_args()
    if a.cases:
        build_candidates()
    if a.preview:
        data, total = accept(PREVIEW_N, a.cap_usd)
        write_preview(data)
        print(json.dumps({'accepted': len(data['accepted']),
                          'rejected_attempts': len(data['rejected']),
                          'spent_usd': round(total, 8)}, indent=1))
    if a.refix:
        data, total = refix(a.cap_usd)
        print(json.dumps({'accepted': len(data['accepted']),
                          'unique_instances': len({c['instance_id']
                                                   for c in data['accepted']}),
                          'spent_usd': round(total, 8)}, indent=1))
    if a.pilot:
        answer_arms(a.cap_usd)
    if a.expand:
        man = json.loads(MANIFEST.read_text())
        assert file_sha(EXPANSION) == man['expansion_30_sha256'], 'expansion changed'
        data, total = accept(a.expand, a.cap_usd)
        write_preview(data)
        print(json.dumps({'accepted': len(data['accepted']),
                          'rejected_attempts': len(data['rejected']),
                          'spent_usd': round(total, 8)}, indent=1))
    if a.report:
        report()


if __name__ == '__main__':
    main()