"""Silo-Bench presence validation (Gemini reference, Haiku labeller).

Rule: `rebuttal/pilots/20261113_sb_presence_validation/RULE.md`, frozen
before any call. 24 fresh board cases, one per (model, n_agents, protocol).

    ./run.sh python -m scripts.sb_presence_validation --build
    ./run.sh python -m scripts.sb_presence_validation --reference
    ./run.sh python -m scripts.sb_presence_validation --freeze_reference
    ./run.sh python -m scripts.sb_presence_validation --labeller
    ./run.sh python -m scripts.sb_presence_validation --report
"""
import argparse
import hashlib
import json
import math
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.coverage_validation import kappa_binary
from scripts.missing_fact_repair_pilot import cp_ci, price
from scripts.per_fact_labeller import parse as parse_lab, render
from scripts.run_e1_anchor_matcher import anchor_ids
from src.audit.critical_fact_validation import build_trace_packages

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_sb_presence_validation'
RULE = OUT / 'RULE.md'
REF_PROMPT = OUT / 'reference_prompt.json'
LAB_PROMPT = OUT / 'labeller_prompt.json'
POP = OUT / 'population.json'
BUILD = OUT / 'build_manifest.json'
REF_CALLS = OUT / 'reference_calls.jsonl'
REF_LABELS = OUT / 'reference_labels.json'
REF_MANIFEST = OUT / 'reference_manifest.json'
LAB_CALLS = OUT / 'labeller_calls.jsonl'
LAB_RESULTS = OUT / 'labeller_results.json'
REPORT = OUT / 'report.md'
GEMINI = 'google/gemini-3.6-flash'
HAIKU = 'anthropic/claude-haiku-5.5'
SEED = 43
MAX_REF = 8192
MAX_LAB = 4096
CAP_REF = 2.0
CAP_LAB = 0.5
STATUS = {'present', 'partial', 'absent'}
FID = {'faithful', 'partial', 'distorted', 'absent'}
PROTOCOLS = ['summary_exchange', 'random_relay', 'score_ranked_relay',
             'redundancy_aware_relay']
RUNS = {
    'qwen235b': [('results/run_qwen235b_n5', 5),
                 ('results/run_qwen235b_n10', 10)],
    'mistrals': [('results/run_mistrals', 5),
                 ('results/run_mistrals_n10', 10)],
    'qwen36f': [('results/run_20260523_214416', 5),
                ('results/run_silobench_n10', 10)],
}
PILOT = {'II-15_n5', 'II-18_n10', 'II-19_n5', 'III-23_n10'}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    used = set(anchor_ids()) | PILOT
    rows = []
    for model, specs in RUNS.items():
        for run, n_agents in specs:
            for proto in PROTOCOLS:
                ps = build_trace_packages(
                    dataset='silobench', run_dir=run, protocol=proto,
                    source_id=run, n_agents=n_agents)
                cand = sorted((p for p in ps if p['instance_id'] not in used),
                              key=lambda p: sha(
                                  f'43|sbval|{model}|{n_agents}|{proto}|'
                                  f'{p["instance_id"]}'))
                if not cand:
                    continue
                p = cand[0]
                facts = [{'fact_id': f'f{i+1}', 'text': s['text'],
                          'support_id': s['support_id']}
                         for i, s in enumerate(p['source_supports'])]
                rows.append({
                    'key': f'sb/{model}/{n_agents}/{proto}/{p["instance_id"]}',
                    'model': model, 'run': run, 'n_agents': n_agents,
                    'protocol': proto, 'instance_id': p['instance_id'],
                    'checkpoint': 'board', 'checkpoint_name': 'shared board',
                    'question': p['question'], 'facts': facts,
                    'entries': [{'unit_id': u['unit_id'],
                                 'agent_id': u['agent_id'],
                                 'text': u['text']}
                                for u in p['checkpoints']['board']]})
    assert len(rows) == 24, len(rows)
    POP.write_text(json.dumps(rows, ensure_ascii=False))
    BUILD.write_text(json.dumps({
        'recorded_before_reference_call': True,
        'rule_sha256': file_sha(RULE),
        'reference_prompt_sha256': file_sha(REF_PROMPT),
        'labeller_prompt_sha256': file_sha(LAB_PROMPT),
        'population_sha256': file_sha(POP),
        'cases': len(rows), 'facts': sum(len(r['facts']) for r in rows),
        'seed': SEED, 'reference_model': GEMINI, 'labeller_model': HAIKU},
        indent=1))
    print(json.dumps({'cases': len(rows),
                      'facts': sum(len(r['facts']) for r in rows),
                      'population_sha256': file_sha(POP)[:12]}, indent=1))


