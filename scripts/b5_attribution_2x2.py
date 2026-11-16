"""B5: attribution 2x2 (audit vs Who&When judge; Qwen vs Gemini) on the 89 known-stage cases.

Rule `rebuttal/pilots/prereg/B5-attribution-2x2.md`, frozen before any call.

    ./run.sh python -m scripts.b5_attribution_2x2 --build
    ./run.sh python -m scripts.b5_attribution_2x2 --validate
    ./run.sh python -m scripts.b5_attribution_2x2 --run
    ./run.sh python -m scripts.b5_attribution_2x2 --score
"""
import argparse
import hashlib
import json
import math
import random
import time
from collections import Counter
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.audit_diagnosis_89 import MAP, accepted, corrupted, packages, records
from scripts.run_e1_anchor_matcher import adapt
from src.audit.matcher_v2 import (CARRIER_PROMPT, carrier_schema, match_trace, strict_parse,
                                  structured_call)
from src.audit.semantic_matcher import validate_carriers
from src.audit.sharding_check import diagnose_with_sharding

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_b5_attribution_2x2'
RULE = ROOT / 'rebuttal/pilots/prereg/B5-attribution-2x2.md'
CASES = ROOT / 'rebuttal/pilots/20261113_attribution_comparison/cases_v2.json'
JUDGE_PROMPT = ROOT / 'rebuttal/pilots/20261113_attribution_comparison/attribution_prompt_v1.json'
EARLIER_JUDGE = ROOT / 'rebuttal/pilots/20261113_attribution_comparison/results_v2.json'
EARLIER_AUDIT = ROOT / 'rebuttal/pilots/20261113_audit_diagnosis_89/audit_results.json'
MATCHER_DIR = ROOT / 'rebuttal/results/batch1/expansion_stage2/matcher'
VAL = OUT / 'validation_sample.json'
MANIFEST = OUT / 'build_manifest.json'
VAL_CALLS = OUT / 'validation_calls.jsonl'
RUN_CALLS = OUT / 'calls.jsonl'
VAL_RESULTS = OUT / 'validation_results.json'
AUDIT_RESULTS = OUT / 'audit_gemini.json'
JUDGE_RESULTS = OUT / 'judge_qwen.json'
SCORE = OUT / 'score.json'
REPORT = OUT / 'report.md'
QWEN = 'qwen/qwen3-235b-a22b-2507'
GEMINI = 'google/gemini-3.6-flash'
PRICE = {QWEN: (0.14 / 1e6, 0.8 / 1e6), GEMINI: (0.75 / 1e6, 3.75 / 1e6)}
MAX_OUT = 4096
VAL_N = 20
VAL_CAP = 0.5
RUN_CAP = 4.0
CHUNK = 0.9
SEED_SAMPLE = 44
SEED_BOOT = 43
AMEND = ROOT / 'rebuttal/pilots/prereg/B5-attribution-2x2-amendment-1.md'
MANIFEST_A = OUT / 'build_manifest_a.json'
VAL_A_CALLS = OUT / 'validation_a_calls.jsonl'
VAL_A_RESULTS = OUT / 'validation_a_results.json'
AUDIT_A_RESULTS = OUT / 'audit_a_gemini.json'
SCORE_A = OUT / 'score_a.json'
INJ_CALLS = ROOT / 'rebuttal/pilots/20261113_audit_diagnosis_89/matcher_run/calls.jsonl'
STAGES = ('extraction', 'sharding', 'transmission', 'aggregation', 'uncertain')


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class Ledger:
    """Minimal intent/result ledger with a cap on actual spend and content reuse by call id."""

    def __init__(self, path, cap):
        self.path = path
        self.cap = cap
        self.rows = ([json.loads(l) for l in path.read_text().splitlines() if l.strip()]
                     if path.exists() else [])
        self.done = {r['call_id']: r for r in self.rows
                     if r.get('event') == 'result' and r.get('success')}
        self.spent = sum(r.get('cost_usd') or 0.0 for r in self.rows if r.get('event') == 'result')

    def call(self, key, model, messages, max_tokens=MAX_OUT, temperature=0, response_format=None):
        pin, pout = PRICE[model]
        cid = sha('|'.join([key, model, json.dumps(messages, sort_keys=True), str(max_tokens),
                            json.dumps(response_format, sort_keys=True)]))
        if cid in self.done:
            return self.done[cid]['content']
        est_in = math.ceil(sum(len(str(m.get('content', ''))) for m in messages) / 4)
        if self.spent + est_in * pin + max_tokens * pout > self.cap:
            raise RuntimeError('cap')
        intent = {'event': 'intent', 'call_id': cid, 'key': key, 'model': model,
                  'prompt_sha256': sha(json.dumps(messages, sort_keys=True)),
                  'max_tokens': max_tokens, 'temperature': temperature,
                  'response_format': response_format, 'time': time.time()}
        with self.path.open('a') as f:
            f.write(json.dumps(intent) + '\n')
        t = time.monotonic()
        try:
            if model == GEMINI:
                # Transport adaptation (recorded in the rule/report): the Gemini provider path rejects the
                # OpenAI client's response_format parameter (connection error for every variant), so the call
                # goes through the project client without it. The JSON schema is still in the system message
                # that match_trace builds, and the frozen strict parser validates the output.
                from utility.apis.base import APIRequest
                from utility.apis.openrouter_api import single_request
                system = '\n'.join(str(m.get('content', '')) for m in messages
                                   if m.get('role') == 'system')
                user = '\n'.join(str(m.get('content', '')) for m in messages
                                 if m.get('role') != 'system')
                resp = single_request(APIRequest(system_query=system, user_query=user, model=model,
                                                 max_tokens=max_tokens, temperature=temperature,
                                                 metadata={'pilot': 'b5_attribution_2x2'}))
                usage = resp.usage or {}
                content = resp.content or '' if resp.success else ''
                if not resp.success:
                    raise RuntimeError(resp.error or 'single_request failed')
            else:
                from utility.apis.openrouter_api import _get_client
                client = _get_client().with_options(max_retries=0)
                extra = {'response_format': response_format} if response_format else {}
                raw = client.chat.completions.create(model=model, messages=messages,
                                                     temperature=temperature, max_tokens=max_tokens,
                                                     seed=42, **extra).model_dump()
                usage = raw.get('usage') or {}
                content = raw['choices'][0]['message'].get('content') or ''
            cost = (usage.get('prompt_tokens', est_in) * pin
                    + usage.get('completion_tokens', 0) * pout)
            row = dict(intent, event='result', success=True, content=content, usage=usage,
                       cost_usd=round(cost, 8), seconds=time.monotonic() - t)
        except Exception as exc:
            row = dict(intent, event='result', success=False, content='',
                       error=type(exc).__name__ + ': ' + str(exc), cost_usd=0.0,
                       seconds=time.monotonic() - t)
        with self.path.open('a') as f:
            f.write(json.dumps(row) + '\n')
        self.rows.append(row)
        self.spent += row.get('cost_usd') or 0.0
        if not row['success']:
            raise RuntimeError(row['error'])
        self.done[cid] = row
        return content


