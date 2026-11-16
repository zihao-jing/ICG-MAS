"""Zero-cost presence check for the Stage 2 clean missing-fact cohort.

Rule: `rebuttal/pilots/20261112_missing_fact_repair/PRESENCE_RULE.md`, frozen
before this script ran. No model calls; reads frozen text only.

    ./run.sh python -m scripts.repair_presence_check
"""
import json
from collections import Counter
from pathlib import Path

from scripts.build_e4_manifest import agent_of, order, spans, target_for
from scripts.run_expansion_stage2 import (
    MATCHER_DIR, MODELS, candidate_rows, packages,
)
from src.audit.e4_fix_gates import STOP, recall
from src.eval.evaluate import normalize

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261112_missing_fact_repair'
PRESENCE = OUT / 'presence.json'
REPORT = OUT / 'presence_check.md'
MODEL_ORDER = ('gemma31b', 'gpt4omini', 'qwen235b')
THRESHOLD = 0.8

# Manual adjudication, allowed by PRESENCE_RULE.md before any paid call.
# Each entry: instance_id -> (final label, reason). Unlisted cases keep the
# content rule's label.
MANUAL = {
    '2hop__304852_758385': ('absent', 'only sentence places Emmaville in Hubbard County; Park Rapids appears as a nearby town, not as being in the county'),
    '3hop1__454441_55349_651302': ('absent', 'sentence is about Dian Bachar born in Denver; Trey Parker appears as a friend/star, birthplace not stated'),
    '2hop__50068_494136': ('absent', 'Flesh and Bone cast sentence lists both actors; no marriage statement'),
    '4hop1__37608_32392_823060_610794': ('absent', 'Forest Acres in Richland County / Columbia MSA; no border statement'),
    '2hop__342746_679190': ("absent", "Adam's Rib screenplay credit; 'married' refers to the film's characters, not Gordon and Kanin"),
    '2hop__46213_494136': ('absent', 'same cast sentence as 50068; no marriage statement'),
    '2hop__71294_494136': ('absent', 'same cast sentence; no spouse statement'),
    '2hop__47808_198548': ('absent', 'Murder in Texas cast sentence; no spouse statement'),
    '2hop__323534_810083': ('partial', 'sentence gives birth date and "from Scranton"; birthplace not explicitly stated'),
    '4hop1__473563_309800_355213_203322': ('partial', '"near the Cabarrus County line" implies adjacency; no border statement'),
    '2hop__504464_708278': ('present', '"one of the founders of Morgan Stanley in 1935" states the co-founding'),
    '2hop__123148_5385': ('present', 'employer table lists University of Oklahoma (11,900)'),
    '2hop__619265_45326': ('present', 'season table row "5 12" gives season 5 with 12 episodes'),
    '2hop__94507_654855': ('present', '"candidate of the Socialist Party of America" states party membership'),
    '3hop1__389761_567566_84283': ('present', 'infobox parent company Warner Music Group for Warner Bros. Records'),
    '2hop__435184_84856': ('present', 'season table row 15 starts January 20, 2017'),
    '2hop__734582_71302': ('present', '"Vito Corleone (De Niro)" states De Niro in the role'),
    '3hop1__637555_339990_15538': ('absent', 'sentence is about Oregon; New York not mentioned'),
    '2hop__128342_375952': ('absent', 'only a radio station licensed to Los Alamos; no county relation'),
    '2hop__64537_482364': ('absent', 'sentence says Pelias intended to kill Aeson; father-of-Jason not stated'),
    '4hop1__58323_375563_161848_44231': ('absent', 'sentence mentions New Zealand and Portugal; Australia not mentioned'),
    '3hop1__702699_792411_51423': ('absent', 'sentence places Gavin Bradley in Toronto; Jane Siberry birthplace not stated'),
    '2hop__55032_786853': ('absent', 'cast sentence lists both actors; no spouse statement'),
    '4hop1__28352_53706_795904_580996': ('absent', 'school located in Rio Linda, Sacramento; no border statement'),
}


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
        if (n.startswith('question ') or n.startswith('you hold the following evidence')
                or n == q or s.strip().startswith('[Document:')):
            continue
        out.append(s)
    return out


