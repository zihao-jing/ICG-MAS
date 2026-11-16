"""Run-time 30 with hop-by-hop fact generation (step 48). Rule rebuttal/pilots/prereg/Runtime-30-hop-fix-v1.md.

    python3 scripts/runtime30_hop.py --build    # no calls: manifest and hashes
    python3 scripts/runtime30_hop.py --pilot    # first 5 traces: facts, labels, equivalence
    python3 scripts/runtime30_hop.py --price    # no calls: projection for the rest
    python3 scripts/runtime30_hop.py --run      # remaining traces, only if projected total < $2
    python3 scripts/runtime30_hop.py --score    # no calls

Changes one thing from the 26-trace rerun: the fact generator uses the bridge-first prompt v2. Labels, gold,
equivalence prompt, merge and scoring are the rerun's own functions (scripts/runtime30_rerun.py), with its paths
pointed at the new output folder.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts.runtime30_rerun as R  # noqa: E402
from scripts.answer_equiv import last_object  # noqa: E402
from scripts.per_fact_points_run import parse as parse_labels  # noqa: E402
from scripts.proxy_support_run import render_docs, validate_facts  # noqa: E402
from utility.apis.base import APIRequest  # noqa: E402
from utility.apis.openrouter_api import single_request  # noqa: E402

P = ROOT / 'rebuttal/pilots'
OUT = P / '20261116_runtime_30_hop'
RULE = P / 'prereg/Runtime-30-hop-fix-v1.md'
FACTS_PROMPT = P / 'prereg/proxy_facts_hop_prompt_v2.json'
LABEL_PROMPT = P / 'prereg/per_fact_points_prompt_v1.json'
EQUIV_PROMPT = P / 'prereg/proxy_support_equiv_prompt_v1.json'
MQ = P / '20261115_proxy_support_mq'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
FACTS = OUT / 'facts.json'
LABELS = OUT / 'labels.json'
EQUIV = OUT / 'equiv.jsonl'
INPUTS = OUT / 'inputs.json'
QWEN = 'qwen/qwen3-235b-a22b-2507'
HAIKU = 'anthropic/claude-haiku-5.5'
PRICE = {QWEN: (0.14 / 1e6, 0.8 / 1e6), HAIKU: (0.1 / 1e6, 0.5 / 1e6), R.GEMINI: R.PRICE}
CAP = 2.00
PILOT_N = 5
MAX_TOK_LABEL = 3000

# point the rerun's functions at this attempt's files (they read these names at call time)
R.OUT, R.CALLS, R.EQUIV, R.INPUTS = OUT, CALLS, EQUIV, INPUTS


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def log(rec):
    with CALLS.open('a') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def check_cap(est):
    if spent() + est > CAP:
        raise RuntimeError(f'cap: spent {spent():.6f} + est {est:.6f} > {CAP}')


OLD_INPUTS = P / '20261116_runtime_30_rerun/inputs.json'


def base_items():
    old = json.loads(OLD_INPUTS.read_text())
    return {it['instance']: it for it in old['items']}, old['not_scoreable']


def traces():
    man = json.loads((P / '20261116_runtime_30_rerun/build_manifest.json').read_text())
    return man['scoreable_list']


def pop_rows():
    return {r['instance_id']: r for r in json.loads((MQ / 'population.json').read_text())
            if r['protocol'] == 'random_relay'}


def atoms_of(text):
    return [a.strip() for a in text.replace('\n', ' ').split('. ') if len(a.strip()) > 3]


def build():
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    OUT.mkdir(parents=True, exist_ok=True)
    tr = traces()
    man = {'recorded_before_any_call': True, 'rule_sha256': sha(RULE), 'facts_prompt_sha256': sha(FACTS_PROMPT),
           'label_prompt_sha256': sha(LABEL_PROMPT), 'equiv_prompt_sha256': sha(EQUIV_PROMPT),
           'facts_model': QWEN, 'label_model': HAIKU, 'equiv_model': R.GEMINI, 'cap_usd': CAP,
           'traces': tr, 'n': len(tr)}
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps({k: v for k, v in man.items() if k != 'traces'}, indent=1))


def check_frozen():
    man = json.loads(MANIFEST.read_text())
    assert sha(RULE) == man['rule_sha256'], 'rule changed after hashing'
    assert sha(FACTS_PROMPT) == man['facts_prompt_sha256'], 'fact prompt changed after hashing'
    assert sha(LABEL_PROMPT) == man['label_prompt_sha256'], 'label prompt changed after hashing'
    assert sha(EQUIV_PROMPT) == man['equiv_prompt_sha256'], 'equivalence prompt changed after hashing'
    return man


def load(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def gen_facts(inst, row, spec, facts):
    """Qwen fact generation with bridge-first prompt v2; up to 3 attempts, validated as in v1."""
    docs = {d['unit_id'] for d in row['documents']}
    user = spec['user'].format(question=row['question'], documents=render_docs(row))
    rec, ok, attempts = None, False, 0
    for attempts in range(1, 4):
        est = math.ceil((len(spec['system']) + len(user)) / 4) * PRICE[QWEN][0] + spec['max_tokens'] * PRICE[QWEN][1]
        check_cap(est)
        log({'event': 'intent', 'key': f'facts/{inst}/attempt-{attempts}', 'model': QWEN})
        resp = single_request(APIRequest(system_query=spec['system'], user_query=user, model=QWEN,
                                         max_tokens=spec['max_tokens'], temperature=0))
        u = resp.usage or {}
        cost = u.get('prompt_tokens', 0) * PRICE[QWEN][0] + u.get('completion_tokens', 0) * PRICE[QWEN][1]
        rec = validate_facts(last_object(resp.content or ''), docs) if resp.success else None
        log({'event': 'result', 'key': f'facts/{inst}/attempt-{attempts}', 'model': QWEN, 'usage': u,
             'cost_usd': round(cost, 8), 'valid': rec is not None, 'phase': 'facts'})
        ok = rec is not None
        if ok:
            break
    facts[inst] = {'status': 'ok' if ok else 'failed', 'value': rec, 'attempts': attempts}
    FACTS.write_text(json.dumps(facts, indent=1, ensure_ascii=False))
    return ok


def label_one(inst, fid, text, row, lab_spec):
    """Haiku per-fact labels at extraction and board, rendered as in the second sample."""
    atoms = [(f'a{i}', t) for i, t in enumerate(atoms_of(text), 1)]
    stages, atom_status, valid = {}, {}, True
    for cp in ('extraction', 'board'):
        entries = row['checkpoints'].get(cp) or []
        user = lab_spec['user'].format(
            question=row['question'], fact=text,
            atoms='\n'.join(f'{a}: {t}' for a, t in atoms),
            entries='\n'.join(f"[{u['unit_id']}] (agent {u['agent_id']}) {u['text'][:1500]}" for u in entries))
        lab = None
        for retry in range(2):
            key = f'labels/{inst}/{fid}/{cp}/attempt-{retry + 1}'
            est = math.ceil((len(lab_spec['system']) + len(user)) / 4) * PRICE[HAIKU][0] + MAX_TOK_LABEL * PRICE[HAIKU][1]
            check_cap(est)
            log({'event': 'intent', 'key': key, 'model': HAIKU})
            resp = single_request(APIRequest(system_query=lab_spec['system'], user_query=user, model=HAIKU,
                                             max_tokens=MAX_TOK_LABEL, temperature=0))
            u = resp.usage or {}
            cost = u.get('prompt_tokens', 0) * PRICE[HAIKU][0] + u.get('completion_tokens', 0) * PRICE[HAIKU][1]
            lab = parse_labels(resp.content or '', {a for a, _ in atoms}) if resp.success else None
            log({'event': 'result', 'key': key, 'model': HAIKU, 'usage': u, 'cost_usd': round(cost, 8),
                 'valid': lab is not None, 'phase': 'labels'})
            if lab is not None:
                break
        if lab is None:
            valid = False
            stages[cp] = 'invalid'
        else:
            st = [v['status'] for v in lab.values()]
            stages[cp] = 'absent' if 'absent' in st else 'partial' if 'partial' in st else 'present'
            atom_status[cp] = {k: v['status'] for k, v in lab.items()}
    return {'fact_id': fid, 'stages': stages, 'atoms': atom_status, 'valid': valid}


def do_trace(inst, facts, labels, fspec, lspec, espec):
    row = pop_rows()[inst]
    if inst not in facts:
        ok = gen_facts(inst, row, fspec, facts)
    else:
        ok = facts[inst]['status'] == 'ok'
    if not ok:
        labels[inst] = {'status': 'facts_failed'}
        LABELS.write_text(json.dumps(labels, indent=1, ensure_ascii=False))
        return None
    if inst not in labels or labels[inst].get('status') != 'done':
        recs = []
        for f in facts[inst]['value']['facts']:
            recs.append(label_one(inst, f['fact_id'], f['text'], row, lspec))
        labels[inst] = {'status': 'done', 'records': recs}
        LABELS.write_text(json.dumps(labels, indent=1, ensure_ascii=False))
    return labels[inst]


def item_for(inst, old, facts, labels):
    """The rerun's item shape: gold and pieces from the 26-trace inputs; new facts and labels."""
    it = dict(old[inst])
    recs = labels[inst]['records']
    it['proxy_facts'] = facts[inst]['value']['facts']
    it['proxy_labels'] = {r['fact_id']: r['stages'] for r in recs}
    it['proxy_atoms'] = {r['fact_id']: r['atoms'] for r in recs}
    return it