def stage_of(label):
    return MAP.get(label) or 'uncertain'


def kappa_cat(a, b, K):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 0.0


def boot_pairs(pairs, draws=2000, seed=SEED_BOOT):
    """pairs: list of (a_ok, b_ok, cluster). Returns (diff, lo, hi) of mean(a_ok-b_ok)."""
    rng = random.Random(seed)
    clusters = {}
    for a, b, c in pairs:
        clusters.setdefault(c, []).append(a - b)
    keys = sorted(clusters)
    out = []
    for _ in range(draws):
        vals = [v for _ in range(len(keys)) for v in clusters[rng.choice(keys)]]
        out.append(sum(vals) / len(vals))
    out.sort()
    d = sum(a - b for a, b, _ in pairs) / len(pairs)
    return d, out[int(0.025 * draws)], out[int(0.975 * draws) - 1]


def cp(k, n):
    if n == 0:
        return 0.0, 1.0

    def cdf(p, upto):
        lp, lq = math.log(p), math.log(1 - p)
        return math.fsum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                                  + i * lp + (n - i) * lq) for i in range(upto + 1))

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


def build():
    cases = json.loads(CASES.read_text())
    recs = records()
    used = {(c['key'].split('/')[1], c['key'].split('/')[2]) for c in cases}
    pool = sorted([k for k, r in recs.items()
                   if r.get('status') == 'ok' and k not in used],
                  key=lambda k: sha(f'{SEED_SAMPLE}|b5val|{k[0]}|{k[1]}'))
    sample = []
    for model, inst in pool[:VAL_N]:
        r = recs[(model, inst)]
        sample.append({'key': f'val/{model}/{inst}', 'model': model, 'instance': inst,
                       'ref_label': r.get('diagnosis'), 'ref_stage': stage_of(r.get('diagnosis'))})
    OUT.mkdir(parents=True, exist_ok=True)
    VAL.write_text(json.dumps(sample, ensure_ascii=False))
    man = {'recorded_before_any_call': True,
           'rule_sha256': file_sha(RULE), 'cases_sha256': file_sha(CASES),
           'judge_prompt_sha256': file_sha(JUDGE_PROMPT),
           'matcher_records_dir': str(MATCHER_DIR.relative_to(ROOT)),
           'earlier_judge_sha256': file_sha(EARLIER_JUDGE),
           'earlier_audit_sha256': file_sha(EARLIER_AUDIT),
           'validation_sample_sha256': file_sha(VAL),
           'validation_n': len(sample), 'validation_seed': SEED_SAMPLE,
           'validation_cap_usd': VAL_CAP, 'run_cap_usd': RUN_CAP, 'chunk_usd': CHUNK,
           'models': {'qwen': QWEN, 'gemini': GEMINI},
           'stage_counts': dict(Counter(s['ref_stage'] for s in sample))}
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def check_frozen():
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(CASES) == man['cases_sha256'], 'cases changed'
    assert file_sha(VAL) == man['validation_sample_sha256'], 'validation sample changed'
    return man


