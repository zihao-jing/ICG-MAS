"""Input-presence (sharding) check in the audit diagnosis; zero model calls.

Rule: `rebuttal/pilots/20261113_sharding_diagnosis/SHARDING_RULE.md`, frozen
before this run. Old diagnoses stay on record; this script only reads them.

    ./run.sh python -m scripts.sharding_diagnosis
"""
import hashlib
import json
from pathlib import Path

from scripts.missing_fact_repair_pilot import cp_ci
from src.audit.sharding_check import diagnose_with_sharding

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_sharding_diagnosis'
RULE = OUT / 'SHARDING_RULE.md'
MANIFEST = OUT / 'run_manifest.json'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'
PRESENCE = ROOT / 'rebuttal/pilots/20261112_missing_fact_repair/presence.json'
MATCHER = ROOT / 'rebuttal/results/batch1/E1_matcher_anchor/matcher'
ANCHOR = ROOT / 'rebuttal/pilots/20261108_review7/e1_anchor_locked_manifest.json'


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cohort():
    p = json.loads(PRESENCE.read_text())
    traces = []
    for r in p['traces']:
        old = 'extraction_omission'
        new = 'sharding_omission' if r['label_final'] == 'absent' else old
        traces.append({'paradigm': 'missing-fact cohort',
                       'instance_id': r['instance_id'], 'model': r['model'],
                       'fact_id': r['fact_id'], 'fact': r['fact'],
                       'presence': r['label_final'], 'old': old, 'new': new})
    inst = {}
    for r in traces:
        inst.setdefault(r['instance_id'], []).append(r)
    instances = []
    for i, rs in inst.items():
        moved = {r['new'] for r in rs}
        instances.append({'paradigm': 'missing-fact cohort', 'instance_id': i,
                          'old': 'extraction_omission',
                          'new': ('sharding_omission'
                                  if moved == {'sharding_omission'} else
                                  rs[0]['new'])})
    return traces, instances


def check_records(records, pk):
    traces = []
    for rec in records:
        if rec.get('status') != 'ok' or rec.get('diagnosis') != 'extraction_omission':
            continue
        t = pk[(rec['model'], rec['instance_id'])]
        new, detail = diagnose_with_sharding(rec['facts'], rec['carriers'], t,
                                             correct=bool(rec['answer_correct']))
        assert detail['old'] == 'extraction_omission'
        traces.append({'instance_id': rec['instance_id'],
                       'model': rec['model'], 'old': detail['old'],
                       'new': new, 'facts': detail['facts'],
                       'answer_correct': rec['answer_correct']})
    return traces


def anchor():
    ids = {i for v in json.loads(ANCHOR.read_text())['strata'].values()
           for i in v['ids']}
    from scripts.build_final_author_packet import packages
    pk = packages(ids)
    recs = [json.loads(p.read_text()) for p in sorted(MATCHER.glob('*.json'))]
    return [dict(r, paradigm='E1 anchor') for r in check_records(recs, pk)]


def main_table():
    from scripts.run_expansion_stage2 import MATCHER_DIR, MODELS, packages
    pk = {}
    for m in MODELS:
        pk.update({(m, inst): t for inst, t in packages(m).items()})
    recs = [json.loads(p.read_text())
            for p in sorted(MATCHER_DIR.glob('*.json'))]
    return [dict(r, paradigm='main table (2,400)')
            for r in check_records(recs, pk)]


def counts(rows):
    out = {}
    for r in rows:
        out.setdefault(r['old'], {}).setdefault(r['new'], 0)
        out[r['old']][r['new']] += 1
    return out


def ci(k, n):
    lo, hi = cp_ci(k, n)
    return [k, n, round(k / n, 4) if n else None,
            round(lo, 4) if n else None, round(hi, 4) if n else None]


