"""Build the shard-presence call list for the over-flag fix, and check the stored labels reproduce ($0).

Old rule: `src.audit.sharding_check.shard_label` counts a fact present in a shard when token recall of some
evidence sentence reaches .8. New rule: a fact counts as present only if the passage states it (atom-level
presence label). This script lists one call per (case, fact) that the old rule had to check, and prints the
projection.
"""
import json
from collections import Counter
from pathlib import Path

import scripts.b5_attribution_2x2 as B
from src.audit.semantic_matcher import diagnose
from src.audit.sharding_check import fact_status, shard_label

ROOT = Path(__file__).resolve().parent.parent
PILOTS = ROOT / 'rebuttal/pilots'
OUT = PILOTS / '20261115_sharding_semantic'
GEM = PILOTS / '20261115_b5_attribution_2x2/calls.jsonl'
QWN = PILOTS / '20261115_b5_qwen_design_a/calls.jsonl'


def carriers(path, prefix):
    out = {}
    for l in Path(path).read_text().splitlines():
        if not l.strip():
            continue
        e = json.loads(l)
        if e.get('event') != 'result' or not e.get('success'):
            continue
        k = e['key']
        if not k.startswith(prefix) or '/carriers/attempt-' not in k:
            continue
        if k.rsplit('/attempt-', 1)[1] != '1':
            continue
        case = k[len(prefix):].split('/carriers/')[0]
        if case.startswith('qa/'):
            case = case[3:]
        try:
            out[case] = json.loads(e['content'])
        except Exception:
            pass
    return out


def main():
    cases = {c['key']: c for c in json.loads(B.CASES.read_text())}
    acc = B.accepted()
    pk = {m: B.packages(m) for m in {c['key'].split('/')[1] for c in cases.values()}}
    qfc = B.qwen_facts_carriers()
    gem = carriers(GEM, 'audita/')
    qwn = carriers(QWN, 'qa/')
    old_gem = {r['key']: r.get('stage') for r in json.loads(B.AUDIT_A_RESULTS.read_text())['items']}
    old_qwn = {r['key']: r.get('stage') for r in json.loads(
        (PILOTS / '20261115_b5_qwen_design_a/results.json').read_text())['items']}
    calls = {}
    mismatch = []
    for key, c in cases.items():
        model, inst = key.split('/')[1], key.split('/')[2]
        t = B.corrupted(c, acc) if c['population'] == 'injected' else pk[model][inst]
        facts = qfc[key]['facts']
        for name, car, old in (('gemini', gem.get(key), old_gem.get(key)),
                               ('qwen', qwn.get(key), old_qwn.get(key))):
            if not car:
                continue
            lab = diagnose(facts, car, correct=False)
            got = 'sharding' if lab in ('sharding_omission', 'mixed_sharding_extraction') else B.stage_of(lab)
            if old and got != old:
                mismatch.append((key, name, old, got))
            if lab != 'extraction_omission':
                continue
            status, chosen = fact_status(facts, car)
            missing = [f for f in chosen if status[f] == 'extraction_omission']
            by_id = {x['fact_id']: x for x in facts['facts']}
            ctx = {x['context_id']: x['text'] for x in t['source_contexts']}
            for fid in missing:
                want = {s.split(':')[-1] for s in by_id[fid]['source_ids']}
                texts = [v for k2, v in ctx.items() if k2.split(':')[-1] in want]
                label, best = shard_label(texts, by_id[fid]['text'], t['question'])
                cid = (key, fid)
                if cid not in calls:
                    calls[cid] = {'key': key, 'fact_id': fid, 'fact': by_id[fid]['text'],
                                  'question': t['question'], 'shards': texts,
                                  'agents': sorted(want), 'old_shard_label': label,
                                  'old_recall': round(best, 3), 'cells': []}
                calls[cid]['cells'].append(name)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = list(calls.values())
    (OUT / 'calls_to_make.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(json.dumps({'calls': len(rows), 'cases': len({r['key'] for r in rows}),
                      'by_old_label': dict(Counter(r['old_shard_label'] for r in rows)),
                      'cases_with_calls': len({r['key'] for r in rows}),
                      'reproduce_mismatch': mismatch[:10],
                      'mismatch_n': len(mismatch)}, indent=1))


if __name__ == '__main__':
    main()