def validate():
    man = check_frozen()
    sample = json.loads(VAL.read_text())
    done = ({r['key']: r for r in json.loads(VAL_RESULTS.read_text())['items']}
            if VAL_RESULTS.exists() else {})
    ledger = Ledger(VAL_CALLS, VAL_CAP)
    pk = {m: packages(m) for m in {s['model'] for s in sample}}
    for s in sample:
        if s['key'] in done:
            continue
        trace = pk[s['model']][s['instance']]
        try:
            res = match_trace(ledger, 'val/' + s['key'], adapt(trace), GEMINI)
        except RuntimeError as exc:
            print(json.dumps({'stopped': str(exc), 'spent': round(ledger.spent, 6)}))
            break
        if res.get('status') != 'ok':
            done[s['key']] = {**{k: s[k] for k in ('key', 'model', 'instance')},
                              'ref_stage': s['ref_stage'], 'stage': None,
                              'status': 'matcher_failed', 'failure': res.get('failure_stage')}
        else:
            new, detail = diagnose_with_sharding(res['facts'], res['carriers'], trace, correct=False)
            done[s['key']] = {**{k: s[k] for k in ('key', 'model', 'instance')},
                              'ref_stage': s['ref_stage'], 'stage': stage_of(new),
                              'label': new, 'status': 'ok'}
        VAL_RESULTS.write_text(json.dumps({'items': list(done.values())}, indent=1))
        print(json.dumps({'key': s['key'], 'stage': done[s['key']]['stage'],
                          'ref': s['ref_stage'], 'spent': round(ledger.spent, 6)}), flush=True)
    a = [r['ref_stage'] for r in done.values() if r.get('stage')]
    b = [r['stage'] for r in done.values() if r.get('stage')]
    if a:
        agree = sum(x == y for x, y in zip(a, b)) / len(a)
        kap = kappa_cat(a, b, STAGES)
        pairs = [(x == y, 1 if False else x == y, r['instance'])
                 for x, y, r in ((r['ref_stage'], r['stage'], r) for r in done.values() if r.get('stage'))]
        # agreement CI by cluster bootstrap on identical-vs-not
        rng = random.Random(SEED_BOOT)
        cl = {}
        for x, y, r in ((r['ref_stage'], r['stage'], r) for r in done.values() if r.get('stage')):
            cl.setdefault(r['instance'], []).append(x == y)
        keys = sorted(cl)
        draws = sorted(sum(v for _ in range(len(keys)) for v in cl[rng.choice(keys)]) / len(keys)
                       for _ in range(2000))
        ci = (draws[49], draws[1949])
        out = {'n': len(a), 'agreement': agree, 'agreement_ci': list(ci), 'kappa': kap,
               'bars': {'agreement': 0.8, 'kappa': 0.6},
               'passes': agree >= 0.8 and kap >= 0.6,
               'spend_usd': round(ledger.spent, 6), 'cells': dict(Counter(f'{x}->{y}' for x, y in zip(a, b)))}
        (OUT / 'validation.json').write_text(json.dumps(out, indent=1))
        print(json.dumps(out, indent=1))


def qwen_facts_carriers():
    """Frozen Qwen facts and carriers for all 89 cases (cohort from matcher records, injected from its ledger)."""
    cases = json.loads(CASES.read_text())
    recs = records()
    inj = {}
    for l in INJ_CALLS.read_text().splitlines():
        if not l.strip():
            continue
        e = json.loads(l)
        if e.get('event') != 'result' or not e.get('success'):
            continue
        k = e['key']
        if k.endswith('/facts/attempt-1'):
            inj.setdefault(k.split('/attempt-')[0].rsplit('/facts', 1)[0], {})['facts'] = strict_parse(e['content'])
        elif k.endswith('/carriers/attempt-1'):
            inj.setdefault(k.split('/attempt-')[0].rsplit('/carriers', 1)[0], {})['carriers'] = strict_parse(e['content'])
    out = {}
    for c in cases:
        model, inst = c['key'].split('/')[1], c['key'].split('/')[2]
        if c['population'] == 'cohort':
            r = recs[(model, inst)]
            out[c['key']] = {'facts': r['facts'], 'carriers': r['carriers']}
        else:
            x = inj.get(f'audit-inj/{model}/{inst}')
            out[c['key']] = {'facts': x['facts'], 'carriers': x['carriers']} if x else None
    return out


def carrier_step(ledger, key, at, facts, model):
    def valid(x):
        validate_carriers(x, facts, at)
        for row in x['facts']:
            for cp in ('extraction', 'board'):
                for c in row[cp]:
                    if c['role'] == 'joint' and len(c['unit_ids']) < 2:
                        raise ValueError('Joint carrier needs at least two units')
    payload = {'question': at['question'], 'facts': facts,
               'source_contexts': at['source_contexts'],
               'extraction': at['checkpoints']['extraction'],
               'board': at['checkpoints']['board']}
    return structured_call(ledger, key + '/carriers', model, CARRIER_PROMPT, payload,
                           carrier_schema(facts, at), valid)


def carrier_presence(carriers):
    """{(fact_id, checkpoint): bool} - a faithful carrier is present."""
    out = {}
    for row in carriers['facts']:
        for cp in ('extraction', 'board'):
            out[(row['fact_id'], cp)] = any(c['fidelity'] == 'faithful' for c in row[cp])
    return out


