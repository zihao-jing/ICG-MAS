"""Build the full proxy-support population: all 89 known-stage cases (no calls).

Same rule, prompts and amendment as the 10-trace pilot; only the population is full.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.run_expansion_stage2 import packages

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_proxy_support_89'
PILOT = ROOT / 'rebuttal/pilots/20261115_proxy_support'
RULE = ROOT / 'rebuttal/pilots/prereg/Proxy-support-pilot-v1.md'
AMEND = ROOT / 'rebuttal/pilots/prereg/Proxy-support-pilot-v1-amendment-1.md'
FACTS_PROMPT = ROOT / 'rebuttal/pilots/prereg/proxy_facts_prompt_v1.json'
EQUIV_PROMPT = ROOT / 'rebuttal/pilots/prereg/proxy_support_equiv_prompt_v1.json'
AUDIT_PROMPT = ROOT / 'rebuttal/pilots/20261113_per_fact_labeller/per_fact_prompt_v3.json'
CASES = ROOT / 'rebuttal/pilots/20261113_attribution_comparison/cases_v2.json'
AUDIT = ROOT / 'rebuttal/pilots/20261113_audit_diagnosis_89/audit_results.json'


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build():
    cases = json.loads(CASES.read_text())
    audit = {x['key']: x for x in json.loads(AUDIT.read_text())['items']}
    chosen = [c for c in cases
              if audit.get(c['key'], {}).get('status') == 'ok']
    pk = {}
    rows, same = [], 0
    for c in chosen:
        model, inst = c['key'].split('/')[1], c['key'].split('/')[2]
        if model not in pk:
            pk[model] = packages(model)
        p = pk[model][inst]
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
    pilot = {r['key'] for r in json.loads((PILOT / 'population.json').read_text())}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'population.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    man = {
        'recorded_before_any_call': True,
        'population': 'all 89 cases_v2 cases with audit status ok (full run)',
        'rule_sha256': file_sha(RULE), 'amendment_sha256': file_sha(AMEND),
        'facts_prompt_sha256': file_sha(FACTS_PROMPT),
        'facts_prompt_system_sha256': sha(json.loads(FACTS_PROMPT.read_text())['system']),
        'equiv_prompt_sha256': file_sha(EQUIV_PROMPT),
        'equiv_prompt_system_sha256': sha(json.loads(EQUIV_PROMPT.read_text())['system']),
        'labeller_prompt_sha256': sha(json.loads(AUDIT_PROMPT.read_text())['system']),
        'cases_sha256': file_sha(CASES), 'audit_sha256': file_sha(AUDIT),
        'traces': len(rows), 'instances': len({r['instance_id'] for r in rows}),
        'by_model': dict(Counter(r['model'] for r in rows)),
        'by_population': dict(Counter(r['key'].split('/')[0] for r in rows)),
        'by_audit_stage': dict(Counter(r['audit_stage'] for r in rows)),
        'by_known_stage': dict(Counter(r['known_stage'] for r in rows)),
        'cohort_rows_matching_package': same,
        'pilot_keys_included': len(pilot & {r['key'] for r in rows}),
        'population_sha256': file_sha(OUT / 'population.json'),
        'facts_model': 'qwen/qwen3-235b-a22b-2507',
        'equiv_model': 'google/gemini-3.6-flash',
        'labeller_model': 'anthropic/claude-haiku-5.5',
        'cap_usd': 1.0,
        'cap_estimator': 'per-call output allowance = max completion tokens observed in the pilot '
                         '(Qwen 400, Gemini 1600, Haiku 1600); the hard stop still uses actual spend',
    }
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


if __name__ == '__main__':
    build()