"""$0 check of Fix C best-recall values against the rule's source-shard list.

Rule: rebuttal/pilots/20261113_sharding_diagnosis/SHARDING_RULE.md (source shards =
source_contexts whose context_id is listed in the fact's source_ids; presence =
frozen content rule, thresholds 0.8 / 0.4) and PRESENCE_RULE.md (Amendment 2).
Reads frozen packages and matcher records only. No model calls.

    .conda-env/bin/python scripts/f38_fixc_shard_check.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.audit_diagnosis_89 import packages, records  # noqa: E402
from scripts.build_e4_manifest import agent_of  # noqa: E402
from scripts.repair_presence_check import MANUAL, content_recall, evidence_sentences  # noqa: E402

OUT = ROOT / 'rebuttal/pilots/20261116_f38_repairs'
POP = OUT / 'populations.json'
RESULT = OUT / 'fixc_shard_check.json'


def shard_label(text, question, fact_text):
    best = max((content_recall(s, fact_text) for s in evidence_sentences(text, question)), default=0.0)
    lab = 'present' if best >= 0.8 else ('partial' if best >= 0.4 else 'absent')
    return lab, round(best, 3)


def combine(labels):
    if 'present' in labels:
        return 'present'
    if 'partial' in labels:
        return 'partial'
    return 'absent'


def main():
    pop = json.loads(POP.read_text())['C']
    recs = records()
    rows = []
    for c in pop:
        pk = packages(c['model'])[c['instance']]
        rec = recs[(c['model'], c['instance'])]
        fact = next(f for f in rec['facts']['facts'] if f['fact_id'] == c['fact_id'])
        ids = {agent_of(s) for s in fact['source_ids']}
        shards = [s for s in pk['source_contexts'] if str(s['agent_id']) in {str(i) for i in ids}]
        per = [(s['agent_id'],) + shard_label(s['text'], pk['question'], c['fact_text']) for s in shards]
        rule = combine([p[1] for p in per]) if per else 'no_shard'
        vals = [p[2] for p in per]
        rows.append({
            'key': c['key'], 'fact_id': c['fact_id'], 'model': c['model'], 'instance': c['instance'],
            'source_ids': fact['source_ids'], 'shards_checked': [str(p[0]) for p in per],
            'shard_best_content_recall': vals, 'shard_labels': [p[1] for p in per],
            'rule_label': rule,
            'manual_read': MANUAL[c['instance']][0] if c['instance'] in MANUAL else None,
            'final_label': MANUAL[c['instance']][0] if c['instance'] in MANUAL else rule,
            'group_v1': c['group'], 'best_owner_v1': c['best_owner'], 'best_other_v1': c['best_other'],
            'v1_max': round(max(c['best_owner'], c['best_other']), 3),
        })
    RESULT.write_text(json.dumps(rows, indent=1))
    print('content rule labels:', Counter(r['rule_label'] for r in rows))
    print('final labels (manual reads of the stage-2 cohort applied where the instance matches):', Counter(r['final_label'] for r in rows))
    mism = [r for r in rows if (r['rule_label'] == 'absent') != (r['v1_max'] < 0.4)]
    print('cases where absent/not-absent differs from v1 (0.4 on max):', len(mism))
    for r in rows:
        print(r['key'], r['fact_id'], r['shards_checked'], r['shard_best_content_recall'],
              r['rule_label'], '| v1', r['best_owner_v1'], r['best_other_v1'], r['group_v1'])


if __name__ == '__main__':
    main()