def build_a():
    assert AMEND.exists()
    man = {'recorded_before_any_call': True,
           'amendment_sha256': file_sha(AMEND),
           'parent_rule_sha256': file_sha(RULE),
           'cases_sha256': file_sha(CASES),
           'validation_sample_sha256': file_sha(VAL),
           'judge_prompt_sha256': file_sha(JUDGE_PROMPT),
           'earlier_judge_sha256': file_sha(EARLIER_JUDGE),
           'earlier_audit_sha256': file_sha(EARLIER_AUDIT),
           'injected_qwen_ledger_sha256': file_sha(INJ_CALLS),
           'validation_cap_usd': VAL_CAP, 'run_cap_usd': RUN_CAP, 'chunk_usd': CHUNK,
           'design': 'audit row: Gemini carrier labels on fixed Qwen facts; judge row: whole judge swap'}
    MANIFEST_A.write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def check_frozen_a():
    man = json.loads(MANIFEST_A.read_text())
    assert file_sha(AMEND) == man['amendment_sha256'], 'amendment changed'
    assert file_sha(CASES) == man['cases_sha256'], 'cases changed'
    assert file_sha(VAL) == man['validation_sample_sha256'], 'validation sample changed'
    return man


def validate_a():
    check_frozen_a()
    sample = json.loads(VAL.read_text())
    recs = records()
    done = ({r['key']: r for r in json.loads(VAL_A_RESULTS.read_text())['items']}
            if VAL_A_RESULTS.exists() else {})
    ledger = Ledger(VAL_A_CALLS, VAL_CAP)
    pk = {m: packages(m) for m in {s['model'] for s in sample}}
    for s in sample:
        if s['key'] in done:
            continue
        t = pk[s['model']][s['instance']]
        at = adapt(t)
        q = recs[(s['model'], s['instance'])]
        facts, qc = q['facts'], q['carriers']
        try:
            res = carrier_step(ledger, 'vala/' + s['key'], at, facts, GEMINI)
        except RuntimeError as exc:
            print(json.dumps({'stopped': str(exc), 'spent': round(ledger.spent, 6)}))
            break
        if res.get('status') != 'ok':
            done[s['key']] = {'key': s['key'], 'status': 'failed'}
        else:
            done[s['key']] = {'key': s['key'], 'status': 'ok', 'gemini': res['value'],
                              'qwen': qc, 'instance': s['instance']}
        VAL_A_RESULTS.write_text(json.dumps({'items': list(done.values())}, indent=1))
        print(json.dumps({'key': s['key'], 'status': done[s['key']]['status'],
                          'spent': round(ledger.spent, 6)}), flush=True)
    a, b, cl = [], [], []
    for r in done.values():
        if r.get('status') != 'ok':
            continue
        g, q = carrier_presence(r['gemini']), carrier_presence(r['qwen'])
        for k in sorted(set(q) & set(g)):
            a.append(q[k])
            b.append(g[k])
            cl.append(r['instance'])
    if a:
        agree = sum(x == y for x, y in zip(a, b)) / len(a)
        kap = kappa_cat([str(x) for x in a], [str(x) for x in b], ('True', 'False'))
        rng = random.Random(SEED_BOOT)
        groups = {}
        for x, y, c in zip(a, b, cl):
            groups.setdefault(c, []).append(x == y)
        keys = sorted(groups)
        def draw():
            vals = [v for _ in range(len(keys)) for v in groups[rng.choice(keys)]]
            return sum(vals) / len(vals)
        draws = sorted(draw() for _ in range(2000))
        out = {'n_units': len(a), 'agreement': agree, 'agreement_ci': [draws[49], draws[1949]],
               'kappa': kap, 'bars': {'agreement': 0.8, 'kappa': 0.6},
               'passes': agree >= 0.8 and kap >= 0.6, 'spend_usd': round(ledger.spent, 6)}
        (OUT / 'validation_a.json').write_text(json.dumps(out, indent=1))
        print(json.dumps(out, indent=1))