def check(rec, package, fact_id, fact_text, question):
    board_by_id = {u['unit_id']: u for u in package['checkpoints']['board']}
    _, target, _, _ = target_for('extraction_omission', package['instance_id'],
                                 rec['facts'], rec['carriers'], board_by_id)
    if target is None:
        return {'target_agent': None, 'label': 'no_target'}
    context = next(s['text'] for s in package['source_contexts']
                   if s['agent_id'] == target)
    sents = evidence_sentences(context, question)
    scored = [(recall(s, fact_text), content_recall(s, fact_text), i, s)
              for i, s in enumerate(sents)]
    supporting = [x for x in scored if x[0] >= THRESHOLD and x[1] >= THRESHOLD]
    best_full = max(scored, key=lambda x: (x[0], -x[2]), default=(0.0, 0.0, -1, ''))
    if supporting:
        label_full = 'present'
    elif best_full[0] > 0:
        label_full = 'partial'
    else:
        label_full = 'absent'
    best = max(scored, key=lambda x: (x[1], x[0], -x[2]), default=(0.0, 0.0, -1, ''))
    label = 'present' if best[1] >= THRESHOLD else ('partial' if best[1] >= 0.4 else 'absent')
    source_ids = next(f['source_ids'] for f in rec['facts']['facts']
                      if f['fact_id'] == fact_id)
    support_agents = {agent_of(sid) for sid in source_ids}
    support_text = next((s['text'] for s in package['source_supports']
                         if s['agent_id'] in support_agents), '')
    ws = lambda t: ' '.join(t.split())
    in_context = bool(support_text) and ws(support_text) in ws(context)
    return {'target_agent': target, 'label': label, 'label_full': label_full,
            'rmax': round(best[0], 3), 'content_recall': round(best[1], 3),
            'best_sentence': best[3], 'support_in_context': in_context,
            'source_ids': source_ids}


