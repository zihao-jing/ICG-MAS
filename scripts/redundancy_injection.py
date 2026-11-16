"""Redundancy injection under a fixed budget (v1). Rule: rebuttal/pilots/prereg/Redundancy-injection-v1.md.

    ./.conda-env/bin/python -m scripts.redundancy_injection --build    # manifest + hand-check, no calls
    nohup ./.conda-env/bin/python -m scripts.redundancy_injection --run > rebuttal/pilots/20261115_redundancy_injection/run.log 2>&1 &

Each agent sends k = 2 units. Duplicated condition adds one exact copy of the agent's top-scored unit (new id).
Selections: score ranking (top k) and the paper's redundancy-aware selection (src/protocols/relay._redundancy_select,
rho = 0.5). The aggregation prompt and model are the stored ones (scripts/injection_experiment).
"""
import argparse
import hashlib
import json
from pathlib import Path

import scripts.injection_experiment as X
import scripts.injection_amendA as A
from scripts.injection_experiment import MODELS, CAP
from src.protocols.relay import _redundancy_select

ROOT = Path(__file__).resolve().parent.parent
RULE = ROOT / 'rebuttal/pilots/prereg/Redundancy-injection-v1.md'
OUT = ROOT / 'rebuttal/pilots/20261115_redundancy_injection'
BUILD = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
HANDCHECK = OUT / 'handcheck.md'
K = 2
RHO = 0.5
CAP_USD = 2.0
PER_MODEL = 30


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def val(sc):
    return sc.get('composite', sc.get('overall', 0.0))


def pool_by_agent(pkg):
    out = {}
    for u in pkg['checkpoints']['extraction']:
        out.setdefault(u['agent_id'], []).append(u)
    return out


def case_pools(model, inst, dup):
    pkg = A.pkgs(model)[inst]
    scores = A.scores_for(model).get(inst, {})
    pools = {}
    for a, units in sorted(pool_by_agent(pkg).items()):
        sc = list(scores.get(a) or [])
        sc = [sc[i] if i < len(sc) else {'composite': 0.5} for i in range(len(units))]
        items = [{'unit_id': u['unit_id'], 'text': u['text'], 'score': s} for u, s in zip(units, sc)]
        if dup:
            top = max(range(len(items)), key=lambda i: (val(items[i]['score']), -i))
            items.append({'unit_id': f'dup:a{a}', 'text': items[top]['text'], 'score': dict(items[top]['score']),
                          'copy_of': items[top]['unit_id']})
        pools[a] = items
    return pkg, pools


def select(items, protocol):
    texts = [i['text'] for i in items]
    scs = [i['score'] for i in items]
    if protocol == 'score_ranked':
        order = sorted(range(len(items)), key=lambda i: -val(scs[i]))[:K]
    else:
        chosen = _redundancy_select(texts, scs, K, RHO)
        order = [texts.index(t) for t in chosen]
    return [items[i] for i in order]