def run_a():
    man = check_frozen_a()
    spec = json.loads(JUDGE_PROMPT.read_text())
    cases = json.loads(CASES.read_text())
    acc = accepted()
    pk = {m: packages(m) for m in {c['key'].split('/')[1] for c in cases}}
    qfc = qwen_facts_carriers()
    judge = ({r['key']: r for r in json.loads(JUDGE_RESULTS.read_text())['items']}
             if JUDGE_RESULTS.exists() else {})
    audit = ({r['key']: r for r in json.loads(AUDIT_A_RESULTS.read_text())['items']}
             if AUDIT_A_RESULTS.exists() else {})
    ledger = Ledger(RUN_CALLS, RUN_CAP)
    chunk_start = ledger.spent
    chunk = 1
    print(json.dumps({'chunk': chunk, 'start': round(chunk_start, 6)}), flush=True)
    for c in cases:
        if ledger.spent - chunk_start > CHUNK:
            spent_chunk = ledger.spent - chunk_start
            print(json.dumps({'chunk': chunk, 'chunk_spend': round(spent_chunk, 6),
                              'overrun': spent_chunk > 1.0}), flush=True)
            if spent_chunk > 1.0:
                print(json.dumps({'stop': 'chunk overrun'}))
                break
            chunk += 1
            chunk_start = ledger.spent
            print(json.dumps({'chunk': chunk, 'start': round(chunk_start, 6)}), flush=True)
        if c['key'] not in judge:
            user = render_judge(spec, c)
            try:
                content = ledger.call('judge/' + c['key'], QWEN,
                                      [{'role': 'system', 'content': spec['system']},
                                       {'role': 'user', 'content': user}], max_tokens=2048)
            except RuntimeError as exc:
                print(json.dumps({'stopped': str(exc), 'spent': round(ledger.spent, 6)}))
                JUDGE_RESULTS.write_text(json.dumps({'items': list(judge.values())}, indent=1))
                return
            obj = last_object(content or '')
            st = str((obj or {}).get('stage', '')).lower()
            judge[c['key']] = {'key': c['key'], 'stage': st if st in STAGES[:-1] else None,
                               'population': c['population'], 'known_stage': c['known_stage']}
            JUDGE_RESULTS.write_text(json.dumps({'items': list(judge.values())}, indent=1))
        if c['key'] not in audit:
            model, inst = c['key'].split('/')[1], c['key'].split('/')[2]
            t = corrupted(c, acc) if c['population'] == 'injected' else pk[model][inst]
            qf = qfc[c['key']]
            try:
                res = carrier_step(ledger, 'audita/' + c['key'], adapt(t), qf['facts'], GEMINI)
            except RuntimeError as exc:
                print(json.dumps({'stopped': str(exc), 'spent': round(ledger.spent, 6)}))
                AUDIT_A_RESULTS.write_text(json.dumps({'items': list(audit.values())}, indent=1))
                return
            if res.get('status') != 'ok':
                audit[c['key']] = {'key': c['key'], 'stage': None, 'status': 'carrier_failed',
                                   'population': c['population'], 'known_stage': c['known_stage']}
            else:
                new, _ = diagnose_with_sharding(qf['facts'], res['value'], t, correct=False)
                audit[c['key']] = {'key': c['key'], 'stage': stage_of(new), 'label': new,
                                   'status': 'ok', 'population': c['population'],
                                   'known_stage': c['known_stage']}
            AUDIT_A_RESULTS.write_text(json.dumps({'items': list(audit.values())}, indent=1))
        print(json.dumps({'key': c['key'], 'spent': round(ledger.spent, 6)}), flush=True)
    print(json.dumps({'chunks': chunk, 'spent': round(ledger.spent, 6),
                      'judge_done': len(judge), 'audit_done': len(audit)}), flush=True)


def score_a():
    check_frozen_a()
    cases = json.loads(CASES.read_text())
    known = {c['key']: c['known_stage'] for c in cases}
    inst = {c['key']: c['key'].split('/')[2] for c in cases}
    earlier_j = _earlier(EARLIER_JUDGE, 'judge')
    earlier_a = _earlier(EARLIER_AUDIT, 'audit_stage')
    judge_q = ({r['key']: r for r in json.loads(JUDGE_RESULTS.read_text())['items']}
               if JUDGE_RESULTS.exists() else {})
    audit_g = ({r['key']: r for r in json.loads(AUDIT_A_RESULTS.read_text())['items']}
               if AUDIT_A_RESULTS.exists() else {})
    cells = {
        'audit_qwen': {k: (r.get('audit_stage') or 'uncertain') for k, r in earlier_a.items()},
        'judge_gemini': {k: r['judge']['stage'] for k, r in earlier_j.items()},
        'judge_qwen': {k: (r.get('stage') or 'uncertain') for k, r in judge_q.items()},
        'audit_gemini': {k: (r.get('stage') or 'uncertain') for k, r in audit_g.items()},
    }
    out = {'cells': {}, 'pairs': {}}
    for name, lab in cells.items():
        keys = [k for k in known if k in lab]
        ok = [lab[k] == known[k] for k in keys]
        k, n = sum(ok), len(keys)
        by = {}
        for pop, pre in (('injected', 'inj/'), ('cohort', 'coh/')):
            kk = [x for x in keys if x.startswith(pre)]
            by[pop] = {'n': len(kk), 'correct': sum(lab[x] == known[x] for x in kk)}
        out['cells'][name] = {'n': n, 'correct': k, 'accuracy': k / n if n else None,
                              'cp_ci': list(cp(k, n)) if n else None, 'by_population': by}
    for row, a, b in (('audit', 'audit_qwen', 'audit_gemini'),
                      ('judge', 'judge_qwen', 'judge_gemini')):
        A, B = cells[a], cells[b]
        keys = [k for k in known if k in A and k in B]
        pairs = [(A[k] == known[k], B[k] == known[k], inst[k]) for k in keys]
        d, lo, hi = boot_pairs(pairs)
        out['pairs'][row] = {'n': len(keys), 'qwen_acc': sum(p[0] for p in pairs) / len(pairs),
                             'gemini_acc': sum(p[1] for p in pairs) / len(pairs),
                             'diff_qwen_minus_gemini': d, 'diff_ci': [lo, hi]}
    out['spend_usd'] = round(sum((json.loads(l).get('cost_usd') or 0.0)
                                 for l in RUN_CALLS.read_text().splitlines()
                                 if l.strip() and json.loads(l).get('event') == 'result'), 6) if RUN_CALLS.exists() else 0.0
    SCORE_A.write_text(json.dumps(out, indent=1))
    write_report_a(out)
    print(json.dumps(out, indent=1))


def case_trace(c, acc, pk):
    model, inst = c['key'].split('/')[1], c['key'].split('/')[2]
    return corrupted(c, acc) if c['population'] == 'injected' else pk[model][inst]


