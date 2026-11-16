"""E2-A option C, wave 2: build the judge input packet for the new MuSiQue bases.

Read-only over the six seed runs; no model call. For every correct k=1 score-ranked-relay trace in
the two new seeds (the wave-1 base rule: correct answer), reconstruct the trace package, set the
k=1 board and the raw aggregation answer text as in the wave-1 packet, drop the 10 reserved
instances and the 68 wave-1 (instance, family) bases, and write one JSONL row per trace. The row has
no answer fields: this is judge input, not an author packet.

    python -m scripts.build_e2a_wave2_packet
"""
import hashlib, json
from collections import Counter
from pathlib import Path

from src.audit.critical_fact_validation import build_trace_packages, get_transmitted_units, \
    reconstruct_states_and_scores, load_jsonl
from src.audit.pilot_common import blind_view, digest
from src.eval.data_loader import load_musique
from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer

OUT = Path('rebuttal/pilots/20261110_e2a_wave2')
RUNS = [('43', 'qwen235b'), ('43', 'gpt4omini'), ('43', 'gemma31b'),
        ('44', 'qwen235b'), ('44', 'gpt4omini'), ('44', 'gemma31b')]
WAVE1 = Path('rebuttal/pilots/20261108_review5/E2A_combined_manifest.json')
RESERVED = {'2hop__16267_25719', '2hop__24661_81961', '2hop__466700_214359', '2hop__532383_768138',
            '2hop__66708_573255', '2hop__809096_491515', '3hop1__131783_131926_13165',
            '3hop1__169494_42197_18397', '3hop1__273571_834494_33939', '3hop1__273571_834494_34053'}
OUT_PACKET = OUT / 'judge_input_traces.jsonl'
MODEL = {'qwen235b': 'qwen/qwen3-235b-a22b-2507', 'gpt4omini': 'openai/gpt-4o-mini',
         'gemma31b': 'google/gemma-4-31b-it'}
