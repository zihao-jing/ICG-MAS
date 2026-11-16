"""B6: audit-guided extraction repairs and re-routed sharding on the 59 missing-fact cases.

Rule `rebuttal/pilots/prereg/B6-audit-guided-repairs.md`, frozen before any call. Cap $5, chunks <= $1.

    ./run.sh python -m scripts.b6_repairs --build
    ./run.sh python -m scripts.b6_repairs --run
    ./run.sh python -m scripts.b6_repairs --score
"""
import argparse
import hashlib
import json
import math
import random
import time
from collections import Counter
from pathlib import Path

from scripts.audit_diagnosis_89 import packages, records
from scripts.answer_equiv import last_object
from src.audit.e4_fix_gates import delivery_gate, recall
from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer
from src.protocols.relay import (_AGGREGATION_SYSTEM, _EXTRACTION_SYSTEM,
                                 _build_evidence_board_prompt, _build_extraction_prompt,
                                 _parse_units)
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_b6_repairs'
RULE = ROOT / 'rebuttal/pilots/prereg/B6-audit-guided-repairs.md'
AMENDMENT = ROOT / 'rebuttal/pilots/prereg/B6-amendment-2.md'
AMEND_MANIFEST = OUT / 'amendment_manifest.json'
PASS1 = OUT / 'results_sharding_pass1.jsonl'
CONTROL = OUT / 'control.jsonl'
SENS_RULE = ROOT / 'rebuttal/pilots/prereg/B6-amendment-3.md'
SENS = OUT / 'sensitivity.jsonl'
SENS_RECALL = 0.5
AMEND4 = ROOT / 'rebuttal/pilots/prereg/B6-amendment-4.md'
COMBINE = OUT / 'combine.jsonl'
AMEND5 = ROOT / 'rebuttal/pilots/prereg/B6-amendment-5.md'
VERBATIM = OUT / 'verbatim.jsonl'
VERB_SYSTEM = ('You quote evidence verbatim. Copy sentences exactly as they appear; never paraphrase, '
               'summarise, or add words.')
AMEND6 = ROOT / 'rebuttal/pilots/prereg/B6-amendment-6.md'
BRIDGE = OUT / 'bridge.jsonl'
BRIDGE_SYSTEM = ('You quote evidence verbatim. Copy sentences exactly as they appear; never paraphrase, '
                 'summarise, or add words. Quote every sentence the question\'s reasoning chain needs, '
                 'including sentences about intermediate entities, even when they do not mention an entity '
                 'named in the question. Do not screen sentences out for irrelevance.')


def bridge_user(passage, question, k=5):
    return ('%s\n\nQuestion: %s\n\nQuote up to %d sentences the question\'s reasoning chain needs, including '
            'bridge sentences about intermediate entities that do not appear in the question. Copy each one '
            'exactly. Number them 1..%d.' % (passage, question, k, k))


def verb_user(passage, question, k=3):
    return ('%s\n\nQuestion: %s\n\nQuote up to %d sentences from the passage that bear on the question. '
            'Copy each one exactly. Number them 1..%d.' % (passage, question, k, k))
CASES = ROOT / 'rebuttal/pilots/20261113_attribution_comparison/cases_v2.json'
AUDIT = ROOT / 'rebuttal/pilots/20261113_audit_diagnosis_89/audit_results.json'
POP = OUT / 'cases.json'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
SCORE = OUT / 'score.json'
REPORT = OUT / 'report.md'
MODEL_IDS = {'qwen235b': 'qwen/qwen3-235b-a22b-2507',
             'gemma31b': 'google/gemma-4-31b-it',
             'gpt4omini': 'openai/gpt-4o-mini'}
PRICE = {MODEL_IDS['qwen235b']: (0.14 / 1e6, 0.8 / 1e6),
         MODEL_IDS['gemma31b']: (0.14 / 1e6, 0.4 / 1e6),
         MODEL_IDS['gpt4omini']: (0.15 / 1e6, 0.6 / 1e6)}
MAX_UNITS = 3
EXTRACT_TOKENS = 512
ANSWER_TOKENS = 1024
CAP = 5.0
CHUNK = 0.9
SEED = 43


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def call(key, model, system, user, max_tokens, cap, total):
    pin, pout = PRICE[model]
    est_in = math.ceil((len(system) + len(user)) / 4)
    if total + est_in * pin + max_tokens * pout > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                'cost_usd': 0.0}) + '\n')
        return None, total
    cid = sha('|'.join([key, system, user, str(max_tokens)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid, 'model': model,
                            'system_sha256': sha(system), 'user_sha256': sha(user),
                            'max_tokens': max_tokens, 'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=system, user_query=user, model=model,
                     max_tokens=max_tokens, temperature=0,
                     metadata={'pilot': 'b6_repairs', 'key': key})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * pin + usage.get('completion_tokens', 0) * pout
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid, 'model': model,
                            'success': resp.success, 'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def build():
    cases = [c for c in json.loads(CASES.read_text()) if c['population'] == 'cohort']
    audit = {r['key']: r for r in json.loads(AUDIT.read_text())['items']}
    recs = records()
    rows = []
    for c in cases:
        model, inst = c['key'].split('/')[1], c['key'].split('/')[2]
        a = audit.get(c['key'])
        if not a:
            continue
        detail = a.get('facts') or {}
        for fid, d in detail.items():
            fr = next((f for f in recs[(model, inst)]['facts']['facts'] if f['fact_id'] == fid), None)
            if fr is None:
                continue
            rows.append({'key': c['key'], 'fact_id': fid, 'stage': c['known_stage'],
                         'model': model, 'instance': inst, 'fact_text': fr['text'],
                         'source_ids': fr['source_ids'], 'shards': d.get('shards', []),
                         'fact_label': d.get('label')})
    OUT.mkdir(parents=True, exist_ok=True)
    POP.write_text(json.dumps(rows, ensure_ascii=False))
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE),
           'audit_sha256': file_sha(AUDIT), 'cases_sha256': file_sha(CASES),
           'population_sha256': file_sha(POP), 'cases': len(rows),
           'by_stage': dict(Counter(r['stage'] for r in rows)),
           'models': MODEL_IDS, 'cap_usd': CAP, 'chunk_usd': CHUNK,
           'extract_prompt_sha256': sha(_EXTRACTION_SYSTEM),
           'answer_prompt_sha256': sha(_AGGREGATION_SYSTEM)}
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def check_frozen():
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(POP) == man['population_sha256'], 'population changed'
    if AMEND_MANIFEST.exists():
        a = json.loads(AMEND_MANIFEST.read_text())
        assert file_sha(AMENDMENT) == a['amendment_sha256'], 'amendment changed'
        if a.get('amendment3_sha256'):
            assert file_sha(SENS_RULE) == a['amendment3_sha256'], 'amendment 3 changed'
    return man


