"""Q1 30-case proxy set, gold definition amendment 1 (rule: rebuttal/pilots/prereg/Q1-gold-answer-bearing-amendment-1.md).

Gold side only. Gold atoms are the answer-bearing sentences of ALL the trace's gold supports (not gold_supports[0]).
Labeller, prompt and stage rule are the ones used in scripts/gold_side_rescore.py (Gemini 3.6 Flash, the point
prompt unchanged). Opus 5.5 reference on the extraction checkpoint through the claude CLI, cap $1.00.

    ./.conda-env/bin/python -m scripts.gold_answer_bearing_rescore --build
    ./.conda-env/bin/python -m scripts.gold_answer_bearing_rescore --run
    ./.conda-env/bin/python -m scripts.gold_answer_bearing_rescore --score
"""
import argparse
import glob
import hashlib
import json
from pathlib import Path

import scripts.gold_side_rescore as G
import scripts.q1_second_sample as S
from scripts.per_fact_points_run import parse
from src.audit.e4_fix_gates import STOP, recall
from src.eval.evaluate import normalize

ROOT = Path(__file__).resolve().parent.parent
RULE = ROOT / 'rebuttal/pilots/prereg/Q1-gold-answer-bearing-amendment-1.md'
OUT = ROOT / 'rebuttal/pilots/20261116_gold_answer_bearing'
GOLD_FILES = 'results/run_qwen235b_musique*'
CAP = 1.00
GEM = G.GEM
MANIFEST = OUT / 'build_manifest.json'
PLAN = OUT / 'plan.json'


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ftoks(s):
    return ' '.join(t for t in normalize(s) if t not in STOP)


def gold_answers(ids):
    gold = {}
    for f in glob.glob(str(ROOT / GOLD_FILES / '**' / '*.jsonl'), recursive=True) + \
            glob.glob(str(ROOT / GOLD_FILES / '*.jsonl')):
        for l in open(f):
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if r.get('id') in ids and 'gold' in r:
                gold.setdefault(r['id'], r['gold'])
    return gold


def population():
    ids = list(dict.fromkeys(json.loads(l)['instance'] for l in
                             (S.OUT / 'results.jsonl').read_text().splitlines() if l.strip()))
    pop = {r['instance_id']: r for r in json.loads((S.MQ / 'population.json').read_text())
           if r['protocol'] == 'random_relay'}
    gold = gold_answers(set(ids))
    rows = []
    for i in ids:
        t = pop[i]
        a = ftoks(gold[i])
        sents = []
        for sup in t['gold_supports']:
            for x in S.atoms_of(sup['text']):
                if a and recall(x, a) >= 0.8 and x not in sents:
                    sents.append(x)
        rows.append({'instance': i, 'answer': gold[i], 'answer_bearing': sents,
                     'supports': len(t['gold_supports'])})
    return rows, pop


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, pop = population()
    scoreable = [r for r in rows if r['answer_bearing']]
    PLAN.write_text(json.dumps({'rows': rows, 'scoreable': [r['instance'] for r in scoreable]},
                               ensure_ascii=False, indent=1))
    man = {'recorded_before_any_call': True, 'rule': str(RULE.relative_to(ROOT)),
           'rule_sha256': sha_file(RULE), 'plan_sha256': sha_file(PLAN),
           'traces': len(rows), 'scoreable': len(scoreable),
           'not_scoreable': [r['instance'] for r in rows if not r['answer_bearing']],
           'labeller': GEM, 'reference': G.OPUS_CLI, 'cap_usd': CAP}
    MANIFEST.write_text(json.dumps(man, indent=1, ensure_ascii=False))
    print(json.dumps({k: man[k] for k in ('rule_sha256', 'plan_sha256', 'traces', 'scoreable')}, indent=1))


def set_module():
    """Point the gold rescore module at this amendment: scoreable traces, answer-bearing atoms, own outputs."""
    plan = json.loads(PLAN.read_text())
    by = {r['instance']: r for r in plan['rows']}
    ids = plan['scoreable']
    _, pop = population()
    G.OUT = OUT
    G.CALLS = OUT / 'calls.jsonl'
    G.RESULTS = OUT / 'results.jsonl'
    G.MANIFEST = MANIFEST
    G.traces = lambda: [pop[i] for i in ids]

    def atoms_for(t):
        r = by[t['instance_id']]
        atoms = [(f'a{i}', x) for i, x in enumerate(r['answer_bearing'], 1)]
        return ' '.join(r['answer_bearing']), atoms
    G.atoms_for = atoms_for
    G.OPUS_N = 10 ** 6            # Opus on every scoreable trace (extraction checkpoint)
    G.FULL_CAP = CAP
    return ids, by