def render_judge(spec, case):
    """Same renderer as the earlier Gemini judge run (scripts/attribution_comparison_v2.render_case)."""
    q = case['question']
    parts = [f'QUESTION\n{q}\n', 'SOURCE SHARDS BY AGENT']
    for a, text in case['source'].items():
        t = text if len(text) <= 500 else text[:500] + ' ...'
        parts.append(f'[agent {a}] {t}')
    for label, cp in (('EXTRACTION POOL', 'extraction'), ('TRANSMITTED EVIDENCE', 'transmission'),
                      ('SHARED BOARD', 'board')):
        parts.append(f'\n{label}')
        for u in case[cp]:
            t = u['text'] if len(u['text']) <= 500 else u['text'][:500] + ' ...'
            parts.append(f'[{u["unit_id"]}] (agent {u["agent_id"]}) {t}')
    parts.append(f'\nFINAL ANSWER (incorrect)\n{case["answer"]}')
    return '\n'.join(parts)


def run():
    man = check_frozen()
    spec = json.loads(JUDGE_PROMPT.read_text())
    cases = json.loads(CASES.read_text())
    acc = accepted()
    pk = {m: packages(m) for m in set(man['models'].values())}
    pk = {m: pk[m] for m in pk}
    judge = ({r['key']: r for r in json.loads(JUDGE_RESULTS.read_text())['items']}
             if JUDGE_RESULTS.exists() else {})
    audit = ({r['key']: r for r in json.loads(AUDIT_RESULTS.read_text())['items']}
             if AUDIT_RESULTS.exists() else {})
    jl = Ledger(RUN_CALLS, RUN_CAP)
    chunk_start = jl.spent
    chunk = 1
    print(json.dumps({'chunk': chunk, 'start': round(chunk_start, 6),
                      'judge_todo': len([c for c in cases if c['key'] not in judge]),
                      'audit_todo': len([c for c in cases if c['key'] not in audit])}), flush=True)
    for c in cases:
        if jl.spent - chunk_start > CHUNK:
            spent_chunk = jl.spent - chunk_start
            print(json.dumps({'chunk': chunk, 'chunk_spend': round(spent_chunk, 6),
                              'overrun': spent_chunk > 1.0}), flush=True)
            if spent_chunk > 1.0:
                print(json.dumps({'stop': 'chunk overrun'}))
                break
            chunk += 1
            chunk_start = jl.spent
            print(json.dumps({'chunk': chunk, 'start': round(chunk_start, 6)}), flush=True)
        if c['key'] not in judge:
            user = render_judge(spec, c)
            try:
                content = jl.call('judge/' + c['key'], QWEN,
                                  [{'role': 'system', 'content': spec['system']},
                                   {'role': 'user', 'content': user}],
                                  max_tokens=2048)
                obj = last_object(content or '')
                st = str((obj or {}).get('stage', '')).lower()
                judge[c['key']] = {'key': c['key'], 'stage': st if st in STAGES[:-1] else None,
                                   'population': c['population'], 'known_stage': c['known_stage']}
            except RuntimeError as exc:
                print(json.dumps({'stopped': str(exc), 'spent': round(jl.spent, 6)}))
                JUDGE_RESULTS.write_text(json.dumps({'items': list(judge.values())}, indent=1))
                return
            JUDGE_RESULTS.write_text(json.dumps({'items': list(judge.values())}, indent=1))
        if c['key'] not in audit:
            t = case_trace(c, acc, pk)
            try:
                res = match_trace(jl, 'audit/' + c['key'], adapt(t), GEMINI)
            except RuntimeError as exc:
                print(json.dumps({'stopped': str(exc), 'spent': round(jl.spent, 6)}))
                AUDIT_RESULTS.write_text(json.dumps({'items': list(audit.values())}, indent=1))
                return
            if res.get('status') != 'ok':
                audit[c['key']] = {'key': c['key'], 'stage': None, 'status': 'matcher_failed',
                                   'population': c['population'], 'known_stage': c['known_stage']}
            else:
                new, _ = diagnose_with_sharding(res['facts'], res['carriers'], t, correct=False)
                audit[c['key']] = {'key': c['key'], 'stage': stage_of(new), 'label': new,
                                   'status': 'ok', 'population': c['population'],
                                   'known_stage': c['known_stage']}
            AUDIT_RESULTS.write_text(json.dumps({'items': list(audit.values())}, indent=1))
        print(json.dumps({'key': c['key'], 'spent': round(jl.spent, 6)}), flush=True)
    print(json.dumps({'chunks': chunk, 'spent': round(jl.spent, 6),
                      'judge_done': len(judge), 'audit_done': len(audit)}), flush=True)


def _earlier(path, field):
    return {r['key']: r for r in json.loads(path.read_text())['items'] if r.get(field)}


