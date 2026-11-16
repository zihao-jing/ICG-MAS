"""Local R-ext unit-count reconstruction from frozen spans.

No model call and no author time. R-ext is one fresh extraction call on the target's shard (cap 3
units); the pilot appends every parsed unit (`scripts/pilot_e4.py`), and V-ext is truncated to that
count. The same extraction prompt on the same frozen shard is already recorded in the run's
extraction pool, so the target agent's pool units are the frozen span set. Reconstruct the
added-unit count as the number of those units and the added-token count from their text, then test
each frozen V-ext donor candidate for a same-volume pair (equal unit count, added tokens within
+/-10%).

    python -m scripts.reconstruct_rext_units
"""
import json
from collections import Counter
from pathlib import Path

from src.audit.base_tokenizers import added_token_count, volume_match
from src.audit.pilot_common import digest
from scripts.build_final_author_packet import packages

MANIFEST = Path('rebuttal/results/batch1/E4_manifest/manifest.json')
OUT = Path('rebuttal/results/batch1/E4_manifest/rext_unit_reconstruction.json')
BASE = {'qwen235b': 'qwen/qwen3-235b-a22b-2507', 'gpt4omini': 'openai/gpt-4o-mini',
        'gemma31b': 'google/gemma-4-31b-it'}


def main():
    man = json.loads(MANIFEST.read_text())
    cases = [c for c in man['cases']
             if c['group'] == 'extraction_omission' and c.get('matcher_status') == 'ok']
    ids = {c['instance'] for c in cases}
    pk = packages(ids)
    rows = []
    for c in cases:
        p = pk[(c['model'], c['instance'])]
        assert digest(p['checkpoints']['board']) == c['board_sha256'], f"board changed: {c['instance']}"
        a = c['target_agent']
        board_texts = {u['text'] for u in p['checkpoints']['board']}
        pool = [u for u in p['checkpoints']['extraction'] if u['agent_id'] == a]
        appended = pool[:3]
        model = BASE[c['model']]
        rep_tokens = added_token_count(model, appended)
        possible, matched = [], []
        for cand in c['control']['candidates']:
            k = str(len(appended))
            if len(cand['units']) < len(appended):
                continue
            ctl_tokens = cand['prefix_tokens'][k]
            ctl_units = cand['units'][:len(appended)]
            m = volume_match(model, appended, ctl_units)
            assert m['control_tokens'] == ctl_tokens, 'prefix token count disagrees with tokenizer'
            possible.append({'donor_agent': cand['agent'], 'donor_sha': cand['sha'],
                             'control_tokens': ctl_tokens, 'matched': m['matched']})
            if m['matched']:
                matched.append(cand['agent'])
        rows.append({'instance': c['instance'], 'model': c['model'], 'benchmark': c['benchmark'],
                     'target_agent': a, 'pool_units': len(pool),
                     'on_board': sum(u['text'] in board_texts for u in pool),
                     'added_units': len(appended), 'repair_tokens': rep_tokens,
                     'added_texts': [u['text'] for u in appended],
                     'donor_possible': possible, 'donor_matched': matched,
                     'matched': bool(matched)})
    by_bench = Counter(r['benchmark'] for r in rows)
    out = {
        'purpose': 'reconstruct the R-ext added-unit count from the frozen extraction spans; no call, no author',
        'source_manifest': str(MANIFEST),
        'source_manifest_sha256': __import__('hashlib').sha256(MANIFEST.read_bytes()).hexdigest(),
        'cases': len(rows),
        'benchmarks': dict(by_bench),
        'pool_units_distribution': dict(Counter(r['pool_units'] for r in rows)),
        'added_units_distribution': dict(Counter(r['added_units'] for r in rows)),
        'possible_pairs': sum(len(r['donor_possible']) for r in rows),
        'matched_pairs': sum(r['matched'] for r in rows),
        'matched_by_benchmark': dict(Counter(r['benchmark'] for r in rows if r['matched'])),
        'possible_by_benchmark': {b: sum(len(r['donor_possible']) for r in rows if r['benchmark'] == b)
                                  for b in by_bench},
        'cases_with_no_control_volume': [f"{r['instance']}/{r['model']}" for r in rows
                                         if not r['donor_possible']],
        'rows': rows,
        'caveat': 'The added-unit count is reconstructed from the frozen extraction pool of the target '
                  'agent (same prompt, same shard, cap 3), treating it as the unit count a fresh R-ext '
                  'call returns; the live call fixes the actual count at intervention. Text content of '
                  'the fresh call is not assumed.',
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps({k: out[k] for k in ('cases', 'benchmarks', 'pool_units_distribution',
                                          'added_units_distribution', 'possible_pairs', 'matched_pairs',
                                          'matched_by_benchmark', 'possible_by_benchmark',
                                          'cases_with_no_control_volume')}, indent=1))


if __name__ == '__main__':
    main()