def cases():
    el = X.eligible(A.recs())
    out = []
    for m in MODELS:
        for inst in el[m][:PER_MODEL]:
            out.append((m, inst))
    return out


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    cs = cases()
    counts = {'cases': len(cs), 'by_model': {m: sum(1 for c in cs if c[0] == m) for m in MODELS}}
    man = {'recorded_before_any_call': True, 'rule_file': str(RULE.relative_to(ROOT)),
           'rule_sha256': file_sha(RULE), 'code_file': str(Path(__file__).resolve().relative_to(ROOT)),
           'code_sha256': file_sha(Path(__file__)), 'cap_usd': CAP_USD, 'k': K, 'rho': RHO,
           'cases': [{'model': m, 'instance': i} for m, i in cs], 'counts': counts}
    # verification 1: duplicates enter the pool; verification 2: hand-check trace
    dup_ok = 0
    for m, i in cs:
        _, base = case_pools(m, i, dup=False)
        _, dupd = case_pools(m, i, dup=True)
        for a in base:
            assert len(dupd[a]) == len(base[a]) + 1
            dup_ok += 1
    man['verified_pools_with_duplicate'] = dup_ok
    m0, i0 = cs[0]
    pkg, base = case_pools(m0, i0, dup=False)
    _, dupd = case_pools(m0, i0, dup=True)
    a0 = sorted(base)[0]
    lines = [f'# Hand check, first case: {m0} {i0}, agent {a0}', '',
             f'Question: {pkg["question"]}', '', '## Base pool (text, score composite)']
    lines += [f'- {i["unit_id"]} score {val(i["score"]):.3f}: {i["text"][:160]}' for i in base[a0]]
    lines += ['', '## Duplicated pool']
    lines += [f'- {i["unit_id"]} score {val(i["score"]):.3f}' + (f' (copy of {i["copy_of"]})' if 'copy_of' in i else '')
              for i in dupd[a0]]
    for name, pool in (('base', base), ('duplicated', dupd)):
        for proto in ('score_ranked', 'redundancy_aware'):
            sel = select(pool[a0], proto)
            lines.append(f'- {name} / {proto}: ' + ', '.join(s['unit_id'] for s in sel))
    lines += ['', 'Check: under score_ranked the duplicated condition must select the duplicate; under redundancy_aware it must not.']
    HANDCHECK.write_text('\n'.join(lines) + '\n')
    man['handcheck_file'] = str(HANDCHECK.relative_to(ROOT))
    BUILD.write_text(json.dumps(man, indent=1))
    print(json.dumps(counts, indent=1), 'verified_pools_with_duplicate', dup_ok)
    print('\n'.join(lines))


def check_frozen():
    man = json.loads(BUILD.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(Path(__file__)) == man['code_sha256'], 'code changed'
    return man


def run():
    man = check_frozen()
    ledger = X.Ledger(CALLS, CAP_USD)
    res = json.loads(RESULTS.read_text()) if RESULTS.exists() else {'cases': []}
    done = {(r['model'], r['instance']) for r in res['cases']}
    stopped = None
    try:
        for c in man['cases']:
            m, inst = c['model'], c['instance']
            if (m, inst) in done:
                continue
            pkg = A.pkgs(m)[inst]
            rec = {'model': m, 'instance': inst, 'gold': pkg['gold_answer'], 'arms': {}}
            for cond in ('base', 'duplicated'):
                _, pools = case_pools(m, inst, dup=(cond == 'duplicated'))
                for proto in ('score_ranked', 'redundancy_aware'):
                    board = [[i['text'] for i in select(pools[a], proto)] for a in sorted(pools)]
                    chosen = [[i['unit_id'] for i in select(pools[a], proto)] for a in sorted(pools)]
                    text_board = ' '.join(t for agent in board for t in agent)
                    raw = ledger.call(f'redund/{m}/{inst}/{cond}/{proto}/aggregate', MODELS[m],
                                      [{'role': 'system', 'content': X._AGGREGATION_SYSTEM},
                                       {'role': 'user', 'content': X._build_evidence_board_prompt(board, pkg['question'])}],
                                      max_tokens=4096)
                    pred = X.extract_answer(raw)
                    f1 = X.answer_f1(pred, {'answer': pkg['gold_answer']})
                    rec['arms'][f'{cond}/{proto}'] = {
                        'f1': f1, 'pred': pred, 'chosen_units': chosen,
                        'gold_string_in_board': pkg['gold_answer'].lower() in text_board.lower(),
                        'duplicate_selected': any(u.startswith('dup:') for agent in chosen for u in agent)}
            res['cases'].append(rec)
            res['spend_usd'] = round(ledger.spent, 6)
            RESULTS.write_text(json.dumps(res, indent=1, ensure_ascii=False))
            print(json.dumps({'model': m, 'instance': inst, 'spent': round(ledger.spent, 6),
                              'n': len(res['cases'])}), flush=True)
    except RuntimeError as e:
        stopped = str(e)
    print(json.dumps({'stopped': stopped, 'spend_usd': round(ledger.spent, 6)}), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.run:
        run()