def main():
    man, rows = candidate_rows()
    clean = [r for r in rows
             if r.get('diagnosis') == 'extraction_omission' and r.get('pass')]
    pk = {m: packages(m) for m in MODELS}
    records = {}
    for p in MATCHER_DIR.glob('*.json'):
        rec = json.loads(p.read_text())
        records[(rec['instance_id'], rec['model'])] = rec
    out = []
    for r in clean:
        rec = records[(r['instance_id'], r['model'])]
        package = pk[r['model']][r['instance_id']]
        row = {'instance_id': r['instance_id'], 'model': r['model'],
               'question': r['question'], 'gold': str(r['gold']),
               'fact_id': r['candidate_fact_id'], 'fact': r['candidate_fact']}
        row.update(check(rec, package, r['candidate_fact_id'],
                         r['candidate_fact'], r['question']))
        out.append(row)

    by_inst = {}
    for r in out:
        by_inst.setdefault(r['instance_id'], []).append(r)
    rank = {m: i for i, m in enumerate(MODEL_ORDER)}
    instances = []
    for inst, rs in by_inst.items():
        chosen = sorted(rs, key=lambda r: (rank[r['model']], r['model']))[0]
        labels = {r['label'] for r in rs}
        labels_full = {r['label_full'] for r in rs}
        final, reason = MANUAL.get(inst, (chosen['label'], ''))
        instances.append({'instance_id': inst, 'model': chosen['model'],
                          'label': final, 'label_rule': chosen['label'],
                          'label_full': chosen['label_full'],
                          'manual': inst in MANUAL, 'manual_reason': reason,
                          'labels_all': sorted(labels),
                          'labels_full_all': sorted(labels_full),
                          'agree': len(labels) == 1 and len(labels_full) == 1,
                          'fact': chosen['fact'], 'target_agent': chosen['target_agent'],
                          'rmax': chosen['rmax'], 'content_recall': chosen['content_recall'],
                          'best_sentence': chosen['best_sentence'],
                          'support_in_context': chosen['support_in_context']})
    for r in out:
        r['label_final'] = MANUAL.get(r['instance_id'], (r['label'], ''))[0]

    tc = Counter(r['label_final'] for r in out)
    ic = Counter(i['label'] for i in instances)
    tcf = Counter(r['label_full'] for r in out)
    icf = Counter(i['label_full'] for i in instances)
    tcr = Counter(i['label_rule'] for i in instances)
    trc = Counter(r['label'] for r in out)
    disagree = [i for i in instances if not i['agree']]
    PRESENCE.write_text(json.dumps({'traces': out, 'instances': instances,
                                    'trace_counts': dict(tc), 'instance_counts': dict(ic),
                                    'instance_counts_rule': dict(tcr),
                                    'trace_counts_full': dict(tcf),
                                    'instance_counts_full': dict(icf)},
                                   indent=1, ensure_ascii=False))

    lines = ['# Delivery check on the Stage 2 clean cohort (zero cost)\n',
             f"Rule: `{OUT / 'PRESENCE_RULE.md'}` (frozen before this check; "
             f"Amendments 1 and 2 were written before any paid call). "
             f"Cohort: {len(out)} clean extraction-omission traces over "
             f"{len(instances)} unique instances. No model calls.\n",
             '## Split\n',
             '| rule | level | present | partial | absent | total |',
             '| --- | --- | ---: | ---: | ---: | ---: |',
             f"| content rule before manual read | traces | {trc.get('present',0)} | "
             f"{trc.get('partial',0)} | {trc.get('absent',0)} | {len(out)} |",
             f"| content rule before manual read | instances | {tcr.get('present',0)} | "
             f"{tcr.get('partial',0)} | {tcr.get('absent',0)} | {len(instances)} |",
             f"| **final (manual read)** | traces | {tc.get('present',0)} | {tc.get('partial',0)} | "
             f"{tc.get('absent',0)} | {len(out)} |",
             f"| **final (manual read)** | instances | {ic.get('present',0)} | {ic.get('partial',0)} | "
             f"{ic.get('absent',0)} | {len(instances)} |",
             f"| full-token rule (Amendment 1) | instances | {icf.get('present',0)} | "
             f"{icf.get('partial',0)} | {icf.get('absent',0)} | {len(instances)} |\n",
             f"Traces per instance where labels disagree across traces: {len(disagree)}.\n",
             '## Manual read\n',
             'The content rule counts co-location, not entailment: two names in a cast '
             'sentence reach 0.8 without the fact being stated. Every case was read against '
             'its best sentence before any paid call; each change and its reason is listed '
             'here and stored with the case in `presence.json`.\n',
             '| instance | rule label | final label | reason |',
             '| --- | --- | --- | --- |']
    for i in instances:
        if i['manual']:
            lines.append(f"| {i['instance_id']} | {i['label_rule']} | {i['label']} | "
                         f"{i['manual_reason']} |")
    lines += ['', '## All cases, with the best context sentence (audit)\n']
    for i in instances:
        lines += [f"### {i['instance_id']} / {i['model']} — {i['label']}"
                  f" (content rule: {i['label_rule']}; full-token rule: {i['label_full']})",
                  f"Fact: {i['fact']}",
                  f"Target agent: {i['target_agent']}; content recall "
                  f"{i['content_recall']:.3f}, full recall {i['rmax']:.3f}; "
                  f"support paragraph in context: {i['support_in_context']}",
                  f"Best sentence: {i['best_sentence']}\n"]
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'traces': len(out), 'instances': len(instances),
                      'trace_counts_final': dict(tc), 'instance_counts_final': dict(ic),
                      'instance_counts_content_rule': dict(tcr),
                      'instance_counts_full': dict(icf),
                      'manual_changes': len(MANUAL),
                      'disagree': len(disagree)}, indent=1))


if __name__ == '__main__':
    main()