def parse_ref(content, fact_ids):
    obj = last_object(content or '') or {}
    items = obj.get('facts')
    if not isinstance(items, list):
        return None
    out = {}
    for x in items:
        fid = x.get('fact_id')
        if fid not in fact_ids or fid in out:
            continue
        st = str(x.get('status', '')).lower()
        fi = str(x.get('fidelity', '')).lower()
        if st not in STATUS or fi not in FID:
            return None
        units = [u for u in (x.get('unit_ids') or []) if isinstance(u, str)]
        out[fid] = {'status': st, 'fidelity': fi,
                    'unit_ids': sorted(set(units)),
                    'reason': str(x.get('reason', ''))[:200]}
    return out if set(out) == fact_ids else None


def spent(path):
    if not Path(path).exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in Path(path).read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def call(key, model, system, user, max_tokens, cap, path):
    pin, pout = ((0.10e-6, 0.50e-6) if model == HAIKU
                 else price(model))
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * pin + max_tokens * pout
    if spent(path) + est > cap:
        return None
    cid = sha('|'.join([key, model, system, user, str(max_tokens)]))
    with path.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid,
                            'model': model, 'system_sha256': sha(system),
                            'user_sha256': sha(user),
                            'max_tokens': max_tokens,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    from utility.apis.base import APIRequest
    req = APIRequest(system_query=system, user_query=user, model=model,
                     max_tokens=max_tokens, temperature=0,
                     metadata={'pilot': 'sb_presence_validation', 'key': key,
                               'openrouter_reasoning': model == GEMINI})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = 0.0 if not resp.success else (
        usage.get('prompt_tokens', est_in) * pin
        + usage.get('completion_tokens', 0) * pout)
    with path.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid,
                            'model': model, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) +
                '\n')
    return resp


def reference(workers=6):
    man = json.loads(BUILD.read_text())
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(POP) == man['population_sha256']
    spec = json.loads(REF_PROMPT.read_text())
    rows = json.loads(POP.read_text())
    for i in range(0, len(rows), workers):
        chunk = rows[i:i + workers]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(call, f"ref/{r['key']}", GEMINI,
                              spec['system'], render(r), MAX_REF, CAP_REF,
                              REF_CALLS) for r in chunk]
            for fut in as_completed(futs):
                fut.result()
        print(json.dumps({'done': min(i + workers, len(rows)),
                          'spent_usd': round(spent(REF_CALLS), 6)}),
              flush=True)


def freeze_reference():
    rows = json.loads(POP.read_text())
    calls = [json.loads(l) for l in REF_CALLS.read_text().splitlines()
             if l.strip() and json.loads(l).get('event') == 'result']
    by = {c['key']: c for c in calls}
    labels = {}
    for r in rows:
        c = by.get(f"ref/{r['key']}")
        if not c:
            raise SystemExit(f"missing reference call {r['key']}")
        lab = parse_ref(c.get('content'), {f['fact_id'] for f in r['facts']})
        if lab is None:
            raise SystemExit(f"unparsed reference {r['key']}")
        labels[r['key']] = lab
    REF_LABELS.write_text(json.dumps(
        {'_note': 'Gemini reference labels, frozen before Haiku calls',
         'model': GEMINI, 'labels': labels}, indent=1, ensure_ascii=False))
    REF_MANIFEST.write_text(json.dumps({
        'recorded_before_labeller_calls': True,
        'reference_labels_sha256': file_sha(REF_LABELS),
        'reference_calls_sha256': file_sha(REF_CALLS),
        'n': len(labels)}, indent=1))
    print(json.dumps({'labels': len(labels),
                      'sha256': file_sha(REF_LABELS)[:12]}, indent=1))


def labeller(workers=6):
    man = json.loads(REF_MANIFEST.read_text())
    assert man['recorded_before_labeller_calls']
    assert file_sha(REF_LABELS) == man['reference_labels_sha256']
    spec = json.loads(LAB_PROMPT.read_text())
    rows = json.loads(POP.read_text())
    done = {}
    if LAB_RESULTS.exists():
        done = {r['key']: r for r in
                json.loads(LAB_RESULTS.read_text())['items']
                if r.get('labeller')}
    todo = [r for r in rows if r['key'] not in done]
    for i in range(0, len(todo), workers):
        chunk = todo[i:i + workers]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(call, f"lab/{r['key']}", HAIKU,
                              spec['system'], render(r), MAX_LAB, CAP_LAB,
                              LAB_CALLS): r for r in chunk}
            for fut in as_completed(futs):
                r = futs[fut]
                resp = fut.result()
                lab = parse_lab(resp.content,
                                {f['fact_id'] for f in r['facts']}) \
                    if resp and resp.success else None
                done[r['key']] = {'key': r['key'],
                                  'model': r['model'],
                                  'n_agents': r['n_agents'],
                                  'protocol': r['protocol'],
                                  'instance_id': r['instance_id'],
                                  'facts': r['facts'],
                                  'labeller': lab}
        LAB_RESULTS.write_text(json.dumps({'items': list(done.values())},
                                          indent=1, ensure_ascii=False))
        print(json.dumps({'done': len(done), 'of': len(rows),
                          'spent_usd': round(spent(LAB_CALLS), 6)}),
              flush=True)


