"""E1 anchor analysis (frozen pre-registration E1.md / E1-v9): fact-level agreement, trace-level binary, judge checks.

Reads (read-only):
  rebuttal/annotation/returns/E1anchor_{A,B,C,D}_labelling-v1.0.json
  rebuttal/results/batch1/E1_judge_sealed/outputs/*.json   (unsealed under UNSEAL_AUTHORISATION.md)
  rebuttal/pilots/20261108_review8/packet_private_map.json
  rebuttal/pilots/20261108_review6/e1_n80_locked_manifest.json
  rebuttal/pilots/20261108_review7/e1_anchor_locked_manifest.json

Writes: rebuttal/results/batch1/E1/anchor_agreement.json and .md

STATISTICS. Author-author fact-level rows are paired by fact_id (the two authors' fact ids agree on
every anchor trace). Presence = board carrier not absent; fidelity = the four fixed categories.
Weights w = N_h / n_anchor from the locked strata; 95% CIs are within-stratum instance-cluster
bootstrap, 2,000 draws, seed 42, percentile. No pass/fail threshold.

BLOCKED, reported in the output:
  - judge-author FACT-level kappa: the judge writes its own fact ids/texts; no author fact mapping
    or adjudicated label set exists, so facts cannot be paired without inventing an alignment.
  - matcher accuracy on held-out traces: the frozen matcher (semantic-dev-v2) has run on the 90
    anchor traces only; the 240 held-out traces have no matcher labels.

MATCHER RUNS. The first run scored 78 of 90 anchor traces and stopped after 6 failures. A single
authorised top-up (one attempt per call, same frozen prompts/settings/code) scored the 6
never-attempted traces (II-13_n10, I-02_n5, three models); all 6 succeeded. The 6 failed traces stay
unscored. Best- and worst-case bounds assign the missing 12 pairs to the author's own label
(agreement) and, for the worst case, to a different category (lost for every non-lost author label,
correct for a lost one).
"""
import hashlib, json, random
from collections import Counter, defaultdict
from pathlib import Path

RET = Path('rebuttal/annotation/returns')
SEALED = Path('rebuttal/results/batch1/E1_judge_sealed')
OUT = Path('rebuttal/results/batch1/E1')
N80 = Path('rebuttal/pilots/20261108_review6/e1_n80_locked_manifest.json')
ANC = Path('rebuttal/pilots/20261108_review7/e1_anchor_locked_manifest.json')
PMAP = Path('rebuttal/pilots/20261108_review8/packet_private_map.json')
MATCHER = Path('rebuttal/results/batch1/E1_matcher_anchor')
TOPUP = Path('rebuttal/results/batch1/E1_matcher_anchor_topup')
DRAWS, SEED = 2000, 42
PRESENT = {'faithful', 'partial', 'distorted'}
FID_CATS = ('absent', 'faithful', 'partial', 'distorted')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def author_rows():
    out = {}
    for a in 'ABCD':
        p = RET / f'E1anchor_{a}_labelling-v1.0.json'
        out[a] = {r['display_name']: r for r in json.loads(p.read_text())}
    return out


def fact_labels(row):
    """fact_id -> (presence code, fidelity code) at the board checkpoint."""
    facts = {f['fact_id'] for f in json.loads(row['answers']['critical_facts_json'])}
    cards = json.loads(row['answers']['carriers_json'])
    board = {c['fact_id']: c['fidelity'] for c in cards if c['checkpoint'] == 'board'}
    out = {}
    for fid in facts:
        f = board.get(fid, 'absent')
        if f == 'uncertain':
            out[fid] = ('uncertain', 'uncertain')
        else:
            out[fid] = ('yes' if f in PRESENT else 'no', f)
    return out


def weighted_kappa(rows, key_a, key_b, cats):
    total = sum(r['weight'] for r in rows)
    if not total:
        return None
    ca, cb = Counter(), Counter()
    agree = 0.0
    for r in rows:
        w = r['weight']
        ca[r[key_a]] += w
        cb[r[key_b]] += w
        agree += w * (r[key_a] == r[key_b])
    pe = sum(ca[c] * cb[c] for c in cats) / total ** 2
    if abs(1 - pe) < 1e-12:
        return None
    return (agree / total - pe) / (1 - pe)


def weighted_ac1(rows, key_a, key_b, cats):
    total = sum(r['weight'] for r in rows)
    if not total:
        return None
    counts = Counter()
    agree = 0.0
    for r in rows:
        w = r['weight']
        counts[r[key_a]] += w / 2
        counts[r[key_b]] += w / 2
        agree += w * (r[key_a] == r[key_b])
    q = len(cats)
    pe = sum((counts[c] / total) * (1 - counts[c] / total) for c in cats) / (q - 1)
    if abs(1 - pe) < 1e-12:
        return None
    return (agree / total - pe) / (1 - pe)


