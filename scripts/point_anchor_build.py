"""Build the aligned anchor sample for the point-level presence check (no API calls)."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.per_fact_points_build import atomize

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_anchor_points'
RULE = ROOT / 'rebuttal/pilots/prereg/Anchor-alignment-v1.md'
PROMPT = ROOT / 'rebuttal/pilots/prereg/per_fact_points_prompt_v1.json'
RETURNS = ROOT / 'rebuttal/annotation/returns'
SEED = 47


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rows_from(name):
    return json.loads((RETURNS / f'E1anchor_{name}_labelling-v1.0.json').read_text())


def build():
    pool = []
    dropped = 0
    for name in ('A', 'C'):
        for r in rows_from(name):
            t = r['trace']
            supports = {s['support_id']: s for s in t['source_supports']}
            board = t['checkpoints']['board']
            facts = json.loads(r['answers']['critical_facts_json'])
            carriers = json.loads(r['answers']['carriers_json'])
            for f in facts:
                src = f.get('source_ids') or []
                if len(src) != 1 or src[0] not in supports:
                    dropped += 1
                    continue
                atoms, kind = atomize(supports[src[0]]['text'])
                if not atoms:
                    dropped += 1
                    continue
                cs = [c for c in carriers
                      if c.get('fact_id') == f['fact_id'] and c.get('checkpoint') == 'board']
                author = any(c.get('fidelity') != 'absent' for c in cs)
                pool.append({
                    'trace_key': f"{name}/{t['instance_id']}/{f['fact_id']}",
                    'instance_id': t['instance_id'],
                    'question': t['question'],
                    'fact': {'fact_id': f['fact_id'], 'text': f['text'],
                             'atoms': [{'atom_id': f"{f['fact_id']}.a{i+1}", 'text': a}
                                       for i, a in enumerate(atoms)],
                             'kind': kind},
                    'entries': [{'unit_id': u['unit_id'], 'agent_id': u['agent_id'], 'text': u['text']}
                                for u in board],
                    'author_present': author,
                    'checkpoint': 'board',
                })
    absent = [r for r in pool if not r['author_present']]
    present = [r for r in pool if r['author_present']]
    for r in pool:
        r['order'] = sha(f"{SEED}|anchor-points|{r['trace_key']}")
    present.sort(key=lambda r: r['order'])
    sample = absent + present[:70]
    sample.sort(key=lambda r: r['order'])
    rows = []
    for r in sample:
        rows.append({'key': f"anc/{r['trace_key']}", 'instance_id': r['instance_id'],
                     'model': 'anchor', 'question': r['question'],
                     'facts': [r['fact']], 'entries': r['entries'],
                     'checkpoint': 'board', 'author_present': r['author_present']})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'population_aligned.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    manifest = {
        'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE),
        'prompt_sha256': file_sha(PROMPT), 'seed': SEED,
        'facts_available': len(pool), 'facts_dropped': dropped,
        'author_present_available': len(present), 'author_absent_available': len(absent),
        'sample': len(rows), 'sample_absent': len(absent),
        'sample_instances': len({r['instance_id'] for r in rows}),
        'sample_atoms': sum(len(r['facts'][0]['atoms']) for r in rows),
        'pool_sha256': hashlib.sha256((OUT / 'population_aligned.json').read_bytes()).hexdigest(),
        'labeller_model': 'anthropic/claude-haiku-5.5',
        'reference_model': 'google/gemini-3.6-flash', 'cap_usd': 1.5,
    }
    (OUT / 'build_manifest.json').write_text(json.dumps(manifest, indent=1))
    print(json.dumps(manifest, indent=1))


if __name__ == '__main__':
    build()