def input_passage(row, pkg):
    """Extraction input: owner's own passage (extraction), the carrying passage (sharding)."""
    if row['stage'] == 'sharding':
        sup = sorted(pkg['source_supports'], key=lambda s: (-recall(s['text'], row['fact_text']),
                                                            str(s['agent_id'])))
        return sup[0]['text']
    owner = owners(row)[0]
    return next((s['text'] for s in pkg['source_supports'] if str(s['agent_id']) == owner), '')


def split_pass1():
    """Move pass-1 sharding rows out of results.jsonl; keep every call record untouched."""
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    old = [r for r in rows if r['stage'] == 'sharding']
    keep = [r for r in rows if r['stage'] != 'sharding']
    with PASS1.open('a') as f:
        for r in old:
            f.write(json.dumps({**r, 'pass': 1, 'note': 'owner passage input; superseded by amendment 2'},
                               ensure_ascii=False) + '\n')
    RESULTS.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in keep))
    AMEND_MANIFEST.write_text(json.dumps({'amendment_sha256': file_sha(AMENDMENT),
                                          'parent_rule_sha256': file_sha(RULE),
                                          'sharding_input': 'max gate recall over source_supports',
                                          'control': 'aggregate unchanged board for delivered cases',
                                          'moved_pass1_sharding_rows': len(old)},
                                         indent=1))
    print(json.dumps({'moved': len(old), 'kept': len(keep), 'amendment_sha256': file_sha(AMENDMENT)[:12]}))


def board_by_agent(pkg):
    by = {}
    for u in pkg['checkpoints']['board']:
        by.setdefault(str(u['agent_id']), []).append(u['text'])
    return by


def owners(row):
    """Owner agent ids: the audit's shards for the slot, else the fact's source ids."""
    out = []
    for s in row['shards'] or row['source_ids']:
        s = str(s)
        out.append(s.split('-')[-1] if s.startswith('agent-') else s.split(':')[-1])
    return list(dict.fromkeys(out))


def run():
    man = check_frozen()
    rows = json.loads(POP.read_text())
    pk = {m: packages(m) for m in MODEL_IDS}
    done = ({json.loads(l)['key'] for l in RESULTS.read_text().splitlines() if l.strip()}
            if RESULTS.exists() else set())
    todo = [r for r in rows if r['key'] not in done]
    total = spent()
    chunk, start = 1, total
    print(json.dumps({'todo': len(todo), 'done': len(done), 'spent': round(total, 6),
                      'chunk': chunk, 'chunk_start': round(start, 6)}), flush=True)
    for row in todo:
        if total - start > CHUNK:
            over = total - start > 1.0
            print(json.dumps({'chunk': chunk, 'chunk_spend': round(total - start, 6),
                              'overrun': over}), flush=True)
            if over:
                print(json.dumps({'stop': 'chunk overrun'}))
                break
            chunk += 1
            start = total
            print(json.dumps({'chunk': chunk, 'start': round(start, 6)}), flush=True)
        pkg = pk[row['model']][row['instance']]
        owner = owners(row)[0]
        shard_text = input_passage(row, pkg)
        if not shard_text:
            with RESULTS.open('a') as f:
                f.write(json.dumps({**row, 'status': 'no_shard_text'}) + '\n')
            continue
        model = MODEL_IDS[row['model']]
        user = _build_extraction_prompt(shard_text, pkg['question'], MAX_UNITS)
        resp, total = call(f"extract/{row['key']}/{row['fact_id']}", model, _EXTRACTION_SYSTEM,
                           user, EXTRACT_TOKENS, CAP, total)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        units = _parse_units(resp.content or '', MAX_UNITS) if resp.success else []
        delivered = [u for u in units if delivery_gate(u, row['fact_text'], pkg['question'])['ok']]
        rec = {**row, 'n_units': len(units), 'n_delivered': len(delivered),
               'status': 'delivered' if delivered else 'undelivered'}
        if delivered:
            by = board_by_agent(pkg)
            by.setdefault(owner, []).extend(delivered)
            order = sorted(by, key=lambda x: (len(x), x))
            prompt = _build_evidence_board_prompt([by[a] for a in order], pkg['question'])
            resp2, total = call(f"answer/{row['key']}/{row['fact_id']}", model,
                                _AGGREGATION_SYSTEM, prompt, ANSWER_TOKENS, CAP, total)
            if resp2 is None:
                print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
                break
            ans = extract_answer(resp2.content or '') if resp2.success else ''
            rec['repair_answer'] = ans
            rec['repair_f1'] = answer_f1(ans, {'answer': pkg['gold_answer']})
            rec['repair_correct'] = rec['repair_f1'] >= 1.0
        rec['orig_f1'] = answer_f1(str(pkg['baseline_prediction']), {'answer': pkg['gold_answer']})
        rec['orig_correct'] = rec['orig_f1'] >= 1.0
        with RESULTS.open('a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print(json.dumps({'key': row['key'], 'fid': row['fact_id'], 'stage': row['stage'],
                          'delivered': len(delivered), 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'chunks': chunk, 'spent': round(spent(), 6)}), flush=True)