def pair_counts(rows, ka, kb):
    return {f'{a} | {b}': n for (a, b), n in Counter((r[ka], r[kb]) for r in rows).items()}


def weighted_rate(rows, fn):
    total = sum(r['weight'] for r in rows)
    return sum(r['weight'] * fn(r) for r in rows) / total if total else None


def bootstrap(rows, stat, by_instance=True):
    """Within-stratum instance-cluster bootstrap; rows already carry stratum, weight and instance_id."""
    if not rows:
        return {'estimate': None, 'lo': None, 'hi': None, 'valid_draws': 0, 'undefined_draws': DRAWS}
    groups = defaultdict(lambda: defaultdict(list))
    for r in rows:
        groups[r['stratum']][r['instance_id']].append(r)
    rng = random.Random(SEED)
    vals = []
    for _ in range(DRAWS):
        sample = []
        for h in sorted(groups):
            keys = sorted(groups[h])
            pick = rng.choices(keys, k=len(keys)) if by_instance else keys
            for k in pick:
                sample.extend(groups[h][k])
        v = stat(sample)
        if v is not None:
            vals.append(v)
    vals.sort()
    n = len(vals)
    return {'estimate': stat(rows), 'lo': vals[int(.025 * (n - 1))] if n else None,
            'hi': vals[int(.975 * (n - 1))] if n else None,
            'valid_draws': n, 'undefined_draws': DRAWS - n}