def agree(pairs):
    n = len(pairs)
    k = sum(a == b for a, b in pairs)
    lo, hi = cp_ci(k, n)
    return {'n': n, 'k': k, 'agreement': k / n, 'lo': lo, 'hi': hi,
            'kappa': kappa_binary(pairs)}


def kappa_ci(pairs, cluster):
    rng = random.Random(SEED)
    groups = {}
    for p, c in zip(pairs, cluster):
        groups.setdefault(c, []).append(p)
    keys = sorted(groups)
    vals = []
    for _ in range(10000):
        draw = []
        for _ in keys:
            draw += groups[keys[rng.randrange(len(keys))]]
        v = kappa_binary(draw)
        if v == v:
            vals.append(v)
    vals.sort()
    return (vals[int(.025 * len(vals))], vals[int(.975 * len(vals)) - 1]) \
        if vals else (float('nan'), float('nan'))


def report():
    rows = {r['key']: r for r in
            json.loads(LAB_RESULTS.read_text())['items']}
    ref = json.loads(REF_LABELS.read_text())['labels']
    pairs = []
    for key, r in rows.items():
        if not r.get('labeller'):
            continue
        for f in r['facts']:
            v = r['labeller'].get(f['fact_id'])
            z = ref[key].get(f['fact_id'])
            if v and z:
                pairs.append((r['instance_id'], r['n_agents'], r['protocol'],
                              v['status'] != 'absent',
                              z['status'] != 'absent'))
    pres = [(a, b) for _, _, _, a, b in pairs]
    m = agree(pres)
    kci = kappa_ci(pres, [x[0] for x in pairs])
    by_n = {}
    for inst, n, proto, a, b in pairs:
        by_n.setdefault(n, []).append((a, b))
    lines = [
        '# Silo-Bench presence validation\n',
        f"Rule `RULE.md` (sha256 `{file_sha(RULE)[:12]}`); reference labels "
        f"`reference_labels.json` (sha256 `{file_sha(REF_LABELS)[:12]}`), "
        f"frozen before the Haiku calls. Reference **Gemini 3.6 Flash**; "
        f"labeller **Claude Haiku 5.5**. {len(rows)} board cases, "
        f"{m['n']} fact comparisons; spend ${spent(REF_CALLS) + spent(LAB_CALLS):.6f}, "
        f"caps $2.00 + $0.50.\n",
        f"Presence agreement **{m['k']}/{m['n']} = {m['agreement']:.3f}** "
        f"(95% CI {m['lo']:.3f}-{m['hi']:.3f}); kappa **{m['kappa']:.3f}** "
        f"({kci[0]:.3f}-{kci[1]:.3f}) - **"
        f"{'PASS' if m['agreement'] >= .80 and m['kappa'] >= .60 else 'FAIL'}** "
        f"against 0.80/0.60.\n",
        '| n_agents | agreement | kappa |', '| --- | --- | --- |']
    for n in sorted(by_n):
        mm = agree(by_n[n])
        lines.append(f"| n={n} | {mm['k']}/{mm['n']} = "
                     f"{mm['agreement']:.3f} [{mm['lo']:.3f}, {mm['hi']:.3f}] "
                     f"| {mm['kappa']:.3f} |")
    lines += ['', 'A PASS validates the board presence label on Silo-Bench '
              'numeric shard facts, cross-model against Gemini, not author '
              'ground truth; Silo-Bench rows may then enter the table. A FAIL '
              'keeps them out and the cause is reported.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'presence': m, 'kappa_ci': kci,
                      'spend_usd': round(spent(REF_CALLS) +
                                         spent(LAB_CALLS), 8)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    for f in ('build', 'reference', 'freeze_reference', 'labeller', 'report'):
        ap.add_argument('--' + f, action='store_true', dest=f)
    ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.build:
        build()
    if a.reference:
        reference(a.workers)
    if a.freeze_reference:
        freeze_reference()
    if a.labeller:
        labeller(a.workers)
    if a.report:
        report()


if __name__ == '__main__':
    main()