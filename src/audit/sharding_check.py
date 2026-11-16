"""Input-presence (sharding) check before an extraction-omission diagnosis.

Additive to `semantic_matcher.diagnose`, which is unchanged: a fact labelled
`extraction_omission` is re-attributed to `sharding_omission` when the frozen
presence rule finds it in none of its source agents' input shards.
Rule: `rebuttal/pilots/20261113_sharding_diagnosis/SHARDING_RULE.md`.
"""
from scripts.build_e4_manifest import spans
from src.audit.e4_fix_gates import STOP, recall
from src.eval.evaluate import normalize

PRESENT = 0.8
PARTIAL = 0.4


def content_recall(text, fact):
    ft = [t for t in normalize(fact) if t not in STOP]
    if not ft:
        return 1.0
    return recall(text, ' '.join(ft))


def evidence_sentences(context, question):
    q = ' '.join(normalize(question))
    out = []
    for s in spans(context):
        n = ' '.join(normalize(s))
        if (n.startswith('question ') or
                n.startswith('you hold the following evidence') or
                n == q or s.strip().startswith('[Document:')):
            continue
        out.append(s)
    return out


def shard_label(contexts, fact, question):
    """Frozen presence rule over one or more source shards."""
    best = 0.0
    for context in contexts:
        for s in evidence_sentences(context, question):
            best = max(best, content_recall(s, fact))
    if best >= PRESENT:
        return 'present', best
    if best >= PARTIAL:
        return 'partial', best
    return 'absent', best


def sharding_diagnosis(old, fact_labels):
    """Map the old label plus per-fact shard labels to the new stage label."""
    if old != 'extraction_omission':
        return old
    labels = set(fact_labels)
    if labels <= {'absent'}:
        return 'sharding_omission'
    if 'absent' in labels:
        return 'mixed_sharding_extraction'
    return 'extraction_omission'


def fact_status(facts, carriers):
    """Per-fact status and chosen support set, exactly as diagnose computes them."""
    status = {}
    for r in carriers['facts']:
        pool, board = r['extraction'], r['board']
        if not pool:
            label = 'extraction_omission'
        elif not board:
            label = 'selection_omission'
        elif any(c['fidelity'] == 'faithful' for c in board):
            label = 'present'
        elif any(c['fidelity'] == 'uncertain' for c in board):
            label = 'uncertain'
        elif any(c['fidelity'] == 'partial' for c in board):
            label = 'partial'
        else:
            label = 'distortion'
        status[r['fact_id']] = label
    chosen = min(facts['support_sets'],
                 key=lambda s: (sum(status[f] != 'present' for f in s),
                                tuple(sorted(s))))
    return status, chosen


def diagnose_with_sharding(facts, carriers, trace, correct=False):
    """Audit diagnosis with the input-presence check; old label kept beside it.

    `trace` supplies `question` and `source_contexts`. Returns
    `(new_label, detail)`; `detail['old']` is the unchanged diagnose label.
    """
    from src.audit.semantic_matcher import diagnose
    old = diagnose(facts, carriers, correct=correct)
    detail = {'old': old, 'facts': {}}
    if old != 'extraction_omission':
        return old, detail
    status, chosen = fact_status(facts, carriers)
    missing = [f for f in chosen if status[f] == 'extraction_omission']
    by_id = {x['fact_id']: x for x in facts['facts']}
    ctx = {c['context_id']: c['text'] for c in trace['source_contexts']}
    for fid in missing:
        want = {s.split(':')[-1] for s in by_id[fid]['source_ids']}
        texts = [v for k, v in ctx.items() if k.split(':')[-1] in want]
        label, best = shard_label(texts, by_id[fid]['text'], trace['question'])
        detail['facts'][fid] = {'label': label, 'best_recall': round(best, 3),
                                'shards': sorted(want)}
    new = sharding_diagnosis(old, {v['label']
                                   for v in detail['facts'].values()})
    return new, detail