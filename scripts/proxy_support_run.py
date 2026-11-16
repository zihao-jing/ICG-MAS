"""Proxy-support pilot: Qwen facts -> gold-support check -> audit stage.

Rule `rebuttal/pilots/prereg/Proxy-support-pilot-v1.md` (frozen before any
call). 10 traces, cap $1.0, every attempt logged.

    ./run.sh python -m scripts.proxy_support_run --facts
    ./run.sh python -m scripts.proxy_support_run --equiv
    ./run.sh python -m scripts.proxy_support_run --audit
    ./run.sh python -m scripts.proxy_support_run --score
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.per_fact_labeller import parse as parse_audit
from scripts.per_fact_labeller import render as render_audit
from src.audit.sharding_check import diagnose_with_sharding
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
RULE = ROOT / 'rebuttal/pilots/prereg/Proxy-support-pilot-v1.md'
FACTS_PROMPT = ROOT / 'rebuttal/pilots/prereg/proxy_facts_prompt_v1.json'
EQUIV_PROMPT = ROOT / 'rebuttal/pilots/prereg/proxy_support_equiv_prompt_v1.json'
AUDIT_PROMPT = ROOT / 'rebuttal/pilots/20261113_per_fact_labeller/per_fact_prompt_v3.json'
CAPS_PATH = ROOT / 'rebuttal/pilots/prereg/Proxy-support-caps-v1.json'


def configure(d):
    global OUT, POP, MANIFEST, CALLS, FACTS, EQUIV, LABELS, RESULTS, REPORT, PIPELINE
    OUT = ROOT / d
    POP = OUT / 'population.json'
    MANIFEST = OUT / 'build_manifest.json'
    CALLS = OUT / 'calls.jsonl'
    FACTS = OUT / 'facts.json'
    EQUIV = OUT / 'equiv.json'
    LABELS = OUT / 'labels.json'
    RESULTS = OUT / 'results.json'
    REPORT = OUT / 'report.md'
    PIPELINE = OUT / 'pipeline.jsonl'


configure('rebuttal/pilots/20261115_proxy_support')
QWEN = 'qwen/qwen3-235b-a22b-2507'
GEMINI = 'google/gemini-3.6-flash'
HAIKU = 'anthropic/claude-haiku-5.5'
PRICE = {QWEN: (0.14 / 1e6, 0.8 / 1e6), GEMINI: (0.75 / 1e6, 3.75 / 1e6),
         HAIKU: (0.1 / 1e6, 0.5 / 1e6)}
# cap-enforcement output allowance: max completion tokens observed in the pilot
EST_OUT = {QWEN: 400, GEMINI: 1600, HAIKU: 1600}
if (ROOT / 'rebuttal/pilots/prereg/Proxy-support-caps-v1.json').exists():
    EST_OUT = {QWEN: 3000, GEMINI: 6000, HAIKU: 6000}
CAP = 1.0
VERDICTS = {'equivalent', 'partial', 'unsupported', 'contradicted'}
STAGE = {
    'extraction_omission': 'extraction',
    'sharding_omission': 'sharding',
    'mixed_sharding_extraction': 'sharding',
    'selection_omission': 'transmission',
    'partial': 'transmission',
    'distortion': 'transmission',
    'candidate_aggregation': 'aggregation',
    'correct_control': 'correct',
    'uncertain': 'uncertain',
}


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check_frozen():
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(FACTS_PROMPT) == man['facts_prompt_sha256'], 'facts prompt changed'
    assert file_sha(EQUIV_PROMPT) == man['equiv_prompt_sha256'], 'equiv prompt changed'
    assert file_sha(POP) == man['population_sha256'], 'population changed'
    assert sha(json.loads(AUDIT_PROMPT.read_text())['system']) == man['labeller_prompt_sha256'], \
        'labeller prompt changed'
    if man.get('caps_sha256'):
        assert file_sha(CAPS_PATH) == man['caps_sha256'], 'caps changed'
    return man


def caps():
    if CAPS_PATH.exists():
        return json.loads(CAPS_PATH.read_text())
    return {}


def spent():
    if not CALLS.exists():
        return 0.0
    out = 0.0
    for line in CALLS.read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get('event') == 'result':
            out += e.get('cost_usd') or 0.0
    return out


LOCK = None
TOTAL = {'v': 0.0}


def call_parallel(key, model, system, user, max_tokens, cap):
    """Thread-safe call with cap enforced on actual spend under a lock."""
    pin, pout = PRICE[model]
    est_in = math.ceil((len(system) + len(user)) / 4)
    with LOCK:
        if TOTAL['v'] + est_in * pin + EST_OUT[model] * pout > cap:
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                    'cost_usd': 0.0}) + '\n')
            return None
    call_id = sha('|'.join([key, system, user, str(max_tokens)]))
    with LOCK, CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': call_id,
                            'model': model, 'system_sha256': sha(system),
                            'user_sha256': sha(user), 'max_tokens': max_tokens,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=system, user_query=user, model=model,
                     max_tokens=max_tokens, temperature=0,
                     metadata={'pilot': 'proxy_support', 'key': key})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * pin
            + usage.get('completion_tokens', 0) * pout)
    with LOCK:
        TOTAL['v'] += cost
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'result', 'key': key, 'call_id': call_id,
                                'model': model, 'success': resp.success,
                                'error': resp.error, 'content': resp.content,
                                'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp


def call(key, model, system, user, max_tokens, cap, total):
    pin, pout = PRICE[model]
    est_in = math.ceil((len(system) + len(user)) / 4)
    if total + est_in * pin + EST_OUT[model] * pout > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                'cost_usd': 0.0}) + '\n')
        return None, total
    call_id = sha('|'.join([key, system, user, str(max_tokens)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': call_id,
                            'model': model, 'system_sha256': sha(system),
                            'user_sha256': sha(user), 'max_tokens': max_tokens,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=system, user_query=user, model=model,
                     max_tokens=max_tokens, temperature=0,
                     metadata={'pilot': 'proxy_support', 'key': key})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * pin
            + usage.get('completion_tokens', 0) * pout)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': call_id,
                            'model': model, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def render_docs(row):
    return '\n\n'.join(f"[{d['unit_id']}]\n{d['text']}" for d in row['documents'])


def norm_src(s, doc_ids):
    if s in doc_ids:
        return s
    for d in sorted(doc_ids, key=len, reverse=True):
        if s.startswith(d) and len(s) > len(d) and s[len(d)] in ': /-_':
            return d
    return None


def validate_facts(obj, doc_ids):
    """Amended shape rule (Proxy-support-pilot-v1-amendment-1.md)."""
    if not isinstance(obj, dict):
        return None
    sets = obj.get('support_sets')
    if isinstance(obj.get('facts'), list):
        rows = obj['facts']
        facts = []
        for f in rows:
            if not isinstance(f, dict) or set(f) != {'fact_id', 'text', 'source_ids'}:
                return None
            facts.append({'fact_id': f['fact_id'], 'text': f['text'],
                          'source_ids': f['source_ids']})
    else:
        facts = []
        for fid, f in obj.items():
            if fid == 'support_sets':
                continue
            if not isinstance(f, dict) or set(f) != {'text', 'source_ids'}:
                return None
            facts.append({'fact_id': fid, 'text': f['text'],
                          'source_ids': f['source_ids']})
    if not facts or not isinstance(sets, list) or not sets:
        return None
    ids = []
    for f in facts:
        fid, text, src = f['fact_id'], f['text'], f['source_ids']
        if not (isinstance(fid, str) and fid and isinstance(text, str) and text.strip()):
            return None
        if not (isinstance(src, list) and src):
            return None
        fixed = []
        for s in src:
            n = norm_src(s, doc_ids) if isinstance(s, str) else None
            if n is None:
                return None
            if n not in fixed:
                fixed.append(n)
        f['source_ids'] = fixed
        ids.append(fid)
    if len(ids) != len(set(ids)):
        return None
    for s in sets:
        if not (isinstance(s, list) and s and all(x in ids for x in s)):
            return None
    return {'facts': facts, 'support_sets': sets}


def load_json(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def run_facts(cap):
    man = check_frozen()
    spec = json.loads(FACTS_PROMPT.read_text())
    rows = json.loads(POP.read_text())
    done = load_json(FACTS, {})
    total = spent()
    for r in rows:
        prev = done.get(r['key'], {})
        if prev.get('status') == 'ok':
            continue
        tag = 'retry' if prev else 'attempt'
        docs = {d['unit_id'] for d in r['documents']}
        user = spec['user'].format(question=r['question'], documents=render_docs(r))
        rec, ok = None, False
        for attempt in range(1, 4):
            key = f"facts/{r['key']}/{tag}-{attempt}"
            resp, total = call(key, QWEN, spec['system'], user, spec['max_tokens'], cap, total)
            if resp is None:
                break
            rec = validate_facts(last_object(resp.content or ''), docs) if resp.success else None
            ok = rec is not None
            if ok:
                break
        done[r['key']] = {'status': 'ok' if ok else 'failed', 'value': rec,
                          'attempts': attempt}
        FACTS.write_text(json.dumps(done, indent=1, ensure_ascii=False))
        print(json.dumps({'key': r['key'], 'ok': ok, 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(total, 6)}))


def assemble():
    """Rebuild facts.json / equiv.json / labels.json from pipeline.jsonl."""
    facts, equiv, labels = {}, {}, {}
    if PIPELINE.exists():
        for line in PIPELINE.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            facts[rec['key']] = rec['facts']
            if rec.get('equiv') is not None:
                equiv[rec['key']] = rec['equiv']
            for chk, lab in (rec.get('labels') or {}).items():
                labels[f"audit/{rec['key']}/{chk}"] = lab
    FACTS.write_text(json.dumps(facts, indent=1, ensure_ascii=False))
    EQUIV.write_text(json.dumps(equiv, indent=1, ensure_ascii=False))
    LABELS.write_text(json.dumps(labels, indent=1, ensure_ascii=False))


def pipeline(workers, cap, limit=None):
    global LOCK
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from threading import Lock
    LOCK = Lock()
    man = check_frozen()
    rows = json.loads(POP.read_text())
    sf = json.loads(FACTS_PROMPT.read_text())
    se = json.loads(EQUIV_PROMPT.read_text())
    sa = json.loads(AUDIT_PROMPT.read_text())
    assert sha(sa['system']) == man['labeller_prompt_sha256']
    cp = caps()
    ftok = cp.get('facts_max_tokens', sf['max_tokens'])
    etok = cp.get('equiv_max_tokens', se['max_tokens'])
    atok = cp.get('labeller_max_tokens', 2000)
    done = set()
    if PIPELINE.exists():
        done = {json.loads(l)['key'] for l in PIPELINE.read_text().splitlines() if l.strip()}
    todo = [r for r in rows if r['key'] not in done]
    if limit:
        todo = todo[:limit]
    TOTAL['v'] = spent()
    print(json.dumps({'todo': len(todo), 'done': len(done), 'spent': round(TOTAL['v'], 6)}),
          flush=True)

    def one(r):
        docs = {d['unit_id'] for d in r['documents']}
        user_f = sf['user'].format(question=r['question'], documents=render_docs(r))
        rec = {'key': r['key'], 'facts': {'status': 'failed', 'value': None, 'attempts': 0},
               'equiv': None, 'labels': {}}
        for n in (1, 2, 3):
            resp = call_parallel(f"facts/{r['key']}/attempt-{n}", QWEN, sf['system'],
                                 user_f, ftok, cap)
            if resp is None:
                return None
            rec['facts']['attempts'] = n
            v = validate_facts(last_object(resp.content or ''), docs) if resp.success else None
            if v is not None:
                rec['facts'] = {'status': 'ok', 'value': v, 'attempts': n}
                break
        if rec['facts']['status'] != 'ok':
            return rec
        fids = [x['fact_id'] for x in rec['facts']['value']['facts']]
        fl = '\n'.join(f"{x['fact_id']}: {x['text']}" for x in rec['facts']['value']['facts'])
        sup = '\n\n'.join(f"[{s['unit_id']}]\n{s['text']}" for s in r['gold_supports'])
        user_e = se['user'].format(question=r['question'], facts=fl, supports=sup)
        for n in (1, 2):
            resp = call_parallel(f"equiv/{r['key']}/attempt-{n}", GEMINI, se['system'],
                                 user_e, etok, cap)
            if resp is None:
                return None
            obj = last_object(resp.content or '') if resp.success else None
            ok = (isinstance(obj, dict) and isinstance(obj.get('facts'), list)
                  and [x.get('fact_id') for x in obj['facts']] == fids
                  and all(x.get('verdict') in VERDICTS for x in obj['facts']))
            if ok:
                rec['equiv'] = {'status': 'ok', 'attempts': n,
                                'value': {x['fact_id']: {'verdict': x['verdict'],
                                                         'support_ids': x.get('support_ids') or [],
                                                         'reason': str(x.get('reason', ''))[:200]}
                                          for x in obj['facts']}}
                break
        if not rec['equiv'] or rec['equiv']['status'] != 'ok':
            rec['equiv'] = rec.get('equiv') or {'status': 'failed', 'value': None, 'attempts': 0}
            return rec
        if not r.get('has_extraction', True):
            return rec
        ids = set(fids)
        for chk, name in (('extraction', 'extraction pool'), ('board', 'shared board')):
            row = {'question': r['question'], 'facts': rec['facts']['value']['facts'],
                   'entries': r['checkpoints'][chk], 'checkpoint_name': name}
            user_a = render_audit(row)
            for n in (1, 2):
                resp = call_parallel(f"audit/{r['key']}/{chk}/attempt-{n}", HAIKU,
                                     sa['system'], user_a, atok, cap)
                if resp is None:
                    return None
                lab = parse_audit(resp.content, ids) if resp.success else None
                if lab is not None:
                    rec['labels'][chk] = {'status': 'ok', 'value': lab, 'attempts': n}
                    break
            if chk not in rec['labels']:
                rec['labels'][chk] = {'status': 'failed', 'value': None, 'attempts': 0}
        return rec

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(one, r): r for r in todo}
        for i, f in enumerate(as_completed(futs), 1):
            rec = f.result()
            if rec is None:
                print(json.dumps({'skipped_at_cap': True}), flush=True)
                continue
            with LOCK, PIPELINE.open('a') as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
            if i % 20 == 0 or i == len(todo):
                print(json.dumps({'done': i, 'of': len(todo), 'spent': round(TOTAL['v'], 6)}),
                      flush=True)
    assemble()
    print(json.dumps({'spent': round(TOTAL['v'], 6)}))


def revalidate():
    """Re-apply the amended parser to logged fact attempts (no calls)."""
    check_frozen()
    rows = {r['key']: r for r in json.loads(POP.read_text())}
    facts = load_json(FACTS, {})
    logged = {}
    if CALLS.exists():
        for line in CALLS.read_text().splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            if e.get('event') == 'result' and e.get('success') and e.get('key', '').startswith('facts/'):
                logged.setdefault(e['key'], e['content'])
    fixed = []
    for key, rec in facts.items():
        if rec.get('status') == 'ok':
            continue
        docs = {d['unit_id'] for d in rows[key]['documents']}
        for tag in ('attempt', 'retry'):
            for n in (1, 2, 3):
                ck = f'facts/{key}/{tag}-{n}'
                if ck not in logged:
                    continue
                v = validate_facts(last_object(logged[ck]), docs)
                if v is not None:
                    rec.update({'status': 'ok', 'value': v, 'attempts': n,
                                'revalidated_from': ck})
                    fixed.append(key)
                    break
            if rec.get('status') == 'ok':
                break
    FACTS.write_text(json.dumps(facts, indent=1, ensure_ascii=False))
    left = [k for k, v in facts.items() if v.get('status') != 'ok']
    print(json.dumps({'revalidated': len(fixed), 'still_failed': len(left),
                      'keys': fixed, 'left': left}, indent=1))


def run_equiv(cap):
    check_frozen()
    spec = json.loads(EQUIV_PROMPT.read_text())
    rows = json.loads(POP.read_text())
    facts = load_json(FACTS, {})
    done = load_json(EQUIV, {})
    total = spent()
    for r in rows:
        f = facts.get(r['key'], {})
        if r['key'] in done or f.get('status') != 'ok':
            continue
        ids = [x['fact_id'] for x in f['value']['facts']]
        fl = '\n'.join(f"{x['fact_id']}: {x['text']}" for x in f['value']['facts'])
        sup = '\n\n'.join(f"[{s['unit_id']}]\n{s['text']}" for s in r['gold_supports'])
        user = spec['user'].format(question=r['question'], facts=fl, supports=sup)
        rec, ok = None, False
        for attempt in range(1, 3):
            key = f"equiv/{r['key']}/attempt-{attempt}"
            resp, total = call(key, GEMINI, spec['system'], user, spec['max_tokens'], cap, total)
            if resp is None:
                break
            obj = last_object(resp.content or '') if resp.success else None
            ok = (isinstance(obj, dict) and isinstance(obj.get('facts'), list)
                  and [x.get('fact_id') for x in obj['facts']] == ids
                  and all(x.get('verdict') in VERDICTS for x in obj['facts']))
            if ok:
                rec = {x['fact_id']: {'verdict': x['verdict'],
                                      'support_ids': x.get('support_ids') or [],
                                      'reason': str(x.get('reason', ''))[:200]}
                       for x in obj['facts']}
                break
        done[r['key']] = {'status': 'ok' if ok else 'failed', 'value': rec,
                          'attempts': attempt}
        EQUIV.write_text(json.dumps(done, indent=1, ensure_ascii=False))
        print(json.dumps({'key': r['key'], 'ok': ok, 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(total, 6)}))


def run_audit(cap):
    man = check_frozen()
    spec = json.loads(AUDIT_PROMPT.read_text())
    assert sha(spec['system']) == man['labeller_prompt_sha256']
    rows = json.loads(POP.read_text())
    facts = load_json(FACTS, {})
    done = load_json(LABELS, {})
    total = spent()
    for r in rows:
        f = facts.get(r['key'], {})
        if f.get('status') != 'ok':
            continue
        ids = {x['fact_id'] for x in f['value']['facts']}
        for cp, name in (('extraction', 'extraction pool'), ('board', 'shared board')):
            key = f"audit/{r['key']}/{cp}"
            if key in done:
                continue
            row = {'question': r['question'], 'facts': f['value']['facts'],
                   'entries': r['checkpoints'][cp], 'checkpoint_name': name}
            user = render_audit(row)
            rec, ok = None, False
            for attempt in range(1, 3):
                resp, total = call(f'{key}/attempt-{attempt}', HAIKU, spec['system'],
                                   user, 2000, cap, total)
                if resp is None:
                    break
                rec = parse_audit(resp.content, ids) if resp.success else None
                ok = rec is not None
                if ok:
                    break
            done[key] = {'status': 'ok' if ok else 'failed', 'value': rec,
                         'attempts': attempt}
            LABELS.write_text(json.dumps(done, indent=1, ensure_ascii=False))
            print(json.dumps({'key': key, 'ok': ok, 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(total, 6)}))


def cp(k, n):
    if n == 0:
        return 0.0, 1.0

    def cdf(p, upto):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(upto + 1))

    def solve(fn, target):
        lo, hi = 0.0, 1.0
        for _ in range(90):
            mid = (lo + hi) / 2
            if fn(mid) > target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    lo = 0.0 if k == 0 else solve(lambda p: cdf(p, k - 1), 0.975)
    hi = 1.0 if k == n else solve(lambda p: cdf(p, k), 0.025)
    return lo, hi


def carriers_for(labels, fids):
    out = []
    for fid in fids:
        row = {'fact_id': fid}
        for cp in ('extraction', 'board'):
            lab = labels.get(f'{cp}/{fid}')
            if not lab or lab['status'] == 'absent':
                row[cp] = []
            else:
                row[cp] = [{'unit_ids': lab['unit_ids'], 'role': 'sole',
                            'fidelity': lab['fidelity']}]
        out.append(row)
    return {'facts': out}


def score():
    check_frozen()
    rows = json.loads(POP.read_text())
    facts = load_json(FACTS, {})
    equiv = load_json(EQUIV, {})
    labels = load_json(LABELS, {})
    per_trace, mismatches = [], []
    eq_all, eq_n = 0, 0
    types = Counter()
    examples = {}
    gen_failed = []
    for r in rows:
        f = facts.get(r['key'], {})
        if f.get('status') != 'ok':
            gen_failed.append(r['key'])
            per_trace.append({'key': r['key'], 'facts': 0, 'status': 'generation_failed',
                              'audit_stage': r['audit_stage'], 'known_stage': r['known_stage']})
            continue
        fids = [x['fact_id'] for x in f['value']['facts']]
        e = equiv.get(r['key'], {})
        if e.get('status') == 'ok':
            for fid in fids:
                eq_n += 1
                v = e['value'][fid]['verdict']
                types[v] += 1
                if v == 'equivalent':
                    eq_all += 1
                elif v not in examples:
                    examples[v] = {'key': r['key'], 'fact_id': fid,
                                   'reason': e['value'][fid]['reason']}
        labs = {}
        for chk in ('extraction', 'board'):
            rec = labels.get(f"audit/{r['key']}/{chk}", {})
            if rec.get('status') != 'ok':
                labs = None
                break
            for fid, lab in rec['value'].items():
                labs[f'{chk}/{fid}'] = lab
        if labs is None:
            per_trace.append({'key': r['key'], 'facts': len(fids), 'status': 'label_failed',
                              'audit_stage': r['audit_stage'], 'known_stage': r['known_stage']})
            continue
        facts_obj = {'facts': f['value']['facts'], 'support_sets': f['value']['support_sets']}
        trace = {'question': r['question'],
                 'source_contexts': [{'context_id': d['unit_id'], 'text': d['text']}
                                     for d in r['documents']]}
        lab, detail = diagnose_with_sharding(facts_obj, carriers_for(labs, fids), trace,
                                             correct=False)
        stage = STAGE.get(lab, lab)
        pt = {'key': r['key'], 'facts': len(fids), 'status': 'ok',
              'proxy_label': lab, 'proxy_stage': stage,
              'audit_label': r['audit_label'], 'audit_stage': r['audit_stage'],
              'known_stage': r['known_stage'], 'old': detail.get('old'),
              'sharding_detail': detail.get('facts'), 'eq': e.get('value')}
        per_trace.append(pt)
        if stage != r['audit_stage']:
            mismatches.append({k: pt[k] for k in ('key', 'proxy_label', 'proxy_stage',
                                                  'audit_label', 'audit_stage',
                                                  'known_stage')})
    scored = [p for p in per_trace if p['status'] == 'ok']
    n = len(scored)
    agree = sum(1 for p in scored if p['proxy_stage'] == p['audit_stage'])
    agree_known = sum(1 for p in scored if p['proxy_stage'] == p['known_stage'])
    rate = agree / n if n else None
    ci = cp(agree, n) if n else None
    krate = agree_known / n if n else None
    kci = cp(agree_known, n) if n else None
    matrix = Counter((p['proxy_stage'], p['audit_stage']) for p in scored)
    mrate = eq_all / eq_n if eq_n else None
    mci = cp(eq_all, eq_n) if eq_n else None
    out = {
        'traces': len(rows), 'facts_generation_failed': gen_failed,
        'facts_total': sum(p['facts'] for p in per_trace),
        'match': {'equivalent': eq_all, 'n': eq_n, 'rate': mrate, 'ci': list(mci) if mci else None,
                  'by_verdict': dict(types), 'examples': examples},
        'stage': {'n_scored': n, 'agree': agree, 'rate': rate, 'ci': list(ci) if ci else None,
                  'agree_known': agree_known, 'rate_known': krate,
                  'ci_known': list(kci) if kci else None,
                  'matrix': {f'{a}->{b}': c for (a, b), c in sorted(matrix.items())},
                  'mismatches': mismatches},
        'per_trace': per_trace,
        'spend_usd': round(spent(), 8), 'cap_usd': CAP,
    }
    RESULTS.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    write_report(out, rows)
    print(json.dumps(out, indent=1, ensure_ascii=False))


def write_report(out, rows):
    m, s = out['match'], out['stage']
    spend = out['spend_usd']
    per_trace_cost = spend / len(rows) if rows else 0.0
    lines = [
        '# Proxy support for the audit stage diagnosis: pilot',
        '',
        '2026-11-15. Rule `Proxy-support-pilot-v1.md` (frozen, hashed), facts prompt '
        '`proxy_facts_prompt_v1.json`, equivalence prompt `proxy_support_equiv_prompt_v1.json`, '
        'labeller prompt v3 (system `3f7f19bb…`). Qwen3-235B generates the facts; Gemini 3.6 Flash '
        'checks them against the gold supports; Haiku 5.5 runs the audit label. '
        f"Spend **${spend:.6f}**, cap $1.0.",
        '',
        '## Sample',
        f"{out['traces']} MuSiQue cases, stratified by the gold-based audit stage "
        f"({', '.join(f'{k} {v}' for k, v in sorted(Counter(r['audit_stage'] for r in rows).items()))}). "
        f"{out['facts_total']} proxy facts generated; generation failures: "
        f"{len(out['facts_generation_failed']) or 'none'}.",
        '',
        '## Proxy facts against the gold supports',
    ]
    if m['n']:
        lines += [
            f"**Match (equivalent) {m['equivalent']}/{m['n']} = {m['rate']:.3f} "
            f"[{m['ci'][0]:.3f}, {m['ci'][1]:.3f}]**, 95% Clopper-Pearson.",
            '',
            '| verdict | facts |',
            '| --- | ---: |',
        ]
        for v in ('equivalent', 'partial', 'unsupported', 'contradicted'):
            lines.append(f"| {v} | {m['by_verdict'].get(v, 0)} |")
        for v, ex in m['examples'].items():
            lines.append(f"- {v}: `{ex['key']}` {ex['fact_id']} — {ex['reason']}")
    else:
        lines.append('No fact was checked (all generations failed).')
    lines += ['', '## Stage diagnosis on proxy facts', '']
    if s['n_scored']:
        lines += [
            f"**Agreement with the gold-based audit {s['agree']}/{s['n_scored']} = "
            f"{s['rate']:.3f} [{s['ci'][0]:.3f}, {s['ci'][1]:.3f}]**; against the case's known "
            f"stage {s['agree_known']}/{s['n_scored']} = {s['rate_known']:.3f} "
            f"[{s['ci_known'][0]:.3f}, {s['ci_known'][1]:.3f}]. 95% Clopper-Pearson.",
            '',
            '| proxy stage \\ gold-audit stage | extraction | transmission | sharding | aggregation |',
            '| --- | ---: | ---: | ---: | ---: |',
        ]
        cols = ('extraction', 'transmission', 'sharding', 'aggregation')
        for a in cols:
            cells = [s['matrix'].get(f'{a}->{b}', 0) for b in cols]
            lines.append(f"| {a} | " + ' | '.join(str(c) for c in cells) + ' |')
        if s['mismatches']:
            lines += ['', 'Mismatches (proxy label, gold-audit label, known stage):', '']
            for x in s['mismatches']:
                lines.append(f"- `{x['key']}`: {x['proxy_label']} vs {x['audit_label']} "
                             f"(known {x['known_stage']})")
    else:
        lines.append('No trace reached a diagnosis.')
    lines += [
        '',
        '## Projection',
        f"Measured ${per_trace_cost:.4f}/trace. Full run over the 89 diagnosed cases "
        f"≈ ${per_trace_cost * 89:.2f}; over the 608 main-table traces ≈ "
        f"${per_trace_cost * 608:.2f}.",
        '',
        '## Ledger',
        f"Spend this pilot ${spend:.6f}.",
    ]
    REPORT.write_text('\n'.join(lines) + '\n')


def main():
    ap = argparse.ArgumentParser()
    for f in ('facts', 'equiv', 'audit', 'score', 'revalidate', 'pipeline'):
        ap.add_argument('--' + f, action='store_true', dest=f)
    ap.add_argument('--cap-usd', type=float, default=CAP)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--dir', default=None)
    a = ap.parse_args()
    if a.dir:
        configure(a.dir)
    if a.facts:
        run_facts(a.cap_usd)
    if a.revalidate:
        revalidate()
    if a.pipeline:
        pipeline(a.workers, a.cap_usd, a.limit)
    if a.equiv:
        run_equiv(a.cap_usd)
    if a.audit:
        run_audit(a.cap_usd)
    if a.score:
        score()


if __name__ == '__main__':
    main()