def main():
    from scripts.make_batch1_tables import check_authorisation
    check_authorisation(Path('rebuttal/results/batch1/UNSEAL_AUTHORISATION.md'))
    labels = author_rows()
    pmap = json.loads(PMAP.read_text())
    n80 = json.loads(N80.read_text())
    anc = json.loads(ANC.read_text())
    strata = {}
    for h, v in n80['strata'].items():
        for i in v['ids']:
            strata[i] = h
    war = {h: v['weight'] for h, v in anc['strata'].items()}
    # sanity: the anchor IDs and the pre-registered weights
    anc_ids = {i for v in anc['strata'].values() for i in v['ids']}
    assert len(anc_ids) == 30

    fact_rows, trace_rows = [], []
    alignment = Counter()
    for a, b in (('A', 'B'), ('C', 'D')):
        for name in sorted(set(labels[a]) & set(labels[b])):
            ra, rb = labels[a][name], labels[b][name]
            item = ra['item_id']
            inst = pmap[item]['instance_id']
            h = strata[inst]
            la, lb = fact_labels(ra), fact_labels(rb)
            alignment['traces'] += 1
            alignment['same_fact_ids'] += set(la) == set(lb)
            for fid in sorted(set(la) & set(lb)):
                pa, fa = la[fid]
                pb, fb = lb[fid]
                fact_rows.append({'instance_id': inst, 'stratum': h, 'weight': war[h],
                                  'trace': name, 'fact_id': fid,
                                  'pa': pa, 'pb': pb, 'fa': fa, 'fb': fb,
                                  'call_a': ra['answers']['binary_call'],
                                  'call_b': rb['answers']['binary_call'],
                                  'judge': None})
            trace_rows.append({'instance_id': inst, 'stratum': h, 'weight': war[h], 'trace': name,
                               'call_a': ra['answers']['binary_call'], 'call_b': rb['answers']['binary_call']})

    # judge outputs mapped to (instance, model) -> display name
    model_to_run = {'qwen235b': 1, 'gpt4omini': 2, 'gemma31b': 3}
    by_item = {}
    for r in labels['A'].values():
        by_item[r['item_id']] = r['display_name']
    for r in labels['C'].values():
        by_item[r['item_id']] = r['display_name']
    judge = {}
    sealed_files = sorted(SEALED.glob('outputs/*.json'))
    for p in sealed_files:
        d = json.loads(p.read_text())
        inst, model = d.get('instance_id'), d.get('model')
        if inst in anc_ids and model in model_to_run:
            judge[(inst, model)] = d
    mapped = 0
    for tr in trace_rows:
        # display name "Anchor Qnn run m": find the judge output for this instance and run
        name = tr['trace']
        qpart, mpart = name.split(' run ')
        model = [k for k, v in model_to_run.items() if v == int(mpart)][0]
        j = judge.get((tr['instance_id'], model))
        if j is None:
            continue
        mapped += 1
        tr['judge'] = (j.get('parsed') or {}).get('binary_call')
        tr['judge_valid'] = bool(j.get('valid'))

    # frozen matcher outputs on the same 90 anchor traces (one run; failed traces unscored)
    mcfg = json.loads(Path('rebuttal/pilots/configs/E1-anchor-matcher-frozen.json').read_text())
    mrecs = [json.loads(p.read_text()) for p in sorted((MATCHER / 'matcher').glob('*.json'))]
    mrecs += [dict(json.loads(p.read_text()), run='topup')
              for p in sorted((TOPUP / 'matcher').glob('*.json'))]
    matcher = {(d['instance_id'], d['model']): d for d in mrecs
               if d.get('status') == 'ok' and d.get('trace_call')}
    msummary = json.loads((MATCHER / 'summary.json').read_text())
    tsummary = json.loads((TOPUP / 'summary.json').read_text())
    anc_all = json.loads(ANC.read_text())
    anchor_order = [i for v in anc_all['strata'].values() for i in v['ids']]
    anchor_stratum = {i: h for h, v in anc_all['strata'].items() for i in v['ids']}
    seen = {(d['instance_id'], d['model']) for d in mrecs}
    failed_traces = [{'instance_id': d['instance_id'], 'model': d['model'],
                      'stratum': anchor_stratum[d['instance_id']],
                      'stage': 'facts' if (d.get('facts_call') or {}).get('status') == 'failed' else 'carriers'}
                     for d in mrecs if d.get('status') == 'failed']
    unattempted = [{'instance_id': i, 'model': m, 'stratum': anchor_stratum[i]}
                   for i in anchor_order for m in mcfg['source_trace_models'] if (i, m) not in seen]
    present_inst = {d['instance_id'] for d in mrecs}
    design_weight = sum(v['weight'] for v in anc_all['strata'].values())
    present_weight = sum(v['weight'] for h, v in anc_all['strata'].items()
                         if any(i in present_inst for i in v['ids']))
    for tr in trace_rows:
        qpart, mpart = tr['trace'].split(' run ')
        model = [k for k, v in model_to_run.items() if v == int(mpart)][0]
        mt = matcher.get((tr['instance_id'], model))
        tr['matcher'] = mt['trace_call'] if mt else None
        tr['answer_correct'] = bool(mt['answer_correct']) if mt else None

    # author-author fact level
    fact_pres = [r for r in fact_rows if r['pa'] != 'uncertain' and r['pb'] != 'uncertain']
    fact_fid = [r for r in fact_pres if r['fa'] != 'uncertain' and r['fb'] != 'uncertain']
    author_fact = {
        'rows': len(fact_pres), 'pairs': len(fact_rows), 'excluded_uncertain': len(fact_rows) - len(fact_pres),
        'presence_kappa': bootstrap(fact_pres, lambda rs: weighted_kappa(rs, 'pa', 'pb', ('yes', 'no'))),
        'presence_agreement': bootstrap(fact_pres, lambda rs: weighted_rate(rs, lambda r: r['pa'] == r['pb'])),
        'fidelity_kappa': bootstrap(fact_fid, lambda rs: weighted_kappa(rs, 'fa', 'fb', FID_CATS)),
        'fidelity_ac1': bootstrap(fact_fid, lambda rs: weighted_ac1(rs, 'fa', 'fb', FID_CATS)),
        'fidelity_agreement': bootstrap(fact_fid, lambda rs: weighted_rate(rs, lambda r: r['fa'] == r['fb'])),
        'presence_counts': pair_counts(fact_pres, 'pa', 'pb'),
        'fidelity_counts': pair_counts(fact_fid, 'fa', 'fb'),
    }
    # unweighted, for transparency
    def uk(rows, ka, kb, cats):
        return weighted_kappa([dict(r, weight=1) for r in rows], ka, kb, cats)
    author_fact['unweighted'] = {
        'presence_kappa': uk(fact_pres, 'pa', 'pb', ('yes', 'no')),
        'fidelity_kappa': uk(fact_fid, 'fa', 'fb', FID_CATS),
        'fidelity_ac1': weighted_ac1([dict(r, weight=1) for r in fact_fid], 'fa', 'fb', FID_CATS),
    }

    # trace-level author-author binary
    BIN = ('correct', 'reached_but_unused', 'lost', 'exclude_partial', 'exclude_uncertain')
    tr_primary = [r for r in trace_rows if r['call_a'] in BIN[:3] and r['call_b'] in BIN[:3]]
    def tr_sens(rs):
        def code(x):
            return 'lost' if x == 'exclude_partial' else x
        return [dict(r, ca=code(r['call_a']), cb=code(r['call_b'])) for r in rs
                if code(r['call_a']) in BIN[:3] and code(r['call_b']) in BIN[:3]]
    sens = tr_sens(trace_rows)
    author_trace = {
        'rows': len(tr_primary), 'excluded': len(trace_rows) - len(tr_primary),
        'kappa': bootstrap(tr_primary, lambda rs: weighted_kappa(rs, 'call_a', 'call_b', BIN[:3])),
        'agreement': bootstrap(tr_primary, lambda rs: weighted_rate(rs, lambda r: r['call_a'] == r['call_b'])),
        'counts': pair_counts(tr_primary, 'call_a', 'call_b'),
        'partial_as_lost': {'rows': len(sens),
                            'kappa': bootstrap(sens, lambda rs: weighted_kappa(rs, 'ca', 'cb', BIN[:3]))},
    }

    # judge against each author on trace binary (secondary; fact-level judge pairing is blocked)
    pair_rows = []
    for r in trace_rows:
        if r.get('judge') is None:
            continue
        for call in (r['call_a'], r['call_b']):
            pair_rows.append({'instance_id': r['instance_id'], 'stratum': r['stratum'],
                              'weight': r['weight'], 'judge': r['judge'], 'author': call})
    jp = [r for r in pair_rows if r['judge'] in BIN[:3] and r['author'] in BIN[:3]]
    judge_trace = {
        'traces': mapped, 'pairs': len(jp), 'excluded': len(pair_rows) - len(jp),
        'agreement': bootstrap(jp, lambda rs: weighted_rate(rs, lambda r: r['judge'] == r['author'])),
        'kappa': bootstrap(jp, lambda rs: weighted_kappa(rs, 'judge', 'author', BIN[:3])),
        'counts': pair_counts(jp, 'judge', 'author'),
    }

    # matcher against each author on trace binary (frozen semantic-dev-v2, anchor run)
    mrows = []
    for r in trace_rows:
        if r.get('matcher') is None:
            continue
        for call in (r['call_a'], r['call_b']):
            mrows.append({'instance_id': r['instance_id'], 'stratum': r['stratum'], 'weight': r['weight'],
                          'matcher': r['matcher'], 'author': call})
    mmp = [r for r in mrows if r['matcher'] in BIN[:3] and r['author'] in BIN[:3]]
    def present(rs, src):
        return [dict(r, ca=('lost' if r[src] == 'lost' else 'reached'), cb=('lost' if r['author'] == 'lost' else 'reached'))
                for r in rs if r[src] in BIN[:3] and r['author'] in BIN[:3]]
    def part_lost(rs):
        code = lambda x: 'lost' if x == 'exclude_partial' else x
        return [dict(r, ca=code(r['matcher']), cb=code(r['author'])) for r in mrows
                if code(r['matcher']) in BIN[:3] and code(r['author']) in BIN[:3]]
    pl = part_lost(mrows)
    matcher_trace = {
        'traces': sum(1 for r in trace_rows if r.get('matcher')),
        'planned': msummary['planned'], 'run_ok': msummary['ok'] + tsummary['ok'],
        'run_failed': msummary['failed'], 'failed_keys': msummary['failed_keys'],
        'calls_dispatched': msummary['calls_dispatched'] + tsummary['calls_dispatched'],
        'calls_failed': msummary['calls_failed'] + tsummary['calls_failed'],
        'cost_usd': round(msummary['cost_usd'] + tsummary['cost_usd'], 6),
        'first_run_ok': msummary['ok'], 'first_run_stopped_early': msummary.get('stopped_early'),
        'topup': {'attempted': tsummary['attempted'], 'ok': tsummary['ok'],
                  'failed': tsummary['failed'], 'calls': tsummary['calls_dispatched'],
                  'cost_usd': tsummary['cost_usd'], 'one_attempt': tsummary['one_attempt'],
                  'traces': [i + ' x3' for i in ['II-13_n10', 'I-02_n5']],
                  'prompt_sha256': tsummary['freeze']['prompt_sha256'],
                  'runner_sha256': tsummary['runner_sha256']},
        'frozen_utc': msummary['freeze']['frozen_utc'],
        'pairs': len(mmp), 'excluded': len(mrows) - len(mmp),
        'failed_traces': failed_traces, 'unattempted_traces': unattempted,
        'present_instances': len(present_inst),
        'design_weight_total': round(design_weight, 3), 'present_weight_total': round(present_weight, 3),
        'agreement': bootstrap(mmp, lambda rs: weighted_rate(rs, lambda r: r['matcher'] == r['author'])),
        'kappa': bootstrap(mmp, lambda rs: weighted_kappa(rs, 'matcher', 'author', BIN[:3])),
        'counts': pair_counts(mmp, 'matcher', 'author'),
        'partial_as_lost': {'rows': len(pl),
                            'kappa': bootstrap(pl, lambda rs: weighted_kappa(rs, 'ca', 'cb', BIN[:3]))},
        'present_vs_lost': {
            'unweighted_kappa': weighted_kappa([dict(r, weight=1) for r in present(mrows, 'matcher')],
                                               'ca', 'cb', ('reached', 'lost')),
            'rows': len(present(mrows, 'matcher'))},
    }
    # bounds for the traces that stay missing (the 6 failed: III-24_n5, III-27_n5 x3 models)
    failed_keys = {(f['instance_id'], f['model']) for f in failed_traces}
    missing_rows = []
    for tr in trace_rows:
        qpart, mpart = tr['trace'].split(' run ')
        model = [k for k, v in model_to_run.items() if v == int(mpart)][0]
        if (tr['instance_id'], model) not in failed_keys:
            continue
        for call in (tr['call_a'], tr['call_b']):
            if call in BIN[:3]:
                missing_rows.append({'instance_id': tr['instance_id'], 'stratum': tr['stratum'],
                                     'weight': tr['weight'], 'author': call})
    best = [dict(r, matcher=r['author']) for r in missing_rows]
    worst = [dict(r, matcher=('correct' if r['author'] == 'lost' else 'lost')) for r in missing_rows]
    matcher_trace['bounds'] = {
        'rule': 'best: every missing pair takes the author label (agreement); worst: every missing '
                'pair takes a different category (lost for a non-lost author label, correct for lost)',
        'missing_traces': len(failed_keys), 'missing_pairs': len(missing_rows),
        'scored_pairs': len(mmp),
        'agreement': {'best': weighted_rate(mmp + best, lambda r: r['matcher'] == r['author']),
                      'worst': weighted_rate(mmp + worst, lambda r: r['matcher'] == r['author'])},
        'kappa': {'best': weighted_kappa(mmp + best, 'matcher', 'author', BIN[:3]),
                  'worst': weighted_kappa(mmp + worst, 'matcher', 'author', BIN[:3])},
        'note': 'point estimates under the design weights; no interval is attached to a bound',
    }
    # author 'correct' vs the benchmark's answer_correct flag (definition gap, descriptive)
    gaps = []
    for r in trace_rows:
        if r.get('answer_correct') is None:
            continue
        ac = r['call_a'] == 'correct' or r['call_b'] == 'correct'
        if ac != r['answer_correct']:
            gaps.append({'trace': r['trace'], 'instance_id': r['instance_id'],
                         'author_correct': ac, 'answer_correct': r['answer_correct']})
    matcher_trace['benchmark_correct_gaps'] = {'traces': len(gaps), 'of': matcher_trace['traces'], 'rows': gaps}

    # judge self-contradiction, E1 fixed definition
    contrad = 0
    checked = 0
    for (inst, model), d in judge.items():
        parsed = d.get('parsed') or {}
        if parsed.get('binary_call') != 'reached_but_unused':
            continue
        checked += 1
        sets = parsed.get('sufficient_support_sets') or []
        first = set(sets[0]) if sets else set()
        cards = [c for c in (parsed.get('carriers') or []) if c.get('checkpoint') == 'board']
        contradictory = any(c.get('fact_id') in first and c.get('fidelity') in ('absent', 'distorted') for c in cards)
        contrad += bool(contradictory)
    judge_quality = {'reached_but_unused_checked': checked, 'self_contradictions': contrad,
                     'rate': contrad / checked if checked else None,
                     'valid_outputs': sum(1 for d in judge.values() if d.get('valid')),
                     'judge_outputs_for_anchor': len(judge)}

    out = {
        'prereg': {'file': 'rebuttal/pilots/prereg/E1.md',
                   'sha256': sha('rebuttal/pilots/prereg/E1.md'),
                   'analysis': 'fact presence + fidelity on the 30-instance anchor; no pass/fail thresholds'},
        'inputs': {p.name: sha(p) for p in sorted(list(RET.glob('E1anchor_*.json')) + list(SEALED.glob('outputs/*.json')))},
        'design': {'anchor_instances': len(anc_ids), 'anchor_traces': len(trace_rows),
                   'weights': war, 'bootstrap_draws': DRAWS, 'seed': SEED,
                   'presence_definition': 'board carrier not absent',
                   'fidelity_categories': list(FID_CATS)},
        'alignment': dict(alignment),
        'author_author_fact': author_fact,
        'author_author_trace_binary': author_trace,
        'judge_trace_binary': judge_trace,
        'matcher_trace_binary': matcher_trace,
        'judge_quality': judge_quality,
        'blocked': {
            'judge_author_fact_level': 'no fact mapping or adjudicated labels; the judge writes its own fact ids/texts',
            'matcher_heldout': 'the matcher has run on the 90 anchor traces only; it has not run on the 240 held-out traces',
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    # raw rows for the generated table (T01): same rows and weights as the numbers above
    def raw(rows, ka, kb, label, col):
        return [{'row': label, 'col': col, 'cluster': r['instance_id'], 'stratum': r['stratum'],
                 'weight': r['weight'], 'a': r[ka], 'b': r[kb]} for r in rows]
    raw_rows = (raw(fact_pres, 'pa', 'pb', 'Author–author', 'presence')
                + raw(fact_fid, 'fa', 'fb', 'Author–author', 'fidelity')
                + raw(jp, 'judge', 'author', 'Judge–author (rebuttal’s reference judge)', 'trace binary')
                + raw(mmp, 'matcher', 'author', 'Matcher–author (frozen semantic-dev-v2)', 'trace binary'))
    (OUT / 'anchor_agreement_rows.jsonl').write_text(
        ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in raw_rows))
    (OUT / 'anchor_agreement.json').write_text(json.dumps(out, indent=2, default=str) + '\n')
    write_md(out)
    print(json.dumps({k: out[k] for k in ['alignment', 'author_author_fact', 'author_author_trace_binary',
                                          'judge_trace_binary', 'judge_quality']}, indent=1, default=str))


def f3(x):
    return 'n/a' if x is None else f'{x:.3f}'


def ci(d):
    return f"{f3(d['estimate'])} [{f3(d['lo'])}, {f3(d['hi'])}]" if d else 'n/a'


def write_md(out):
    a = out['author_author_fact']
    t = out['author_author_trace_binary']
    j = out['judge_trace_binary']
    m = out['matcher_trace_binary']
    q = out['judge_quality']
    pc = a['presence_counts']
    fc = a['fidelity_counts']
    L = ['# E1 anchor analysis', '',
         f"2026-11-09. Pre-registration `rebuttal/pilots/prereg/E1.md` (SHA-256 `{out['prereg']['sha256']}`). "
         "30-instance anchor, 90 traces, two authors per trace. Weighted; within-stratum instance-cluster "
         "bootstrap, 2,000 draws, seed 42, percentile 95% CI. No pass/fail threshold.", '',
         '## Numbers', '',
         '| Quantity | Estimate [95% CI] | n | Raw counts |', '|---|---|---:|---|',
         f"| Fact presence, author–author κ | {ci(a['presence_kappa'])} | {a['rows']} facts | "
         f"{pc.get('yes | yes',0)} yes/yes, {pc.get('no | no',0)} no/no; {a['excluded_uncertain']} uncertain excluded |",
         f"| Fact presence, weighted agreement | {ci(a['presence_agreement'])} | {a['rows']} facts | same rows |",
         f"| Fact fidelity, author–author κ (4 categories) | {ci(a['fidelity_kappa'])} | {a['rows']} facts | "
         f"{sum(v for k,v in fc.items() if k.split(' | ')[0]!=k.split(' | ')[1])} disagreements; {a['excluded_uncertain']} uncertain excluded |",
         f"| Fact fidelity, AC1 | {ci(a['fidelity_ac1'])} | {a['rows']} facts | fixed categories absent/faithful/partial/distorted |",
         f"| Fact fidelity, weighted agreement | {ci(a['fidelity_agreement'])} | {a['rows']} facts | "
         f"{sum(v for k,v in fc.items() if k.split(' | ')[0]!=k.split(' | ')[1])} disagreements |",
         f"| Trace binary, author–author κ | {ci(t['kappa'])} | {t['rows']} traces | "
         f"{t['excluded']} partial/uncertain traces excluded |",
         f"| Trace binary, partial as lost (sensitivity) κ | {ci(t['partial_as_lost']['kappa'])} | "
         f"{t['partial_as_lost']['rows']} traces | partial recoded lost |",
         f"| Judge–author trace binary, agreement | {ci(j['agreement'])} | {j['pairs']} author–trace pairs ({j['traces']} traces) | "
         f"{j['excluded']} excluded |",
         f"| Judge–author trace binary, κ | {ci(j['kappa'])} | {j['pairs']} pairs | "
         f"{j['counts'].get('lost | reached_but_unused',0)} judge lost / author reached_but_unused; "
         f"{j['counts'].get('reached_but_unused | lost',0)} judge reached_but_unused / author lost |",
         f"| Matcher–author trace binary, agreement | {ci(m['agreement'])} | {m['pairs']} author–trace pairs ({m['traces']} traces) | "
         f"{m['excluded']} excluded; {m['run_ok']}/{m['planned']} traces scored: {m['run_failed']} failed and unscored, "
         f"{len(m['unattempted_traces'])} never attempted |",
         f"| Matcher–author trace binary, κ | {ci(m['kappa'])} | {m['pairs']} pairs | "
         f"{m['counts'].get('lost | reached_but_unused',0)} matcher lost / author reached; "
         f"{m['counts'].get('reached_but_unused | lost',0)} matcher reached / author lost |",
         f"| Matcher–author, partial as lost (sensitivity) κ | {ci(m['partial_as_lost']['kappa'])} | "
         f"{m['partial_as_lost']['rows']} pairs | partial recoded lost on both sides |",
         f"| Matcher–author, present vs lost (sensitivity) κ | {f3(m['present_vs_lost']['unweighted_kappa'])} (unweighted) | "
         f"{m['present_vs_lost']['rows']} pairs | correct and reached_but_unused recoded reached |",
         f"| Matcher–author, bounds over the {m['bounds']['missing_traces']} failed traces | agreement "
         f"{f3(m['bounds']['agreement']['worst'])}–{f3(m['bounds']['agreement']['best'])}; κ "
         f"{f3(m['bounds']['kappa']['worst'])}–{f3(m['bounds']['kappa']['best'])} | {m['bounds']['scored_pairs']} scored + "
         f"{m['bounds']['missing_pairs']} missing pairs | best = missing pair takes the author label; worst = different category |",
         f"| Judge self-contradiction (E1 definition) | {q['self_contradictions']} / {q['reached_but_unused_checked']} | "
         f"{q['reached_but_unused_checked']} reached-but-unused calls | {q['valid_outputs']} / 90 judge outputs valid |", '',
         '## Data hygiene', '',
         'All 16 files in `rebuttal/annotation/returns/` parse. 252 rows: dev 40, anchor 180, calibration 20, '
         'E2 spot-check 12. Dev covers 20/20 pre-registered dev instances; calibration covers 5/5 pre-registered '
         'calibration instances; anchor covers 30/30 pre-registered anchor instances and 90/90 traces, with exactly '
         'two author labels on every anchor trace (A+B on 45 traces, C+D on 45). The two authors’ fact ids agree on '
         '90/90 anchor traces, which is what makes the fact-level pairing above possible. Empty `unit_ids` occur only '
         'with fidelity `absent`, which the guideline prescribes. The 80 held-out instances are author-labelled on the '
         'anchor only: 30 have author labels, and the other 50 have judge labels only, as pre-registered. Dev instances '
         'are disjoint from the 80.', '',
         '## Reading', '',
         f"The rebuttal’s reference judge (Gemini 3.6 Flash) is **stricter** than the authors on traces: in "
         f"{j['counts'].get('lost | reached_but_unused',0)} of {j['pairs']} author–trace pairs it calls a trace "
         f"lost that an author calls reached_but_unused, and in {j['counts'].get('reached_but_unused | lost',0)} "
         f"pairs the reverse. It also moves {j['counts'].get('reached_but_unused | correct',0)} author-correct "
         f"pairs to reached_but_unused and {j['counts'].get('correct | reached_but_unused',0)} the other way. "
         "The direction works against the method: judge labels under-credit reach relative to the authors.", '',
         '| Instrument | Direction on author labels | Pairs |', '|---|---|---:|',
         f"| Rebuttal’s reference judge (Gemini 3.6 Flash) | calls lost where the authors say reached: "
         f"{j['counts'].get('lost | reached_but_unused',0)}; calls reached where the authors say lost: "
         f"{j['counts'].get('reached_but_unused | lost',0)} | {j['pairs']} |",
         f"| Frozen matcher (`semantic-dev-v2`) | calls lost where the authors say reached: "
         f"{m['counts'].get('lost | reached_but_unused',0)}; calls reached where the authors say lost: "
         f"{m['counts'].get('reached_but_unused | lost',0)} | {m['pairs']} |", '',
         '_Footnote to the matcher rows: matcher frozen after anchor labels were collected but before it was run on '
         'them; no changes since dev._', '',
         f"**Missing matcher traces.** The first run scored 78 of {m['planned']} planned anchor traces and stopped "
         f"itself once more than 5 traces had failed; it never reached the last two instances of the fixed "
         f"manifest order, `II-13_n10` and `I-02_n5`. One authorised top-up then ran the frozen matcher on those "
         f"6 traces with one attempt per call and no setting changed: {m['topup']['ok']}/{m['topup']['attempted']} "
         f"succeeded ({m['topup']['calls']} calls, ${m['topup']['cost_usd']:.4f}), so {m['run_ok']} of "
         f"{m['planned']} traces are now scored. Six traces remain unscored: `III-24_n5` and `III-27_n5` (three "
         f"models each; `finish_reason: length`), which stay unscored with that reason. Their fact calls "
         f"generated far longer output than the rest (3,568–4,096 tokens against a median of 152), so the scored "
         f"traces are **not a random subset** of the anchor. The bounds row treats the {m['bounds']['missing_pairs']} "
         f"missing author–trace pairs as agreeing (best case) and as disagreeing (worst case).", '',
         f"**Weights.** Each trace keeps its locked design weight w_h = N_h/n_anchor,h from the anchor manifest, "
         f"unchanged by which traces ran. With the top-up, every stratum has at least one scored instance and the "
         f"present weight equals the full-anchor total ({m['present_weight_total']:.3f}), so no stratum is dropped "
         f"and no renormalisation factor is applied. `SB/partial` is still represented by a single scored instance "
         f"(`III-29_n5`; the other two are the failed traces), so that stratum adds no between-instance variance. "
         f"The CIs describe the {m['traces']} scored traces under this design.", '',
         '## Compared with the paper’s instrument', '',
         'The paper defines critical-fact coverage and the extraction/selection loss call without an LLM matcher. '
         'CritRec is the lexical rule in `app_main.tex:238–258` (`s(g,t)=max{J,N} > τ`, default τ=0; also '
         '`3-methodology.tex:58–59`), applied to gold supporting paragraphs/facts (`3-methodology.tex:45`). The '
         'reached/lost call is the checkpoint comparison in `3-methodology.tex:52` and `app_main.tex:759–761` '
         '(loss before extraction = extraction omission; later loss = selection omission; complete coverage with a '
         'non-perfect answer = candidate aggregation failure, `app_main.tex:283`). The paper has no “reached but '
         'unused” label; that category comes from this rebuttal’s labelling scheme, whose closest paper statement is '
         'the candidate-aggregation-failure flag.', '',
         'The paper’s only LLM judge is the distortion/alignment judge (`app_main.tex:269`, `app_distortion_se.tex:7`, '
         '`app_distortion_relay.tex:11`): Qwen-235B at temperature 0.0 (`app_main.tex:669`, `674`), JSON-only output '
         '(`app_main.tex:405–428`). The frozen matcher shares that judge model, temperature 0 and JSON output, and '
         'nothing else: its prompt (`src/audit/matcher_v2.py:6–25`, hash `3d97341d…`) fixes atomic facts from the '
         'gold supports and locates their carriers in the extraction pool and board, with role (sole/alternative/'
         'joint) and fidelity, then a trace-level call. The paper’s prompt classifies one aligned pair into five '
         'distortion labels and asks for neither carrier location nor reach. The two are not the same instrument.', '',
         'The matcher result speaks to the paper’s statements that lexical coverage measures overlap rather than '
         'semantic sufficiency (`app_main.tex:243–244`, `3-methodology.tex:97`, `app_main.tex:305`), and to the '
         'generalisation limit that a semantic matcher may disagree with the lexical one. It does not speak to any '
         'reported CritRec, OmissionRate, AggFail or distortion percentage, none of which is computed by this '
         'matcher, and it cannot validate per-stage attributions. The paper states no `max_tokens` or schema for its '
         'judge, so the matcher’s 4,096-token cap cannot be compared with it.', '',
         '## Blocked', '',
         f'- **Matcher on held-out traces:** the matcher has run on the anchor only ({m["run_ok"]} of {m["planned"]} '
         'traces scored); the 240 held-out traces have no matcher labels yet, so any held-out matcher–judge '
         'agreement remains unmeasured.',
         '- **Judge–author fact-level κ:** the judge writes its own fact ids and texts; no author fact mapping or '
         'adjudicated label set exists, so judge facts cannot be paired with author facts without inventing an alignment.', '',
         '## Go / fix / drop', '',
         '| Row | Verdict | Reason |', '|---|---|---|',
         '| E1 fact-level human–human κ (presence) | Go (descriptive) | Computed on 339 paired facts; no threshold is pre-registered. |',
         '| E1 fact-level human–human κ (fidelity) and AC1 | Go (descriptive) | Computed on the same rows; report AC1 beside κ. |',
         '| Judge as the 80-instance reference | Go, labelled as a judge | 90/90 outputs valid, 0/32 self-contradictions, judge–author trace κ reported above; fact-level judge agreement is not measured. |',
         f"| Matcher validated against author labels | Go on the anchor (descriptive) | Frozen `semantic-dev-v2`; "
         f"{m['run_ok']} of {m['planned']} anchor traces scored (one run plus a one-attempt top-up of 6 traces), "
         f"{m['run_failed']} failed and unscored with the reason recorded. Matcher–author trace agreement "
         f"{f3(m['agreement']['estimate'])} [{f3(m['agreement']['lo'])}, {f3(m['agreement']['hi'])}] and κ "
         f"{f3(m['kappa']['estimate'])} [{f3(m['kappa']['lo'])}, {f3(m['kappa']['hi'])}] on the scored traces; "
         f"bounds including the missing traces are in the table. Reported descriptively: no pass/fail rule is "
         f"adopted. Held-out accuracy still unmeasured. |",
         '| Judge–author fact-level agreement | Fix | No fact mapping/adjudicated set. |', '',
         'No numeric pass/fail threshold exists in the E1 pre-registration; the verdicts above are about what can be '
         'computed and claimed, not about whether a threshold was met.', '']
    (OUT / 'anchor_agreement.md').write_text('\n'.join(L))


if __name__ == '__main__':
    main()