"""Build the frozen point-level Silo-Bench extraction sample (no API calls).

Atomizes each source support into deterministic claim atoms (list elements,
dict entries, sentences) and draws 21 fresh traces, one per instance, from
instances not used by prompt v3 or v4.
"""
import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_sb_points'
V3 = ROOT / 'rebuttal/pilots/20261114_per_fact_extraction_sb'
V4 = ROOT / 'rebuttal/pilots/20261114_per_fact_extraction_sb_v2'
RULE = ROOT / 'rebuttal/pilots/prereg/Per-fact-presence-points-v1.md'
PROMPT = ROOT / 'rebuttal/pilots/prereg/per_fact_points_prompt_v1.json'
AMENDMENT = ROOT / 'rebuttal/pilots/prereg/Per-fact-presence-points-v1-amendment-1.md'
SEED = 47
RUNS = {('deepseekr1_32b', 5): 'run_deepseekr1_32b_n5',
        ('deepseekr1_32b', 10): 'run_deepseekr1_32b_n10',
        ('geminiflashlite', 5): 'run_geminiflashlite_n5',
        ('geminiflashlite', 10): 'run_geminiflashlite_n10'}


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def parse_literal(text):
    for f in (json.loads, ast.literal_eval):
        try:
            return f(text)
        except Exception:
            pass
    return None


def atomize(text):
    """Return (atoms, kind) without any model call."""
    v = parse_literal(text)
    if isinstance(v, list) and len(v) > 1:
        return [json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x for x in v], 'list'
    if isinstance(v, dict) and len(v) > 1:
        return [json.dumps({k: x}, ensure_ascii=False) for k, x in v.items()], 'dict'
    parts = [p.strip() for p in re.split(r'(?<=[.!?])\s+', text.strip()) if p.strip()]
    if len(parts) > 1:
        return parts, 'sentence'
    return [text.strip()], 'single'


def excluded():
    ex = set()
    for d in (V3, V4):
        ex |= {r['instance_id'] for r in json.loads((d / 'population.json').read_text())}
    return ex


def build():
    import sys
    sys.path.insert(0, str(ROOT))
    from src.audit.critical_fact_validation import build_trace_packages
    ex = excluded()
    by_instance = {}
    for (model, n), run in RUNS.items():
        for t in build_trace_packages(dataset='silobench', run_dir=f'results/{run}',
                                      protocol='score_ranked_relay', source_id=run,
                                      n_agents=n):
            if t['instance_id'] in ex:
                continue
            by_instance.setdefault(t['instance_id'], {})[model] = (run, n, t)
    rows = []
    for instance_id in sorted(by_instance):
        models = sorted(by_instance[instance_id])
        pick = min(models, key=lambda m: sha(f'{SEED}|{instance_id}|{m}'))
        run, n, t = by_instance[instance_id][pick]
        facts = []
        for i, s in enumerate(t['source_supports']):
            atoms, kind = atomize(s['text'])
            facts.append({'fact_id': f'f{i+1}', 'text': s['text'], 'kind': kind,
                          'atoms': [{'atom_id': f'f{i+1}.a{j+1}', 'text': a}
                                    for j, a in enumerate(atoms)]})
        rows.append({'key': f"pts/{pick}/{instance_id}", 'instance_id': instance_id,
                     'model': pick, 'run': run, 'n_agents': n, 'question': t['question'],
                     'facts': facts,
                     'entries': [{'unit_id': u['unit_id'], 'agent_id': u['agent_id'],
                                  'text': u['text']} for u in t['checkpoints']['extraction']]})
    rows.sort(key=lambda r: sha(f'{SEED}|points|{r["instance_id"]}'))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'population.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    atoms = sum(len(f['atoms']) for r in rows for f in r['facts'])
    facts = sum(len(r['facts']) for r in rows)
    manifest = {
        'recorded_before_any_call': True,
        'rule_sha256': file_sha(RULE),
        'prompt_sha256': file_sha(PROMPT),
        'amendment_sha256': file_sha(AMENDMENT),
        'seed': SEED, 'traces': len(rows),
        'instances': len({r['instance_id'] for r in rows}),
        'facts': facts, 'atoms': atoms,
        'excluded_instances': sorted(ex),
        'population_sha256': hashlib.sha256((OUT / 'population.json').read_bytes()).hexdigest(),
        'models': sorted({r['model'] for r in rows}),
        'checkpoint': 'extraction', 'protocol': 'score_ranked_relay',
        'calls': 2 * facts,
        'projection_usd': round(facts * 0.0072, 2),
        'reference_model': 'google/gemini-3.6-flash', 'labeller_model': 'anthropic/claude-haiku-5.5',
        'projection_note': ('155 facts x 2 models; amended reference Gemini 3.6 Flash at $0.006/call '
                            'and Haiku at $0.0012/call, both from measured smoke calls; estimate, cap $3.5'),
    }
    (OUT / 'build_manifest.json').write_text(json.dumps(manifest, indent=1))
    print(json.dumps(manifest, indent=1))


if __name__ == '__main__':
    build()