def control():
    """Amendments 2: aggregate the unchanged board for every delivered case."""
    man = check_frozen()
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    delivered = [r for r in rows if r['status'] == 'delivered']
    done = ({json.loads(l)['key'] for l in CONTROL.read_text().splitlines() if l.strip()}
            if CONTROL.exists() else set())
    pk = {m: packages(m) for m in MODEL_IDS}
    total = spent()
    print(json.dumps({'control_todo': len([r for r in delivered if r['key'] not in done]),
                      'spent': round(total, 6)}), flush=True)
    for r in delivered:
        if r['key'] in done:
            continue
        pkg = pk[r['model']][r['instance']]
        by = board_by_agent(pkg)
        order = sorted(by, key=lambda x: (len(x), x))
        prompt = _build_evidence_board_prompt([by[a] for a in order], pkg['question'])
        resp, total = call(f"control/{r['key']}/{r['fact_id']}", MODEL_IDS[r['model']],
                           _AGGREGATION_SYSTEM, prompt, ANSWER_TOKENS, CAP, total)
        if resp is None:
            break
        ans = extract_answer(resp.content or '') if resp.success else ''
        f1 = answer_f1(ans, {'answer': pkg['gold_answer']})
        with CONTROL.open('a') as f:
            f.write(json.dumps({'key': r['key'], 'fact_id': r['fact_id'], 'stage': r['stage'],
                                'control_answer': ans, 'control_f1': f1,
                                'control_correct': f1 >= 1.0},
                               ensure_ascii=False) + '\n')
        print(json.dumps({'control': r['key'], 'correct': f1 >= 1.0,
                          'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


def sensitivity():
    """Amendment 3: deliver stored units at recall >= 0.5 (post-hoc threshold, sensitivity only)."""
    check_frozen()
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    done = ({json.loads(l)['key'] for l in SENS.read_text().splitlines() if l.strip()}
            if SENS.exists() else set())
    calls = ({json.loads(l)['key']: json.loads(l) for l in CALLS.read_text().splitlines()
              if l.strip() and '"result"' in l and 'extract/' in l})
    pk = {m: packages(m) for m in MODEL_IDS}
    total = spent()
    for r in rows:
        if r['status'] != 'undelivered' or r['key'] in done:
            continue
        pkg = pk[r['model']][r['instance']]
        rec = calls.get("extract/%s/%s" % (r['key'], r['fact_id']))
        units = _parse_units((rec or {}).get('content') or '', MAX_UNITS)
        pick = [u for u in units if recall(u, r['fact_text']) >= SENS_RECALL]
        out = {**r, 'sens_units': len(pick), 'sens_status': 'delivered' if pick else 'no_unit',
               'orig_f1': r['orig_f1'], 'orig_correct': r['orig_correct']}
        if pick:
            by = board_by_agent(pkg)
            owner = owners(r)[0]
            by.setdefault(owner, []).extend(pick)
            order = sorted(by, key=lambda x: (len(x), x))
            prompt = _build_evidence_board_prompt([by[a] for a in order], pkg['question'])
            resp, total = call(f"sens/{r['key']}/{r['fact_id']}", MODEL_IDS[r['model']],
                               _AGGREGATION_SYSTEM, prompt, ANSWER_TOKENS, CAP, total)
            if resp is None:
                break
            ans = extract_answer(resp.content or '') if resp.success else ''
            out['sens_answer'] = ans
            out['sens_f1'] = answer_f1(ans, {'answer': pkg['gold_answer']})
            out['sens_correct'] = out['sens_f1'] >= 1.0
        with SENS.open('a') as f:
            f.write(json.dumps(out, ensure_ascii=False) + '\n')
        print(json.dumps({'sens': r['key'], 'stage': r['stage'], 'units': len(pick),
                          'spent': round(total, 6)}), flush=True)


def boot(pairs, seed=SEED, draws=2000):
    by = {}
    for a, b, inst in pairs:
        by.setdefault(inst, []).append(a - b)
    keys = sorted(by)
    rng = random.Random(seed)
    out = []
    for _ in range(draws):
        vals = [v for _ in range(len(keys)) for v in by[rng.choice(keys)]]
        out.append(sum(vals) / len(vals))
    out.sort()
    d = sum(a - b for a, b, _ in pairs) / len(pairs)
    return d, out[int(0.025 * draws)], out[int(0.975 * draws) - 1]


def fact_in_input(rows):
    """Does the passage the extraction saw carry the flagged fact? Delivered extraction cases only."""
    pk = {m: packages(m) for m in MODEL_IDS}
    vals = []
    for r in rows:
        if r['status'] != 'delivered' or r['stage'] != 'extraction':
            continue
        pkg = pk[r['model']][r['instance']]
        vals.append(recall(input_passage(r, pkg), r['fact_text']))
    return {'n': len(vals), 'ge80': sum(v >= 0.8 for v in vals), 'ge50': sum(v >= 0.5 for v in vals)}


def copied_summary(rows):
    """How much of each delivered unit is carried by the passage it was extracted from."""
    if not CALLS.exists():
        return {'n': 0, 'ge80': 0, 'ge50': 0}
    calls = ({json.loads(l)['key']: json.loads(l) for l in CALLS.read_text().splitlines()
              if l.strip() and '"result"' in l and 'extract/' in l})
    pk = {m: packages(m) for m in MODEL_IDS}
    vals = []
    for r in rows:
        if r['status'] != 'delivered':
            continue
        pkg = pk[r['model']][r['instance']]
        key = "extract/%s/%s" % (r['key'], r['fact_id'])
        rec = calls.get(key)
        if not rec:
            continue
        text = input_passage(r, pkg)
        units = _parse_units(rec.get('content') or '', MAX_UNITS)
        vals += [recall(text, u) for u in units if delivery_gate(u, r['fact_text'], pkg['question'])['ok']]
    return {'n': len(vals), 'ge80': sum(v >= 0.8 for v in vals), 'ge50': sum(v >= 0.5 for v in vals)}


def full_context(pkg):
    parts = []
    for s in pkg['source_supports']:
        title = (s.get('title') or '').strip()
        parts.append(('[Document: %s]\n' % title if title else '') + s['text'])
    return '\n\n'.join(parts)


def combine():
    """Amendment 4: full-evidence routing for the 20 sharding cases."""
    check_frozen()
    man = json.loads(AMEND_MANIFEST.read_text())
    assert file_sha(AMEND4) == man.get('amendment4_sha256'), 'amendment 4 changed'
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    sharding = [r for r in rows if r['stage'] == 'sharding']
    done = ({json.loads(l)['key'] for l in COMBINE.read_text().splitlines() if l.strip()}
            if COMBINE.exists() else set())
    pk = {m: packages(m) for m in MODEL_IDS}
    total = spent()
    for r in sharding:
        if r['key'] in done:
            continue
        pkg = pk[r['model']][r['instance']]
        model = MODEL_IDS[r['model']]
        user = _build_extraction_prompt(full_context(pkg), pkg['question'], MAX_UNITS)
        resp, total = call(f"combine/extract/{r['key']}/{r['fact_id']}", model,
                           _EXTRACTION_SYSTEM, user, EXTRACT_TOKENS, CAP, total)
        if resp is None:
            break
        units = _parse_units(resp.content or '', MAX_UNITS) if resp.success else []
        delivered = [u for u in units if delivery_gate(u, r['fact_text'], pkg['question'])['ok']]
        rec = {'key': r['key'], 'fact_id': r['fact_id'], 'stage': r['stage'],
               'fact_text': r['fact_text'], 'n_units': len(units),
               'n_delivered': len(delivered),
               'status': 'delivered' if delivered else 'undelivered',
               'orig_f1': r['orig_f1'], 'orig_correct': r['orig_correct']}
        if delivered:
            by = board_by_agent(pkg)
            by.setdefault(owners(r)[0], []).extend(delivered)
            order = sorted(by, key=lambda x: (len(x), x))
            prompt = _build_evidence_board_prompt([by[a] for a in order], pkg['question'])
            resp2, total = call(f"combine/answer/{r['key']}/{r['fact_id']}", model,
                                _AGGREGATION_SYSTEM, prompt, ANSWER_TOKENS, CAP, total)
            if resp2 is None:
                break
            ans = extract_answer(resp2.content or '') if resp2.success else ''
            rec['answer'] = ans
            rec['f1'] = answer_f1(ans, {'answer': pkg['gold_answer']})
            rec['correct'] = rec['f1'] >= 1.0
        with COMBINE.open('a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print(json.dumps({'combine': r['key'], 'delivered': len(delivered),
                          'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


def combine_score():
    from scripts.missing_fact_repair_pilot import cp_ci
    rows = [json.loads(l) for l in COMBINE.read_text().splitlines() if l.strip()]
    d = [r for r in rows if r['status'] == 'delivered']
    k, n = len(d), len(rows)
    lo, hi = cp_ci(k, n) if n else (0.0, 0.0)
    out = {'n': n, 'delivered': k, 'delivered_ci': [lo, hi],
           'undelivered': n - k, 'spend_usd': round(spent(), 6)}
    if d:
        p = [(int(r['correct']), int(r['orig_correct'])) for r in d]
        out['correct'] = {'repaired': sum(a for a, _ in p), 'original': sum(b for _, b in p),
                          'diff': boot([(a, b, 'x') for a, b in p])[0],
                          'diff_ci': list(boot([(a, b, 'x') for a, b in p])[1:])}
    return out


def shard_support(rows):
    """For each sharding case, the best gate recall of the flagged fact in any supplied passage."""
    pk = {m: packages(m) for m in MODEL_IDS}
    out = []
    for r in rows:
        if r['stage'] != 'sharding':
            continue
        pkg = pk[r['model']][r['instance']]
        best = max(pkg['source_supports'],
                   key=lambda s: (recall(s['text'], r['fact_text']), -int(s['agent_id'])))
        out.append({'key': r['key'], 'fact': r['fact_text'],
                    'best_recall': round(recall(best['text'], r['fact_text']), 3),
                    'passage_agent': best['agent_id']})
    out.sort(key=lambda x: -x['best_recall'])
    return {'n': len(out), 'stated_ge80': sum(x['best_recall'] >= 0.8 for x in out),
            'unsupported': sum(x['best_recall'] < 0.8 for x in out), 'cases': out}


def verbatim():
    """Amendment 5: verbatim quotation extraction on the six supported sharding cases."""
    check_frozen()
    man = json.loads(AMEND_MANIFEST.read_text())
    assert file_sha(AMEND5) == man.get('amendment5_sha256'), 'amendment 5 changed'
    assert sha(VERB_SYSTEM + '|' + verb_user('P', 'Q')) == man.get('verbatim_prompt_sha256'), 'verbatim prompt changed'
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    sup = {x['key']: x for x in shard_support(rows)['cases'] if x['best_recall'] >= 0.8}
    sharding = [r for r in rows if r['stage'] == 'sharding' and r['key'] in sup]
    done = ({json.loads(l)['key'] for l in VERBATIM.read_text().splitlines() if l.strip()}
            if VERBATIM.exists() else set())
    pk = {m: packages(m) for m in MODEL_IDS}
    total = spent()
    for r in sharding:
        if r['key'] in done:
            continue
        pkg = pk[r['model']][r['instance']]
        best = max(pkg['source_supports'], key=lambda s: recall(s['text'], r['fact_text']))
        model = MODEL_IDS[r['model']]
        user = verb_user(best['text'], pkg['question'])
        resp, total = call(f"verb/extract/{r['key']}/{r['fact_id']}", model, VERB_SYSTEM,
                           user, EXTRACT_TOKENS, CAP, total)
        if resp is None:
            break
        units = _parse_units(resp.content or '', MAX_UNITS) if resp.success else []
        delivered = [u for u in units if delivery_gate(u, r['fact_text'], pkg['question'])['ok']]
        rec = {'key': r['key'], 'fact_id': r['fact_id'], 'best_recall': round(recall(best['text'], r['fact_text']), 3),
               'fact_text': r['fact_text'], 'n_units': len(units), 'n_delivered': len(delivered),
               'units': units, 'status': 'delivered' if delivered else 'undelivered',
               'orig_f1': r['orig_f1'], 'orig_correct': r['orig_correct']}
        if delivered:
            by = board_by_agent(pkg)
            by.setdefault(owners(r)[0], []).extend(delivered)
            order = sorted(by, key=lambda x: (len(x), x))
            prompt = _build_evidence_board_prompt([by[a] for a in order], pkg['question'])
            resp2, total = call(f"verb/answer/{r['key']}/{r['fact_id']}", model,
                                _AGGREGATION_SYSTEM, prompt, ANSWER_TOKENS, CAP, total)
            if resp2 is None:
                break
            ans = extract_answer(resp2.content or '') if resp2.success else ''
            rec['answer'] = ans
            rec['f1'] = answer_f1(ans, {'answer': pkg['gold_answer']})
            rec['correct'] = rec['f1'] >= 1.0
        with VERBATIM.open('a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print(json.dumps({'verbatim': r['key'], 'delivered': len(delivered),
                          'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


def verbatim_score():
    from scripts.missing_fact_repair_pilot import cp_ci
    rows = [json.loads(l) for l in VERBATIM.read_text().splitlines() if l.strip()]
    d = [r for r in rows if r['status'] == 'delivered']
    k, n = len(d), len(rows)
    lo, hi = cp_ci(k, n)
    out = {'n': n, 'delivered': k, 'delivered_ci': [lo, hi], 'undelivered': n - k,
           'spend_usd': round(spent(), 6), 'cases': rows}
    if d:
        p = [(int(r['correct']), int(r['orig_correct'])) for r in d]
        out['correct'] = {'repaired': sum(a for a, _ in p), 'original': sum(b for _, b in p),
                          'diff': boot([(a, b, 'x') for a, b in p])[0],
                          'diff_ci': list(boot([(a, b, 'x') for a, b in p])[1:])}
    return out


def bridge():
    """Amendment 6: bridge-aware extraction on the six supported sharding cases (arm cap $0.20)."""
    check_frozen()
    man = json.loads(AMEND_MANIFEST.read_text())
    assert file_sha(AMEND6) == man.get('amendment6_sha256'), 'amendment 6 changed'
    assert sha(BRIDGE_SYSTEM + '|' + bridge_user('P', 'Q')) == man.get('bridge_prompt_sha256'), \
        'bridge prompt changed'
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    sup = {x['key']: x for x in shard_support(rows)['cases'] if x['best_recall'] >= 0.8}
    sharding = [r for r in rows if r['stage'] == 'sharding' and r['key'] in sup]
    done = ({json.loads(l)['key'] for l in BRIDGE.read_text().splitlines() if l.strip()}
            if BRIDGE.exists() else set())
    pk = {m: packages(m) for m in MODEL_IDS}
    total = spent()
    arm_cap = total + 0.20
    for r in sharding:
        if r['key'] in done:
            continue
        pkg = pk[r['model']][r['instance']]
        best = max(pkg['source_supports'], key=lambda s: recall(s['text'], r['fact_text']))
        model = MODEL_IDS[r['model']]
        user = bridge_user(best['text'], pkg['question'])
        resp, total = call(f"bridge/extract/{r['key']}/{r['fact_id']}", model, BRIDGE_SYSTEM,
                           user, EXTRACT_TOKENS, arm_cap, total)
        if resp is None:
            break
        units = _parse_units(resp.content or '', 5) if resp.success else []
        delivered = [u for u in units if delivery_gate(u, r['fact_text'], pkg['question'])['ok']]
        rec = {'key': r['key'], 'fact_id': r['fact_id'],
               'best_recall': round(recall(best['text'], r['fact_text']), 3),
               'fact_text': r['fact_text'], 'n_units': len(units), 'n_delivered': len(delivered),
               'units': units, 'status': 'delivered' if delivered else 'undelivered',
               'orig_f1': r['orig_f1'], 'orig_correct': r['orig_correct']}
        if delivered:
            by = board_by_agent(pkg)
            by.setdefault(owners(r)[0], []).extend(delivered)
            order = sorted(by, key=lambda x: (len(x), x))
            prompt = _build_evidence_board_prompt([by[a] for a in order], pkg['question'])
            resp2, total = call(f"bridge/answer/{r['key']}/{r['fact_id']}", model,
                                _AGGREGATION_SYSTEM, prompt, ANSWER_TOKENS, arm_cap, total)
            if resp2 is None:
                break
            ans = extract_answer(resp2.content or '') if resp2.success else ''
            rec['answer'] = ans
            rec['f1'] = answer_f1(ans, {'answer': pkg['gold_answer']})
            rec['correct'] = rec['f1'] >= 1.0
        with BRIDGE.open('a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print(json.dumps({'bridge': r['key'], 'delivered': len(delivered),
                          'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


def bridge_score():
    from scripts.missing_fact_repair_pilot import cp_ci
    rows = [json.loads(l) for l in BRIDGE.read_text().splitlines() if l.strip()]
    d = [r for r in rows if r['status'] == 'delivered']
    k, n = len(d), len(rows)
    lo, hi = cp_ci(k, n)
    out = {'n': n, 'delivered': k, 'delivered_ci': [lo, hi], 'undelivered': n - k,
           'spend_usd': round(spent(), 6), 'cases': rows}
    if d:
        p = [(int(r['correct']), int(r['orig_correct'])) for r in d]
        out['correct'] = {'repaired': sum(a for a, _ in p), 'original': sum(b for _, b in p),
                          'diff': boot([(a, b, 'x') for a, b in p])[0],
                          'diff_ci': list(boot([(a, b, 'x') for a, b in p])[1:])}
    return out


def pass1_spend():
    if not PASS1.exists() or not CALLS.exists():
        return 0.0
    keys = {'extract/%s/%s' % (json.loads(l)['key'], json.loads(l)['fact_id'])
            for l in PASS1.read_text().splitlines() if l.strip()}
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('key') in keys)


def sens_cells():
    if not SENS.exists():
        return {}
    rows = [json.loads(l) for l in SENS.read_text().splitlines() if l.strip()]
    out = {}
    for stage in ('extraction', 'sharding', 'all'):
        sel = [r for r in rows if stage == 'all' or r['stage'] == stage]
        d = [r for r in sel if r['sens_status'] == 'delivered']
        c = {'n': len(sel), 'delivered': len(d), 'no_unit': len(sel) - len(d)}
        if d:
            ap = [(int(r['sens_correct']) if r['sens_status'] == 'delivered' else int(r['orig_correct']),
                   int(r['orig_correct']), r['instance']) for r in sel]
            af = [(r['sens_f1'] if r['sens_status'] == 'delivered' else r['orig_f1'],
                   r['orig_f1'], r['instance']) for r in sel]
            c['correct_pairs'] = {'repaired': sum(a for a, _, _ in ap), 'original': sum(b for _, b, _ in ap),
                                  'diff': boot(ap)[0], 'diff_ci': list(boot(ap)[1:])}
            c['f1_pairs'] = {'repaired': sum(a for a, _, _ in af) / len(af),
                             'original': sum(b for _, b, _ in af) / len(af),
                             'diff': boot(af)[0], 'diff_ci': list(boot(af)[1:])}
            c['flips'] = {'gain': sum(1 for a, b, _ in ap if a and not b),
                          'loss': sum(1 for a, b, _ in ap if b and not a),
                          'tie': sum(1 for a, b, _ in ap if a == b)}
        out[stage] = c
    return out


def score():
    check_frozen()
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    ctl = ({json.loads(l)['key']: json.loads(l) for l in CONTROL.read_text().splitlines() if l.strip()}
           if CONTROL.exists() else {})
    cells = {}
    for stage in ('extraction', 'sharding', 'all'):
        sel = [r for r in rows if stage == 'all' or r['stage'] == stage]
        c = {'n': len(sel),
             'delivered': sum(1 for r in sel if r['status'] == 'delivered'),
             'undelivered': sum(1 for r in sel if r['status'] == 'undelivered')}
        allp = [(int(r['repair_correct']) if r['status'] == 'delivered' else int(r['orig_correct']),
                 int(r['orig_correct']), r['instance']) for r in sel]
        allf = [(r['repair_f1'] if r['status'] == 'delivered' else r['orig_f1'],
                 r['orig_f1'], r['instance']) for r in sel]
        c['correct_all'] = {'repaired': sum(a for a, _, _ in allp), 'original': sum(b for _, b, _ in allp),
                            'diff': boot(allp)[0], 'diff_ci': list(boot(allp)[1:])}
        c['f1_all'] = {'repaired': sum(a for a, _, _ in allf) / len(allf),
                       'original': sum(b for _, b, _ in allf) / len(allf),
                       'diff': boot(allf)[0], 'diff_ci': list(boot(allf)[1:])}
        c['flips_all'] = {'gain': sum(1 for a, b, _ in allp if a and not b),
                          'loss': sum(1 for a, b, _ in allp if b and not a),
                          'tie': sum(1 for a, b, _ in allp if a == b)}
        repaired = [r for r in sel if r['status'] == 'delivered']
        if repaired:
            pc = [(int(r['repair_correct']), int(r['orig_correct']), r['instance']) for r in repaired]
            pf = [(r['repair_f1'], r['orig_f1'], r['instance']) for r in repaired]
            c['correct_pairs'] = {'repaired': sum(a for a, _, _ in pc), 'original': sum(b for _, b, _ in pc),
                                  'diff': boot(pc)[0], 'diff_ci': list(boot(pc)[1:])}
            c['f1_pairs'] = {'repaired': sum(a for a, _, _ in pf) / len(pf),
                             'original': sum(b for _, b, _ in pf) / len(pf),
                             'diff': boot(pf)[0], 'diff_ci': list(boot(pf)[1:])}
            c['flips'] = {'gain': sum(1 for a, b, _ in pc if a and not b),
                          'loss': sum(1 for a, b, _ in pc if b and not a),
                          'tie': sum(1 for a, b, _ in pc if a == b)}
            with_ctl = [r for r in repaired if r['key'] in ctl]
            if with_ctl:
                qc = [(int(r['repair_correct']), int(ctl[r['key']]['control_correct']), r['instance'])
                      for r in with_ctl]
                qf = [(r['repair_f1'], ctl[r['key']]['control_f1'], r['instance']) for r in with_ctl]
                cc = [(int(ctl[r['key']]['control_correct']), int(r['orig_correct']), r['instance'])
                      for r in with_ctl]
                c['vs_control'] = {
                    'n': len(with_ctl),
                    'control_correct': sum(b for _, b, _ in qc),
                    'repaired_minus_control': {'diff': boot(qc)[0], 'diff_ci': list(boot(qc)[1:])},
                    'f1': {'repaired': sum(a for a, _, _ in qf) / len(qf),
                           'control': sum(b for _, b, _ in qf) / len(qf),
                           'diff': boot(qf)[0], 'diff_ci': list(boot(qf)[1:])},
                    'control_minus_original': {'diff': boot(cc)[0], 'diff_ci': list(boot(cc)[1:])},
                    'control_flips': {'to_correct': sum(1 for a, b, _ in cc if a and not b),
                                      'to_wrong': sum(1 for a, b, _ in cc if b and not a)}}
        cells[stage] = c
    res = {'cells': cells, 'spend_usd': round(spent(), 6), 'rows': len(rows),
           'cells_sens': sens_cells(),
           'copied': copied_summary(rows), 'fact_in_input': fact_in_input(rows),
           'combine': (combine_score() if COMBINE.exists() else None),
           'verbatim': (verbatim_score() if VERBATIM.exists() else None),
           'bridge': (bridge_score() if BRIDGE.exists() else None),
           'shard_support': shard_support(rows),
           'pass1_rows': (len(PASS1.read_text().splitlines())
                                                          if PASS1.exists() else 0),
           'pass1_spend': pass1_spend()}
    SCORE.write_text(json.dumps(res, indent=1))
    write_report(res)
    print(json.dumps(res, indent=1))


def write_report(res):
    lines = ['# Audit-guided repairs on the 59 missing-fact cases',
             '',
             '2026-11-15. Rule `B6-audit-guided-repairs.md` (sha `%s...`), amendment 2 (sha `%s...`), amendment 3 '
             '(post-hoc sensitivity), amendment 4 (full-evidence routing), amendment 5 (verbatim quotation) and '
             'amendment 6 (bridge-aware extraction). One repair '
             'procedure, two targets: re-extraction from the flagged agent shard (extraction cases), re-routing '
             'the source support passage that carries the fact through the same extraction step (sharding '
             'cases). Original arm = the same trace\'s stored baseline. Spend $%.6f, cap $5.00.'
             % (file_sha(RULE)[:8], file_sha(AMENDMENT)[:8], res['spend_usd']),
             '',
             '| cell | cases | delivered | undelivered | correct: repaired / original | diff [95% CI] | '
             'F1: repaired / original | diff [95% CI] | gain / loss / tie |',
             '| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |']
    for stage in ('extraction', 'sharding', 'all'):
        c = res['cells'][stage]
        cp = c.get('correct_all')
        fp = c.get('f1_all')
        fl = c.get('flips_all')
        lines.append('| %s | %d | %d | %d | %s | %s | %s | %s | %s |'
                     % (stage, c['n'], c['delivered'], c['undelivered'],
                        '%d / %d' % (cp['repaired'], cp['original']) if cp else '—',
                        '%+.3f [%+.3f, %+.3f]' % (cp['diff'], *cp['diff_ci']) if cp else '—',
                        '%.3f / %.3f' % (fp['repaired'], fp['original']) if fp else '—',
                        '%+.3f [%+.3f, %+.3f]' % (fp['diff'], *fp['diff_ci']) if fp else '—',
                        '%d / %d / %d' % (fl['gain'], fl['loss'], fl['tie']) if fl else '—'))
    lines += ['', 'Paired bootstrap over cases, 2,000 draws, seed 43. The table above is every case in the cell: '
              'an undelivered case is scored on its original answer, so it contributes a zero difference and '
              'stays in the denominator.',
              '',
              '### Delivered cases only',
              '',
              '| cell | delivered | correct: repaired / original | diff [95% CI] | F1: repaired / original | '
              'diff [95% CI] | gain / loss / tie |',
              '| --- | ---: | --- | --- | --- | --- | --- |']
    for stage in ('extraction', 'sharding', 'all'):
        c = res['cells'][stage]
        cp, fp, fl = c.get('correct_pairs'), c.get('f1_pairs'), c.get('flips')
        if not cp:
            lines.append('| %s | 0 | — | — | — | — | — |' % stage)
            continue
        lines.append('| %s | %d | %d / %d | %+.3f [%+.3f, %+.3f] | %.3f / %.3f | %+.3f [%+.3f, %+.3f] | '
                     '%d / %d / %d |'
                     % (stage, c['delivered'], cp['repaired'], cp['original'],
                        cp['diff'], *cp['diff_ci'], fp['repaired'], fp['original'],
                        fp['diff'], *fp['diff_ci'], fl['gain'], fl['loss'], fl['tie']))
    ss = res['shard_support']
    cb = res.get('combine')
    lines += ['', 'This subset is conditional on the gate delivering; it is not the cell\'s average effect.',
              '',
              '## Which sharding diagnoses a supplied passage can support', '',
              'The flagged fact is stated in a supplied passage at the gate threshold (recall >= 0.8) in **%d of '
              '%d** sharding cases. The other **%d diagnoses are unsupported**: no passage the instance supplied '
              'states the fact, so no gold-free repair of the sharding stage can deliver it. The sharding '
              'diagnosis is restricted to the %d supported cases.'
              % (ss['stated_ge80'], ss['n'], ss['unsupported'], ss['stated_ge80']),
              '',
              '| supported case | best passage recall | passage agent |', '| --- | ---: | ---: |']
    for x in ss['cases']:
        if x['best_recall'] >= 0.8:
            lines.append('| %s | %.2f | %d |' % (x['key'], x['best_recall'], x['passage_agent']))
    if cb and cb.get('delivered'):
        first = next((r for r in [json.loads(l) for l in COMBINE.read_text().splitlines()
                                  if l.strip()] if r['status'] == 'delivered'), {})
        lines += ['', 'The corrected single-passage pass delivered none of these six: even where a passage states '
                  'the fact, the extracted units paraphrase it below the 0.8 gate. The full-evidence arm '
                  'delivered one case, `%s`, which is not one of the six and stayed incorrect.'
                  % first.get('key', '?')]
    vb = res.get('verbatim')
    if vb:
        lines += ['', '## B6c: verbatim quotation on the six supported cases (amendment 5)', '',
                  'The extractor must copy sentences exactly; nothing else changes.',
                  '',
                  '| cases | delivered | delivered 95% CI | undelivered | correct repaired / original | diff [95% CI] |',
                  '| ---: | ---: | --- | ---: | --- | --- |',
                  '| %d | %d | %.3f-%.3f | %d | %s | %s |'
                  % (vb['n'], vb['delivered'], vb['delivered_ci'][0], vb['delivered_ci'][1],
                     vb['undelivered'],
                     ('%d / %d' % (vb['correct']['repaired'], vb['correct']['original'])
                      if vb.get('correct') else '—'),
                     ('%+.3f [%+.3f, %+.3f]' % (vb['correct']['diff'], *vb['correct']['diff_ci'])
                      if vb.get('correct') else '—')),
                  '',
                  'Four of the six returned no usable quote: three refusals ("the provided text does not contain ...") and '
                  'one "no sentences ... bear on the question". The other two quoted sentences that do not carry '
                  'the fact. The extractor screened for sentences that mention the question\'s entities, so the '
                  'bridge sentence the fact needs was not quoted.',
                  '',
                  '| case | best passage recall | units | delivered | outcome |',
                  '| --- | ---: | ---: | ---: | --- |']
        for x in vb['cases']:
            lines.append('| %s | %.2f | %d | %d | %s |'
                         % (x['key'], x['best_recall'], x['n_units'], x['n_delivered'],
                            ('correct' if x.get('correct') else ('wrong' if x['status'] == 'delivered'
                                                                 else 'undelivered'))))
    bg = res.get('bridge')
    if bg:
        lines += ['', '## B6d: bridge-aware extraction on the six supported cases (amendment 6)', '',
                  'Verbatim quotation with the entity screen removed: quote every sentence the chain needs, '
                  'including bridge sentences.',
                  '',
                  '| cases | delivered | delivered 95% CI | undelivered | correct repaired / original |',
                  '| ---: | ---: | --- | ---: | --- |',
                  '| %d | %d | %.3f-%.3f | %d | %s |'
                  % (bg['n'], bg['delivered'], bg['delivered_ci'][0], bg['delivered_ci'][1],
                     bg['undelivered'],
                     ('%d / %d' % (bg['correct']['repaired'], bg['correct']['original'])
                      if bg.get('correct') else '—')),
                  '',
                  '| case | best passage recall | units | delivered | outcome |',
                  '| --- | ---: | ---: | ---: | --- |']
        for x in bg['cases']:
            lines.append('| %s | %.2f | %d | %d | %s |'
                         % (x['key'], x['best_recall'], x['n_units'], x['n_delivered'],
                            ('correct' if x.get('correct') else ('wrong' if x['status'] == 'delivered'
                                                                 else 'undelivered'))))
        if bg['delivered'] == 0:
            lines += ['', '**The sharding repair is closed as a negative result.** Across the corrected '
                      'single-passage pass, full-evidence routing, verbatim quotation and bridge-aware '
                      'quotation, no gold-free extraction delivers these six bridge facts under the frozen '
                      'gate. The cause read from the outputs is the extractor\'s own behaviour: it screens '
                      'sentences by question entities, refuses when a document does not mention them, and '
                      'paraphrases or summarises what it does quote; it does not copy the bridge sentence '
                      'even when the passage states the fact. This is an extractor limitation, not a passage '
                      'or gate defect.']
    lines += ['',
              '## No-unit control (delivered cases)',
              '',
              '| cell | n | control correct | repaired - control [95% CI] | F1 repaired / control, diff [95% CI] '
              '| control - original [95% CI] | control flips to correct / to wrong |',
              '| --- | ---: | ---: | --- | --- | --- | --- |']
    for stage in ('extraction', 'sharding', 'all'):
        v = res['cells'][stage].get('vs_control')
        if not v:
            lines.append('| %s | 0 | — | — | — | — | — |' % stage)
            continue
        rc = v['repaired_minus_control']
        ff = v['f1']
        co = v['control_minus_original']
        lines.append('| %s | %d | %d | %+.3f [%+.3f, %+.3f] | %.3f / %.3f, %+.3f [%+.3f, %+.3f] | '
                     '%+.3f [%+.3f, %+.3f] | %d / %d |'
                     % (stage, v['n'], v['control_correct'],
                        rc['diff'], *rc['diff_ci'],
                        ff['repaired'], ff['control'], ff['diff'], *ff['diff_ci'],
                        co['diff'], *co['diff_ci'],
                        v['control_flips']['to_correct'], v['control_flips']['to_wrong']))
    lines += ['', '## Sensitivity: delivery at recall >= 0.5 (post-hoc threshold, amendment 3)', '',
              '| cell | undelivered cases | delivered | no unit >= 0.5 | correct: repaired / original | '
              'diff [95% CI] | F1: repaired / original | diff [95% CI] | gain / loss / tie |',
              '| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |']
    for stage in ('extraction', 'sharding', 'all'):
        c = res.get('cells_sens', {}).get(stage)
        if not c:
            lines.append('| %s | — | — | — | — | — | — | — | — |' % stage)
            continue
        cp, fp, fl = c.get('correct_pairs'), c.get('f1_pairs'), c.get('flips')
        lines.append('| %s | %d | %d | %d | %s | %s | %s | %s | %s |'
                     % (stage, c['n'], c['delivered'], c['no_unit'],
                        '%d / %d' % (cp['repaired'], cp['original']) if cp else '—',
                        '%+.3f [%+.3f, %+.3f]' % (cp['diff'], *cp['diff_ci']) if cp else '—',
                        '%.3f / %.3f' % (fp['repaired'], fp['original']) if fp else '—',
                        '%+.3f [%+.3f, %+.3f]' % (fp['diff'], *fp['diff_ci']) if fp else '—',
                        '%d / %d / %d' % (fl['gain'], fl['loss'], fl['tie']) if fl else '—'))
    lines += ['',
              'All undelivered cases are in this denominator: a case with no unit at or above 0.5 counts as a '
              'zero difference.',
              '', 'The post-hoc label applies to this table only; amendment 4 below is a separate frozen arm.']
    cb = res.get('combine')
    if cb:
        lines += ['',
                  '## Full-evidence routing for the sharding cell (amendment 4)',
                  '',
                  'The flagged agent is given the concatenation of all the instance\'s source supports, then the '
                  'same frozen extraction step and gate. Gold-free: no fact text is shown.',
                  '',
                  '| cases | delivered | delivered 95% CI | undelivered | correct repaired / original | diff [95% CI] |',
                  '| ---: | ---: | --- | ---: | --- | --- |',
                  '| %d | %d | %.3f-%.3f | %d | %s | %s |'
                  % (cb['n'], cb['delivered'], cb['delivered_ci'][0], cb['delivered_ci'][1],
                     cb['undelivered'],
                     ('%d / %d' % (cb['correct']['repaired'], cb['correct']['original'])
                      if cb.get('correct') else '—'),
                     ('%+.3f [%+.3f, %+.3f]' % (cb['correct']['diff'], *cb['correct']['diff_ci'])
                      if cb.get('correct') else '—'))]
    lines += ['',
              'The control re-aggregates the unchanged board with the same prompt, model and token budget. '
              'Control - original measures re-run drift; repaired - control is the delivered units alone.',
              '', '## Delivery',
              '',
              'Delivery is the frozen `delivery_gate` (fact token recall >= 0.8). Undelivered cases never reach '
              'the board. The gate certifies that a unit states the flagged fact; it does not certify that the '
              'passage contains it. For the delivered units, the shard carries the unit text at recall >= 0.8 '
              'for %d of %d units (>= 0.5 for %d).'
              % (res.get('copied', {}).get('ge80', 0), res.get('copied', {}).get('n', 0),
                 res.get('copied', {}).get('ge50', 0)),
              '',
              'For the %d delivered extraction cases the flagged fact sits in the flagged agent\'s own passage at '
              'recall >= 0.8 in %d and >= 0.5 in %d, so these repairs recover a fact the shard did carry.'
              % (res.get('fact_in_input', {}).get('n', 0), res.get('fact_in_input', {}).get('ge80', 0),
                 res.get('fact_in_input', {}).get('ge50', 0)),
              '', '## What this cannot show', '',
              'A single-slot repair adds the fact the audit flagged. It does not separate "the audit picked the '
              'right slot" from "any correct fact added would have helped", and it does not re-run the full '
              'upstream protocol: extraction and re-routing are the repaired stages, the downstream selection '
              'and aggregation run on the existing board plus the delivered units.',
              '',
              'The first sharding pass fed the flagged agent\'s own passage, which by definition lacks the fact, '
              'and delivered nothing; its 20 calls ($%.6f) and records in `results_sharding_pass1.jsonl` stay on '
              'record.' % res.get('pass1_spend', 0.0),
              '', '## Ledger', 'Spend $%.6f.' % res['spend_usd']]
    REPORT.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    ap.add_argument('--split-pass1', action='store_true')
    ap.add_argument('--control', action='store_true')
    ap.add_argument('--sensitivity', action='store_true')
    ap.add_argument('--combine', action='store_true')
    ap.add_argument('--combine-score', action='store_true')
    ap.add_argument('--verbatim', action='store_true')
    ap.add_argument('--verbatim-score', action='store_true')
    ap.add_argument('--bridge', action='store_true')
    ap.add_argument('--bridge-score', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.run:
        run()
    if a.split_pass1:
        split_pass1()
    if a.control:
        control()
    if a.sensitivity:
        sensitivity()
    if a.combine:
        combine()
    if a.combine_score:
        print(json.dumps(combine_score(), indent=1))
    if a.verbatim:
        verbatim()
    if a.verbatim_score:
        print(json.dumps(verbatim_score(), indent=1))
    if a.bridge:
        bridge()
    if a.bridge_score:
        print(json.dumps(bridge_score(), indent=1))
    if a.score:
        score()