def run():
    man = json.loads(MANIFEST.read_text())
    assert sha_file(RULE) == man['rule_sha256'] and sha_file(PLAN) == man['plan_sha256'], 'amendment or plan changed'
    ids, _ = set_module()
    G.run(len(ids), CAP)


def score():
    man = json.loads(MANIFEST.read_text())
    ids, by = set_module()
    rows = [json.loads(l) for l in G.RESULTS.read_text().splitlines() if l.strip()]
    old = [json.loads(l) for l in (S.OUT / 'results.jsonl').read_text().splitlines() if l.strip()]
    proxy = {}
    for r in old:
        if r['kind'] == 'proxy':
            proxy.setdefault(r['instance'], []).append(r)
    proxy_stage = {}
    for i, facts in proxy.items():
        st = [f['stages'].get('extraction') for f in facts]
        proxy_stage[i] = ('extraction' if 'absent' in st else
                          'transmission' if any(f['stages'].get('board') == 'absent' for f in facts) else 'aggregation')
    new_stage, pairs_op, ext_pairs = {}, [], []
    for i in ids:
        g = G.last_result(i, GEM, 'extraction')
        if g is None:
            continue
        if any(v['status'] == 'absent' for v in g.values()):
            new_stage[i] = 'extraction'
        else:
            b = G.last_result(i, GEM, 'board')
            if b is None:
                continue
            new_stage[i] = 'transmission' if any(v['status'] == 'absent' for v in b.values()) else 'aggregation'
        o = [r for r in rows if r['instance'] == i and r['labeller'] == 'opus' and r['checkpoint'] == 'extraction' and r['valid']]
        if o:
            opus_absent = any(s == 'absent' for s in o[-1]['atoms'].values())
            pairs_op.append(('absent' if any(v['status'] == 'absent' for v in g.values()) else 'present',
                             'absent' if opus_absent else 'present'))
            for a in o[-1]['atoms']:
                if a in g:
                    ext_pairs.append((g[a]['status'], o[-1]['atoms'][a]))
    both = [i for i in new_stage if i in proxy_stage]
    agree = sum(1 for i in both if proxy_stage[i] == new_stage[i])
    n = len(both)
    cm = {}
    for i in both:
        k = f'{proxy_stage[i]} -> {new_stage[i]}'
        cm[k] = cm.get(k, 0) + 1

    def kap(p):
        m = len(p)
        po = sum(a == b for a, b in p) / m
        labs = {x for q in p for x in q}
        pe = sum((sum(1 for a, _ in p if a == l) / m) * (sum(1 for _, b in p if b == l) / m) for l in labs)
        return (po - pe) / (1 - pe) if pe < 1 else 1.0
    k_op = kap(pairs_op) if pairs_op else None
    ag_op = sum(1 for a, b in pairs_op if a == b) / len(pairs_op) if pairs_op else None
    atom_ag = sum(1 for a, b in ext_pairs if a == b)
    cost = G.spent()
    bars = {'stage_agreement_vs_opus>=0.90': ag_op is not None and ag_op >= 0.90,
            'kappa_vs_opus>=0.75': k_op is not None and k_op >= 0.75}
    out = {'rule_sha256': man['rule_sha256'], 'scoreable_traces': len(ids), 'new_gold_stage_scored': n,
           'proxy_vs_new_gold_agree': agree, 'confusion_proxy_to_new_gold': cm,
           'new_gold_stage_counts': {s: sum(1 for v in new_stage.values() if v == s) for s in set(new_stage.values())},
           'old_figure': {'agree': 6, 'n': 30, 'note': 'first-support gold, Haiku labels (20261115_q1_second_sample/score.json)'},
           'opus_extraction_stage': {'n': len(pairs_op), 'agree': round(ag_op * len(pairs_op)) if ag_op is not None else None,
                                     'agreement': round(ag_op, 3) if ag_op is not None else None,
                                     'kappa': round(k_op, 3) if k_op is not None else None},
           'opus_atom_agreement': [atom_ag, len(ext_pairs)],
           'bars': bars, 'outcome': 'Q1 uses new figure' if all(bars.values()) else 'Q1 keeps 6/30',
           'spend_usd': round(cost, 6), 'cap_usd': CAP,
           'not_scoreable': man['not_scoreable']}
    (OUT / 'score.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--build', action='store_true')
    g.add_argument('--run', action='store_true')
    g.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    elif a.run:
        run()
    else:
        score()


if __name__ == '__main__':
    main()
