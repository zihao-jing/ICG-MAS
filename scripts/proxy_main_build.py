"""Build the 608-trace main-table proxy population (no calls).

Same frozen rule and prompts as the 89-case run. Source: the 608 trace packages in
`rebuttal/pilots/20261112_rescore/cases.jsonl`. Summary-exchange traces carry no extraction
checkpoint, so they enter the equivalence check but not the audit-stage diagnosis.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_proxy_support_main'
RULE = ROOT / 'rebuttal/pilots/prereg/Proxy-support-pilot-v1.md'
AMEND = ROOT / 'rebuttal/pilots/prereg/Proxy-support-pilot-v1-amendment-1.md'
FACTS_PROMPT = ROOT / 'rebuttal/pilots/prereg/proxy_facts_prompt_v1.json'
EQUIV_PROMPT = ROOT / 'rebuttal/pilots/prereg/proxy_support_equiv_prompt_v1.json'
AUDIT_PROMPT = ROOT / 'rebuttal/pilots/20261113_per_fact_labeller/per_fact_prompt_v3.json'
CASES = ROOT / 'rebuttal/pilots/20261112_rescore/cases.jsonl'


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build():
    rows = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]
    out = []
    for r in rows:
        t = r['trace']
        cp = t['checkpoints']
        docs = []
        for x in t['source_contexts']:
            text = x['text'].split('You hold the following evidence:', 1)[-1].strip()
            docs.append({'unit_id': x['context_id'], 'text': text})
        sup = []
        for s in t['source_supports']:
            title = s.get('title') or ''
            sup.append({'unit_id': s['support_id'],
                        'text': (title + '. ' if title else '') + s['text']})
        out.append({
            'key': r['key'], 'model': r['model'], 'benchmark': r['benchmark'],
            'protocol': r['protocol'], 'instance_id': r['instance_id'],
            'question': t['question'], 'documents': docs, 'gold_supports': sup,
            'checkpoints': {'extraction': cp.get('extraction') or [],
                            'board': cp.get('board') or []},
            'has_extraction': bool(cp.get('extraction')),
        })
    assert len(out) == 608
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'population.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
    man = {
        'recorded_before_any_call': True,
        'rule_sha256': file_sha(RULE), 'amendment_sha256': file_sha(AMEND),
        'facts_prompt_sha256': file_sha(FACTS_PROMPT),
        'facts_prompt_system_sha256': sha(json.loads(FACTS_PROMPT.read_text())['system']),
        'equiv_prompt_sha256': file_sha(EQUIV_PROMPT),
        'equiv_prompt_system_sha256': sha(json.loads(EQUIV_PROMPT.read_text())['system']),
        'labeller_prompt_sha256': sha(json.loads(AUDIT_PROMPT.read_text())['system']),
        'cases_sha256': file_sha(CASES),
        'traces': len(out),
        'by_benchmark_protocol': {'|'.join(k): v for k, v in
                                  Counter((r['benchmark'], r['protocol']) for r in out).items()},
        'with_extraction': sum(1 for r in out if r['has_extraction']),
        'without_extraction': sum(1 for r in out if not r['has_extraction']),
        'population_sha256': file_sha(OUT / 'population.json'),
        'facts_model': 'qwen/qwen3-235b-a22b-2507',
        'equiv_model': 'google/gemini-3.6-flash',
        'labeller_model': 'anthropic/claude-haiku-5.5',
        'cap_usd': 3.5,
        'cap_estimator': 'per-call output allowance from the 89-case run (Qwen 400, Gemini 1600, '
                         'Haiku 1600); hard stop on actual spend',
        'audit_scope': "relay protocols only; summary-exchange traces have no extraction checkpoint "
                       "in the frozen package",
    }
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


if __name__ == '__main__':
    build()