def scoreable(inst, facts, labels):
    lab = labels.get(inst) or {}
    return (facts.get(inst, {}).get('status') == 'ok' and lab.get('status') == 'done'
            and all(r['valid'] for r in lab['records']))


def run_equiv(inst, old, facts, labels, espec):
    it = item_for(inst, old, facts, labels)
    est = math.ceil(len(espec['system']) / 4) * R.PRICE[0] + R.MAX_TOK * R.PRICE[1]
    check_cap(est)
    cost, valid = R.run_one(it, espec)
    return cost, valid


def done_traces():
    """Traces with a completed equivalence record (the rerun writes one line per trace to EQUIV)."""
    if not EQUIV.exists():
        return set()
    return {json.loads(l)['instance'] for l in EQUIV.read_text().splitlines() if l.strip()}


def phase(limit=None, only_if_affordable=False):
    check_frozen()
    old, _ = base_items()
    tr = traces()
    facts = load(FACTS, {})
    labels = load(LABELS, {})
    fspec = json.loads(FACTS_PROMPT.read_text())
    lspec = json.loads(LABEL_PROMPT.read_text())
    espec = json.loads(EQUIV_PROMPT.read_text())
    todo = [t for t in tr if t not in done_traces()]
    if limit is not None:
        todo = todo[:limit]
    if only_if_affordable:
        mean_trace = (spent() / max(1, len(done_traces())))
        projected = spent() + mean_trace * len(todo)
        print(json.dumps({'todo': len(todo), 'spent': round(spent(), 6), 'mean_per_trace': round(mean_trace, 6),
                          'projected_total': round(projected, 6), 'cap': CAP}))
        if projected >= CAP:
            print('NOT RUN: projected total is not under the cap')
            return
    for inst in todo:
        rec = do_trace(inst, facts, labels, fspec, lspec, espec)
        if rec is None or not scoreable(inst, facts, labels):
            print(json.dumps({'inst': inst, 'scoreable': False, 'spent': round(spent(), 6)}), flush=True)
            continue
        cost, valid = run_equiv(inst, old, facts, labels, espec)
        print(json.dumps({'inst': inst, 'equiv_valid': valid, 'cost_trace': round(cost, 6),
                          'spent': round(spent(), 6)}), flush=True)
    print(json.dumps({'spent_total': round(spent(), 6), 'traces_done': len(done_traces())}))


def price():
    tr = traces()
    n = len(done_traces())
    mean = spent() / n if n else float('nan')
    print(json.dumps({'done': n, 'remaining': len(tr) - n, 'spent': round(spent(), 6),
                      'mean_per_trace': round(mean, 6), 'projected_total': round(spent() + mean * (len(tr) - n), 6)}))


def score():
    check_frozen()
    old, not_sc = base_items()
    facts = load(FACTS, {})
    labels = load(LABELS, {})
    items, extra_not = [], []
    for inst in traces():
        if scoreable(inst, facts, labels):
            items.append(item_for(inst, old, facts, labels))
        else:
            extra_not.append(inst)
    INPUTS.write_text(json.dumps({'items': items, 'not_scoreable': not_sc + extra_not}, indent=1, ensure_ascii=False))
    R.score()


def main():
    ap = argparse.ArgumentParser()
    for a in ('--build', '--pilot', '--price', '--run', '--score'):
        ap.add_argument(a, action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.pilot:
        phase(limit=PILOT_N)
    if a.price:
        price()
    if a.run:
        phase(only_if_affordable=True)
    if a.score:
        score()


if __name__ == '__main__':
    main()
