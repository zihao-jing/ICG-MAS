"""Build the proxy-support pilot population (no API calls).

Rule `rebuttal/pilots/prereg/Proxy-support-pilot-v1.md`, frozen before any call.
10 MuSiQue cases stratified by the gold-based audit stage.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.run_expansion_stage2 import packages

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_proxy_support'
RULE = ROOT / 'rebuttal/pilots/prereg/Proxy-support-pilot-v1.md'
FACTS_PROMPT = ROOT / 'rebuttal/pilots/prereg/proxy_facts_prompt_v1.json'
EQUIV_PROMPT = ROOT / 'rebuttal/pilots/prereg/proxy_support_equiv_prompt_v1.json'
CASES = ROOT / 'rebuttal/pilots/20261113_attribution_comparison/cases_v2.json'
AUDIT = ROOT / 'rebuttal/pilots/20261113_audit_diagnosis_89/audit_results.json'
SEED = 47
TAKE = {'extraction': 4, 'transmission': 4, 'sharding': 1, 'aggregation': 1}
MAP = {
    'extraction_omission': 'extraction',
    'sharding_omission': 'sharding',
    'mixed_sharding_extraction': 'sharding',
    'selection_omission': 'transmission',
    'partial': 'transmission',
    'distortion': 'transmission',
    'candidate_aggregation': 'aggregation',
}


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def select():
    cases = json.loads(CASES.read_text())
    audit = {x['key']: x for x in json.loads(AUDIT.read_text())['items']}
    by = {}
    for c in cases:
        a = audit.get(c['key'])
        if not a or a.get('status') != 'ok':
            continue
        by.setdefault(MAP[a['audit_label']], []).append(c)
    chosen = []
    for stage, n in TAKE.items():
        pool = sorted(by.get(stage, []), key=lambda c: sha(f'{SEED}|proxy|{c["key"]}'))
        chosen += pool[:n]
    return chosen, audit


def build():
    chosen, audit = select()
    pk = {}
    rows, same = [], 0
    for c in chosen:
        model = c['key'].split('/')[1]
        inst = c['key'].split('/')[2]
        if model not in pk:
            pk[model] = packages(model)
        p = pk[model][inst]
        # cohort rows must reproduce the frozen package exactly
        full = all([(u['unit_id'], u['text']) for u in c[cp]] ==
                   [(u['unit_id'], u['text']) for u in p['checkpoints'][cp]]
                   for cp in ('extraction', 'transmission', 'board'))
        same += bool(full)
        a = audit[c['key']]
        rows.append({
            'key': c['key'], 'model': model, 'instance_id': inst,
            'known_stage': c['known_stage'],
            'audit_label': a['audit_label'], 'audit_stage': a['audit_stage'],
            'question': c['question'],
            'documents': [{'unit_id': x['context_id'],
                           'text': x['text'].split('You hold the following evidence:', 1)[-1].strip()}
                          for x in p['source_contexts']],
            'gold_supports': [{'unit_id': s['support_id'],
                               'text': (s.get('title') + '. ' if s.get('title') else '') + s['text']}
                              for s in p['source_supports']],
            'checkpoints': {'extraction': c['extraction'], 'board': c['board']},
        })
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'population.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    man = {
        'recorded_before_any_call': True,
        'rule_sha256': file_sha(RULE),
        'facts_prompt_sha256': file_sha(FACTS_PROMPT),
        'facts_prompt_system_sha256': sha(json.loads(FACTS_PROMPT.read_text())['system']),
        'equiv_prompt_sha256': file_sha(EQUIV_PROMPT),
        'equiv_prompt_system_sha256': sha(json.loads(EQUIV_PROMPT.read_text())['system']),
        'labeller_prompt_sha256': sha(json.loads(
            (ROOT / 'rebuttal/pilots/20261113_per_fact_labeller/per_fact_prompt_v3.json')
            .read_text())['system']),
        'cases_sha256': file_sha(CASES), 'audit_sha256': file_sha(AUDIT),
        'seed': SEED, 'take': TAKE,
        'traces': len(rows), 'instances': len({r['instance_id'] for r in rows}),
        'by_model': dict(Counter(r['model'] for r in rows)),
        'by_audit_stage': dict(Counter(r['audit_stage'] for r in rows)),
        'by_known_stage': dict(Counter(r['known_stage'] for r in rows)),
        'cohort_rows_matching_package': same,
        'population_sha256': file_sha(OUT / 'population.json'),
        'selection': [r['key'] for r in rows],
        'facts_model': 'qwen/qwen3-235b-a22b-2507',
        'equiv_model': 'google/gemini-3.6-flash',
        'labeller_model': 'anthropic/claude-haiku-5.5',
        'cap_usd': 1.0,
    }
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


if __name__ == '__main__':
    build()