"""Build the matched anchor sample: evidence = the author's carrier units only (no API calls)."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_anchor_matched'
SRC = ROOT / 'rebuttal/pilots/20261115_anchor_points'
RULE = ROOT / 'rebuttal/pilots/prereg/Anchor-alignment-matched-v1.md'
PROMPT = ROOT / 'rebuttal/pilots/prereg/per_fact_points_prompt_v1.json'
RETURNS = ROOT / 'rebuttal/annotation/returns'


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def carriers(name):
    out = {}
    rows = json.loads((RETURNS / f'E1anchor_{name}_labelling-v1.0.json').read_text())
    for r in rows:
        t = r['trace']
        cf = json.loads(r['answers']['critical_facts_json'])
        car = json.loads(r['answers']['carriers_json'])
        for f in cf:
            cs = [c for c in car
                  if c.get('fact_id') == f['fact_id'] and c.get('checkpoint') == 'board']
            units = sorted({u for c in cs for u in (c.get('unit_ids') or [])})
            out[(t['instance_id'], f['fact_id'])] = units
    return out


def build():
    rows = json.loads((SRC / 'population_aligned.json').read_text())
    lookups = {'A': carriers('A'), 'C': carriers('C')}
    out = []
    empty = 0
    for r in rows:
        ann, inst = r['key'].split('/')[1], r['instance_id']
        fid = r['facts'][0]['fact_id']
        units = set(lookups[ann].get((inst, fid), []))
        entries = [e for e in r['entries'] if e['unit_id'] in units]
        if not entries:
            empty += 1
        rr = dict(r)
        rr['entries'] = entries
        rr['carrier_units'] = sorted(units)
        out.append(rr)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'population_matched.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
    man = {
        'recorded_before_any_call': True,
        'rule_sha256': file_sha(RULE), 'prompt_sha256': file_sha(PROMPT),
        'source_population_sha256': file_sha(SRC / 'population_aligned.json'),
        'population_sha256': hashlib.sha256((OUT / 'population_matched.json').read_bytes()).hexdigest(),
        'facts': len(out), 'facts_empty_evidence': empty,
        'author_present': sum(1 for r in out if r['author_present']),
        'author_absent': sum(1 for r in out if not r['author_present']),
        'instances': len({r['instance_id'] for r in out}),
        'atoms': sum(len(r['facts'][0]['atoms']) for r in out),
        'labeller_model': 'anthropic/claude-haiku-5.5',
        'reference_model': 'google/gemini-3.6-flash', 'cap_usd': 1.0,
    }
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


if __name__ == '__main__':
    build()