def score():
    check_frozen()
    cases = json.loads(CASES.read_text())
    known = {c['key']: c['known_stage'] for c in cases}
    inst = {c['key']: c['key'].split('/')[2] for c in cases}
    earlier_j = _earlier(EARLIER_JUDGE, 'judge')
    earlier_a = _earlier(EARLIER_AUDIT, 'audit_stage')
    judge_q = ({r['key']: r for r in json.loads(JUDGE_RESULTS.read_text())['items']}
               if JUDGE_RESULTS.exists() else {})
    audit_g = ({r['key']: r for r in json.loads(AUDIT_RESULTS.read_text())['items']}
               if AUDIT_RESULTS.exists() else {})

    def stages(rows, field):
        return {k: (r.get(field) or 'uncertain') for k, r in rows.items()}

    cells = {
        'audit_qwen': stages(earlier_a, 'audit_stage'),
        'judge_gemini': {k: r['judge']['stage'] for k, r in earlier_j.items()},
        'judge_qwen': stages(judge_q, 'stage'),
        'audit_gemini': stages(audit_g, 'stage'),
    }
    out = {'known': {k: known[k] for k in known}, 'cells': {}, 'pairs': {}}
    for name, lab in cells.items():
        keys = [k for k in known if k in lab]
        ok = [lab[k] == known[k] for k in keys]
        k, n = sum(ok), len(keys)
        by = {}
        for pop, pre in (('injected', 'inj/'), ('cohort', 'coh/')):
            kk = [x for x in keys if x.startswith(pre)]
            by[pop] = {'n': len(kk), 'correct': sum(lab[x] == known[x] for x in kk)}
        out['cells'][name] = {'n': n, 'correct': k, 'accuracy': k / n if n else None,
                              'cp_ci': list(cp(k, n)) if n else None,
                              'by_population': by}
    for row, a, b in (('audit', 'audit_qwen', 'audit_gemini'),
                      ('judge', 'judge_qwen', 'judge_gemini')):
        A, B = cells[a], cells[b]
        keys = [k for k in known if k in A and k in B]
        pairs = [(A[k] == known[k], B[k] == known[k], inst[k]) for k in keys]
        d, lo, hi = boot_pairs(pairs)
        out['pairs'][row] = {'n': len(keys), 'qwen_acc': sum(p[0] for p in pairs) / len(pairs),
                             'gemini_acc': sum(p[1] for p in pairs) / len(pairs),
                             'diff_qwen_minus_gemini': d, 'diff_ci': [lo, hi]}
    out['spend_usd'] = round(sum((json.loads(l).get('cost_usd') or 0.0)
                                 for l in RUN_CALLS.read_text().splitlines()
                                 if l.strip() and json.loads(l).get('event') == 'result'), 6) if RUN_CALLS.exists() else 0.0
    SCORE.write_text(json.dumps(out, indent=1))
    write_report(out)
    print(json.dumps(out, indent=1))


def write_report(out):
    def pct(x):
        return '—' if x is None else '%.3f' % x

    lines = ['# Attribution 2x2: audit vs Who&When judge, Qwen vs Gemini',
             '',
             '2026-11-15. Rule `B5-attribution-2x2.md` (sha `%s...`). Population: the 89 known-stage cases '
             '(30 injected, known transmission; 59 cohort, 39 extraction / 20 sharding). Cell spend $%.6f; '
             'total cap $4.00.'
             % (file_sha(RULE)[:8], out['spend_usd']),
             '',
             '| row | Qwen-235B accuracy [95% CI] | Gemini 3.6 Flash accuracy [95% CI] |',
             '| --- | --- | --- |']
    for row, a, b in (('audit, measured diagnosis', 'audit_qwen', 'audit_gemini'),
                      ('Who&When-style judge', 'judge_qwen', 'judge_gemini')):
        A, B = out['cells'][a], out['cells'][b]
        lines.append('| %s | %s [%s, %s] (%d/%d) | %s [%s, %s] (%d/%d) |'
                     % (row, pct(A['accuracy']), '%.3f' % A['cp_ci'][0] if A['cp_ci'] else '—',
                        '%.3f' % A['cp_ci'][1] if A['cp_ci'] else '—', A['correct'], A['n'],
                        pct(B['accuracy']), '%.3f' % B['cp_ci'][0] if B['cp_ci'] else '—',
                        '%.3f' % B['cp_ci'][1] if B['cp_ci'] else '—', B['correct'], B['n']))
    lines += ['', '| row | Qwen − Gemini, paired difference [95% CI] | n |', '| --- | --- | ---: |']
    for row in ('audit', 'judge'):
        x = out['pairs'][row]
        lines.append('| %s | %+.3f [%+.3f, %+.3f] | %d |'
                     % (row, x['diff_qwen_minus_gemini'], *x['diff_ci'], x['n']))
    lines += ['', 'Paired bootstrap over cases (2,000 draws, seed 43); clusters are instances.',
              '', '## Notes',
              '- The earlier 89-case runs are the Qwen-audit and Gemini-judge columns; they stay on record '
              'labelled as the earlier run. The new columns are the Qwen judge and the Gemini audit.',
              '- Four-model distortion rates are out of the headline (kappa lower bound below .40) and are '
              'not cited.', '', '## Ledger', 'Spend $%.6f.' % out['spend_usd']]
    REPORT.write_text('\n'.join(lines) + '\n')