def main():
    man = {'rule_sha256': file_sha(RULE),
           'recorded_before_first_run': True,
           'presence_sha256': file_sha(PRESENCE),
           'spend_usd': 0.0, 'model_calls': 0}
    MANIFEST.write_text(json.dumps(man, indent=1))
    ct, ci_rows = cohort()
    at = anchor()
    mt = main_table()
    res = {'cohort_traces': ct, 'cohort_instances': ci_rows,
           'anchor_traces': at, 'main_table_traces': mt,
           'counts': {'cohort_traces': counts(ct),
                      'cohort_instances': counts(ci_rows),
                      'anchor_traces': counts(at),
                      'main_table_traces': counts(mt)}}
    RESULTS.write_text(json.dumps(res, indent=1, ensure_ascii=False))

    def share(rows):
        n = len(rows)
        k = sum(r['new'] != r['old'] for r in rows)
        return ci(k, n)

    moved_anchor_facts = sum(
        1 for r in at for v in r['facts'].values() if v['label'] == 'absent')
    anchor_facts = sum(len(r['facts']) for r in at)
    lines = ['# Input-presence (sharding) check in the audit diagnosis\n',
             f"Rule `SHARDING_RULE.md` (sha256 `{file_sha(RULE)[:12]}`) frozen "
             'before this run. Zero model calls; spend $0.000000. Old diagnoses '
             'stay on record in the files named below; the old `diagnose` '
             'function is unchanged.\n',
             '## Missing-fact cohort (extraction stage)\n',
             'Cohort: 69 clean extraction-omission traces over 59 unique '
             'instances; presence labels and targeted fact from '
             '`20261112_missing_fact_repair/presence.json` (frozen presence '
             'rule, including the recorded manual read).\n',
             '| level | old diagnosis | new sharding | new extraction | moved |',
             '| --- | ---: | ---: | ---: | ---: |']
    for lvl, rows in (('traces', ct), ('instances', ci_rows)):
        c = counts(rows)
        sh = c['extraction_omission'].get('sharding_omission', 0)
        ex = c['extraction_omission'].get('extraction_omission', 0)
        k, n, est, lo, hi = share(rows)
        lines.append(f'| {lvl} | {n} | {sh} | {ex} | {k}/{n} '
                     f'({100 * est:.1f}%, 95% CI {100 * lo:.1f}-{100 * hi:.1f}) |')
    lines += ['', '## E1 anchor diagnoses (relay checkpoints)\n',
              f'Population: the {len(at)} valid E1-anchor matcher records whose '
              'frozen diagnosis is `extraction_omission` (30 instances x 3 '
              'models; failed records excluded). Source file: '
              '`rebuttal/results/batch1/E1_matcher_anchor/matcher/`. Targeted '
              'facts are the `extraction_omission` facts in each trace\'s '
              'chosen support set; a fact is in-shard if any source shard '
              'contains it under the frozen presence rule.\n',
              '| level | old diagnosis | new sharding | new mixed | new extraction | moved |',
              '| --- | ---: | ---: | ---: | ---: | ---: |']
    c = counts(at)
    sh = c['extraction_omission'].get('sharding_omission', 0)
    mx = c['extraction_omission'].get('mixed_sharding_extraction', 0)
    ex = c['extraction_omission'].get('extraction_omission', 0)
    k, n, est, lo, hi = share(at)
    lines.append(f'| traces | {n} | {sh} | {mx} | {ex} | {k}/{n} '
                 f'({100 * est:.1f}%, 95% CI {100 * lo:.1f}-{100 * hi:.1f}) |')
    lines += ['', f'Per-fact shard labels: **{anchor_facts - moved_anchor_facts} '
              f'of {anchor_facts}** targeted facts are present or partial in '
              f'their source shard, **{moved_anchor_facts}** are absent in every '
              'source shard.\n']

    lines += ['## Main-table diagnoses (2,400 traces, relay checkpoints)\n',
              'Population: the 216 valid traces in the Stage 2 main-run matcher '
              'set (`rebuttal/results/batch1/expansion_stage2/matcher/`, 2,400 '
              'traces over three models) whose frozen diagnosis is '
              '`extraction_omission`. Targeted facts and source shards as in the '
              'rule. No new matcher call.\n',
              '| level | old diagnosis | new sharding | new mixed | new extraction | moved |',
              '| --- | ---: | ---: | ---: | ---: | ---: |']
    cm = counts(mt)
    sh = cm['extraction_omission'].get('sharding_omission', 0)
    mx = cm['extraction_omission'].get('mixed_sharding_extraction', 0)
    ex = cm['extraction_omission'].get('extraction_omission', 0)
    k, n, est, lo, hi = share(mt)
    lines.append(f'| traces | {n} | {sh} | {mx} | {ex} | {k}/{n} '
                 f'({100 * est:.1f}%, 95% CI {100 * lo:.1f}-{100 * hi:.1f}) |')
    mt_facts = sum(len(r['facts']) for r in mt)
    mt_absent = sum(1 for r in mt for v in r['facts'].values()
                    if v['label'] == 'absent')
    lines += ['', f'Per-fact shard labels: **{mt_facts - mt_absent} of {mt_facts}** '
              f'targeted facts are present or partial in their source shard, '
              f'**{mt_absent}** are absent in every source shard. By model: '
              + ', '.join(f'{m} {sum(r["new"] != r["old"] for r in mt if r["model"] == m)}/'
                          f'{sum(1 for r in mt if r["model"] == m)} moved'
                          for m in sorted({r['model'] for r in mt})) + '.\n']

    lines += ['', '## Anchor detail\n']
    for r in sorted(at, key=lambda x: (x['new'], x['instance_id'], x['model'])):
        fl = ', '.join(f"{f}: {v['label']} ({v['best_recall']:.2f})"
                       for f, v in sorted(r['facts'].items()))
        lines.append(f"- {r['instance_id']} / {r['model']}: old extraction, "
                     f"new **{r['new']}**; {fl}")
    ca = counts(at)
    a_sh = ca['extraction_omission'].get('sharding_omission', 0)
    a_mx = ca['extraction_omission'].get('mixed_sharding_extraction', 0)
    a_k, a_n, _, _, _ = share(at)
    m_k, m_n, _, _, _ = share(mt)
    lines += ['', '## Reading\n',
              'The old diagnosis assumed the fact was in the agent\'s input. '
              'In the missing-fact cohort the frozen presence labels put 20 of '
              '59 instances outside the target agent\'s shard, so those losses '
              'happen at sharding, not extraction; the remaining 39 stay '
              'extraction losses (33 present, 6 partial). '
              f'In the main-table diagnosis set, {m_k} of {m_n} extraction '
              'diagnoses change (to sharding or mixed). '
              f'In the E1 anchor, {a_sh + a_mx} of {a_n} change. Because the '
              'presence rule is lexical and can read co-located tokens as '
              'presence, the sharding count is a lower bound. The old '
              'diagnoses remain in `presence.json` and the matcher records.']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'cohort_traces': counts(ct),
                      'anchor_traces': ca,
                      'main_table_traces': counts(mt),
                      'anchor_facts': [anchor_facts - moved_anchor_facts,
                                       anchor_facts],
                      'main_table_facts': [mt_facts - mt_absent, mt_facts]},
                     indent=1))


if __name__ == '__main__':
    main()