# Wave-1 manifest names the same three families qwen/gemma/gpt.
W1_FAMILY = {'qwen235b': 'qwen', 'gpt4omini': 'gpt', 'gemma31b': 'gemma'}
SEED_FILE = {s: OUT / f'instances_seed{s}.jsonl' for s in ('43', '44')}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    wave1 = json.loads(WAVE1.read_text())
    w1_bases = {(c['instance_id'], c['model_family']) for c in wave1['candidates']}
    w1_instances = {i for i, _ in w1_bases}
    instances = {r['id']: r for r in load_musique()}
    rows, stats = [], []
    seed_instances = {s: {json.loads(l)['id'] for l in p.read_text().splitlines()}
                      for s, p in SEED_FILE.items()}
    for seed, fam in RUNS:
        run = f'E2A_wave2_seed{seed}_{fam}'
        d = Path(f'rebuttal/results/batch1/E2A_wave2/seed{seed}_{fam}')
        results = json.loads((d / 'results.json').read_text())
        per = {r['id']: r for r in results['instance_results']['score_ranked_relay']}
        logged = [json.loads(l) for l in (d / 'api_responses.jsonl').read_text().splitlines()]
        agg = {}
        for r in logged:
            if r['phase'] == 'aggregation':
                assert r['instance_id'] not in agg, 'more than one aggregation call for an instance'
                agg[r['instance_id']] = r
        assert set(agg) == set(per), 'aggregation log and results.json disagree on instances'
        responses = load_jsonl(d / 'api_responses.jsonl')
        states, scores = reconstruct_states_and_scores(responses)
        packages = {t['instance_id']: t for t in build_trace_packages(
            dataset='musique', run_dir=str(d), protocol='score_ranked_relay', source_id=run)}
        assert set(packages) == set(per), 'trace packages and results.json disagree on instances'
        run_stats = {'seed': seed, 'family': fam, 'run': run, 'instances': len(per),
                     'correct': sum(bool(x['correct']) for x in per.values()),
                     'correct_agrees_with_answer_f1': 0, 'mismatch': [],
                     'reserved_in_sample': 0, 'wave1_pair_excluded': 0,
                     'wave1_instance_new_family_bases': 0, 'new_bases': 0}
        for iid, r in sorted(per.items()):
            assert iid not in RESERVED, 'reserved instance present in a seed sample'
            # Same rule as wave-1: correctness from the extracted aggregation answer against gold.
            f1 = answer_f1(extract_answer(agg[iid]['content']), instances[iid])
            if bool(r['correct']) == (f1 >= 1.0):
                run_stats['correct_agrees_with_answer_f1'] += 1
            else:
                run_stats['mismatch'].append(iid)
            if not r['correct']:
                continue
            if (iid, W1_FAMILY[fam]) in w1_bases:
                run_stats['wave1_pair_excluded'] += 1
                continue
            if iid in w1_instances:
                run_stats['wave1_instance_new_family_bases'] += 1
            t = packages[iid]
            units = get_transmitted_units(iid, 'score_ranked_relay', states, scores,
                                          len(t['source_contexts']), k=1)
            board = [{'unit_id': f'k1:a{agent}:u{j}', 'agent_id': agent, 'text': text}
                     for agent, texts in sorted(units.items()) for j, text in enumerate(texts)]
            t['checkpoints']['transmission'] = board
            t['checkpoints']['board'] = board
            t['answer_text'] = agg[iid]['content']
            rows.append({'task': 'E2-A base screening (wave 2, judge input)', 'item_id': digest([run, iid, 1]),
                         'seed': int(seed), 'model_family': fam, 'k': 1,
                         'candidate_agent_ids': [x['agent_id'] for x in t['source_contexts']],
                         'trace': blind_view(t),
                         'provenance': {'run': run, 'request_id': agg[iid]['request_id'],
                                        'content_sha256': digest(agg[iid]['content'])}})
            run_stats['new_bases'] += 1
        stats.append(run_stats)
    rows.sort(key=lambda r: digest([42, r['item_id']]))
    assert len({r['item_id'] for r in rows}) == len(rows), 'duplicate trace id'
    OUT_PACKET.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    corrections = [{'seed': row['seed'], 'family': row['model_family'],
                    'same_instance_wave1': row['trace']['instance_id']}
                   for row in rows if row['trace']['instance_id'] in w1_instances]
    overlap_seeds = sorted(seed_instances['43'] & seed_instances['44']
                           - RESERVED)
    doc = {
        'purpose': 'judge input for E2-A option C wave-2 screening (fake bases only, no injections)',
        'packet': str(OUT_PACKET), 'packet_sha256': sha(OUT_PACKET),
        'rows': len(rows), 'order_sha256': digest([[42, r['item_id']] for r in rows]),
        'base_rule': 'score-ranked relay k=1, extracted aggregation answer with answer_f1 >= 1',
        'exclusions': {'reserved_instances': sorted(RESERVED),
                       'wave1_bases_excluded': len(w1_bases),
                       'wave1_instances': len(w1_instances)},
        'per_run': stats,
        'new_bases_by_family': dict(Counter(r['model_family'] for r in rows)),
        'new_bases': len(rows),
        'new_bases_on_wave1_instances': corrections,
        'seed43_seed44_shared_instances': overlap_seeds,
        'instances_seed43': len(seed_instances['43']),
        'instances_seed44': len(seed_instances['44']),
        'note': 'Rows on a wave-1 instance are not independent clusters; counted in '
                'new_bases_on_wave1_instances. Repeated instances across the two seeds produce the '
                'same trace (score-ranked relay has no RNG); those pairs are not independent either.',
    }
    (OUT / 'packet_manifest.json').write_text(json.dumps(doc, indent=2) + '\n')
    print(json.dumps(doc, indent=1))


if __name__ == '__main__':
    main()