def write_report_a(out):
    def f(x):
        return '—' if x is None else '%.3f' % x

    val = (json.loads((OUT / 'validation_a.json').read_text())
           if (OUT / 'validation_a.json').exists() else None)
    lines = ['# Attribution 2x2 (design A): judge swap vs fixed-fact labelling swap',
             '',
             '2026-11-15. Rule `B5-attribution-2x2-amendment-1.md` (sha `%s...`), parent `B5-attribution-2x2.md` '
             '(sha `%s...`), frozen before any call. Population: the 89 known-stage cases (30 injected, known '
             'transmission; 59 cohort, 39 extraction / 20 sharding). 2x2 spend $%.6f (cap $4.00).'
             % (file_sha(AMEND)[:8], file_sha(RULE)[:8], out['spend_usd']),
             '',
             '## Design, plainly',
             '',
             '- **Judge row:** the whole judge is swapped. Same frozen `attribution_prompt_v1.json`, same case '
             'text, model Qwen-235B vs Gemini 3.6 Flash. The model regenerates everything from the trace.',
             '- **Audit row:** only the labelling model is swapped. The facts are the Qwen matcher\'s own, '
             'frozen; the carrier-labelling call (`CARRIER_PROMPT`, frozen) runs with Qwen or Gemini on the same '
             'facts and the same checkpoints; the same `diagnose_with_sharding` produces the stage.',
             '- The earlier Gemini-regenerates-its-own-facts audit failed validation (.316 agreement) and is '
             'not part of this design; it stays on record as the failed attempt.',
             '- Both rows answer whether the method or the model does the work: in the judge row the model '
             'writes the facts and the verdict; in the audit row only the carrier labels change.',
             '',
             '## Validation of the Gemini labelling step (before the 2x2)',
             '']
    if val:
        lines += ['| quantity | value [95% CI] |', '| --- | --- |',
                  '| carrier-presence agreement | %.3f [%.3f, %.3f] |'
                  % (val['agreement'], *val['agreement_ci']),
                  '| carrier-presence kappa | %.3f |' % val['kappa'],
                  '| units (fact x checkpoint) | %d |' % val['n_units'],
                  '', 'Bars .80 / .60: **%s**. Spend $%.6f.' %
                  ('PASSES' if val['passes'] else 'FAILS', val['spend_usd'])]
    lines += ['', '## Result', '',
              '| row | Qwen accuracy [95% CI] | Gemini accuracy [95% CI] |',
              '| --- | --- | --- |']
    for row, a, b in (('audit, fixed facts + carrier swap', 'audit_qwen', 'audit_gemini'),
                      ('Who&When judge, whole swap', 'judge_qwen', 'judge_gemini')):
        A, B = out['cells'][a], out['cells'][b]
        lines.append('| %s | %s [%s, %s] (%d/%d) | %s [%s, %s] (%d/%d) |'
                     % (row, f(A['accuracy']), '%.3f' % A['cp_ci'][0], '%.3f' % A['cp_ci'][1],
                        A['correct'], A['n'], f(B['accuracy']), '%.3f' % B['cp_ci'][0],
                        '%.3f' % B['cp_ci'][1], B['correct'], B['n']))
    lines += ['', '| cell | injected | cohort |', '| --- | --- | --- |']
    for name in ('audit_qwen', 'audit_gemini', 'judge_qwen', 'judge_gemini'):
        x = out['cells'][name]['by_population']
        lines.append('| %s | %d/%d | %d/%d |' % (name, x['injected']['correct'], x['injected']['n'],
                                                 x['cohort']['correct'], x['cohort']['n']))
    lines += ['', '| row | Qwen − Gemini, paired difference [95% CI] | n |', '| --- | --- | ---: |']
    for row in ('audit', 'judge'):
        x = out['pairs'][row]
        lines.append('| %s | %+.3f [%+.3f, %+.3f] | %d |'
                     % (row, x['diff_qwen_minus_gemini'], *x['diff_ci'], x['n']))
    lines += ['', 'Paired bootstrap over cases (2,000 draws, seed 43), clusters are instances. Audits and '
              'judges name a stage from the same four-class vocabulary; accuracy is against the known stage.',
              '', '## Caveat on the audit row', '',
              'The audit row\'s facts are the frozen Qwen matcher\'s own facts, and the carrier step then labels '
              'them. That fact set was generated by Qwen-235B, so the audit row may favour Qwen labelling: the '
              'Qwen advantage there (+.101) is confounded with who wrote the facts, and it cannot be read as '
              'Qwen being the better labeller in general. The Gemini-regenerates-its-own-facts design, which '
              'would remove this confound, is the design that failed validation (.316 agreement) and is not '
              'reported as a result.',
              '', '## Transport deviation', '',
              'Gemini calls ran through the project client (`single_request`) **without `response_format`**, '
              'because the provider path rejected every variant of it; the JSON schema remains in the system '
              'message and the frozen strict parser validates the output. The transport test call cost '
              '$0.008070 and is logged in `transport_test_calls.jsonl`.',
              '', '## Ledger', '2x2 spend $%.6f; validation $%.6f; transport test $0.008070.'
              % (out['spend_usd'], val['spend_usd'] if val else 0.0)]
    (OUT / 'report_a.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--validate', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    ap.add_argument('--build-a', action='store_true')
    ap.add_argument('--validate-a', action='store_true')
    ap.add_argument('--run-a', action='store_true')
    ap.add_argument('--score-a', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.validate:
        validate()
    if a.run:
        run()
    if a.score:
        score()
    if a.build_a:
        build_a()
    if a.validate_a:
        validate_a()
    if a.run_a:
        run_a()
    if a.score_a:
        score_a()