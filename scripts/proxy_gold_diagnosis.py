"""Diagnose every proxy-vs-gold stage disagreement from the stored labels. No calls.

Rule `prereg/Proxy-gold-disagreement-causes.md`, hashed before this runs.

    ./run.sh python -m scripts.proxy_gold_diagnosis
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

from src.audit.e4_fix_gates import STOP, recall
from src.eval.evaluate import normalize

ROOT = Path(__file__).resolve().parent.parent
PILOTS = ROOT / 'rebuttal/pilots'
RULE = PILOTS / 'prereg/Proxy-gold-disagreement-causes.md'
MQ = PILOTS / '20261115_proxy_support_mq'
ATOM = PILOTS / '20261115_proxy_atom_presence/results.jsonl'
OUT = PILOTS / '20261115_proxy_vs_gold_stage'
SAMPLES = {'sample1_uniform': '20261115_q1_gold_stage',
           'sample2_coarse': '20261115_q1_gold_stage_2',
           'sample3_atom': '20261115_q1_gold_stage_3'}
STAGES = ('extraction', 'transmission', 'aggregation')
STATUS = {'present', 'partial', 'absent'}


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def toks(text):
    return [t for t in normalize(text) if t not in STOP]


def cov(text, atom):
    t = toks(atom)
    return 1.0 if not t else recall(text, ' '.join(t))


def gold_valid(labels, atoms):
    A = set(atoms)
    return (isinstance(labels, dict) and set(labels) == A
            and all(isinstance(v, dict) and v.get('status') in STATUS
                    and isinstance(v.get('unit_ids'), list) for v in labels.values()))


def gold_stage(rec):
    e, b = rec['labels'].get('extraction'), rec['labels'].get('board')
    if not (gold_valid(e, rec['atoms']) and gold_valid(b, rec['atoms'])):
        return None, None, None
    if any(v['status'] == 'absent' for v in e.values()):
        return 'extraction', 'extraction', e
    if any(v['status'] == 'absent' for v in b.values()):
        return 'transmission', 'board', b
    return 'aggregation', None, None


def main():
    rule_sha = file_sha(RULE)
    pop = {r['instance_id']: r for r in json.loads((MQ / 'population.json').read_text())
           if r['protocol'] == 'random_relay'}
    facts = json.loads((MQ / 'facts.json').read_text())
    atom_rows = [json.loads(l) for l in ATOM.read_text().splitlines() if l.strip()]
    atom_by_key = {}
    for r in atom_rows:
        atom_by_key.setdefault(r['key'], []).append(r)
    proxy = {}
    for key, rows in atom_by_key.items():
        inst = rows[0]['instance']
        if any(not r['valid'] for r in rows):
            proxy[inst] = None
            continue
        if any(r['stages']['extraction'] == 'absent' for r in rows):
            proxy[inst] = 'extraction'
        elif any(r['stages']['board'] == 'absent' for r in rows):
            proxy[inst] = 'transmission'
        else:
            proxy[inst] = 'aggregation'

    out = {'rule_sha256': rule_sha, 'samples': {}}
    for name, dirname in SAMPLES.items():
        items = json.loads((PILOTS / dirname / 'results.json').read_text())
        traces = []
        excluded = 0
        for inst, rec in items.items():
            gs, cp, lab = gold_stage(rec)
            ps = proxy.get(inst)
            if gs is None or ps is None:
                excluded += 0 if gs is not None else 1
                continue
            if gs == ps:
                continue
            if gs == 'aggregation':
                row = pop[inst]
                rows = [r for r in atom_rows if r['key'] == row['key']]
                cp = 'extraction' if any(r['stages']['extraction'] == 'absent' for r in rows) else 'board'
                fe = facts[row['key']]['value']['facts']
                pa = []
                for r in rows:
                    ft = next((f['text'] for f in fe if f['fact_id'] == r['fact_id']), '')
                    for aid, st in (r['atoms'].get(cp) or {}).items():
                        if st == 'absent':
                            idx = int(aid[1:]) - 1
                            parts = [x.strip() for x in ft.replace('\n', ' ').split('. ')
                                     if len(x.strip()) > 3]
                            pa.append({'atom': parts[idx][:200] if idx < len(parts) else aid,
                                       'fact_id': r['fact_id']})
                traces.append({'instance': inst, 'gold_stage': gs, 'proxy_stage': ps,
                               'checkpoint': cp, 'atoms': [], 'proxy_absent_atoms': pa,
                               'cause': 'no gold-absent atom (gold reports all present)'})
                continue
            row = pop[inst]
            entries = '\n'.join(u['text'] for u in (row['checkpoints'].get(cp) or []))
            fe = facts[row['key']]['value']['facts']
            atoms = []
            for atom, v in lab.items():
                if v['status'] != 'absent':
                    continue
                r_evid = cov(entries, atom)
                best = None
                for f in fe:
                    recs = [r for r in atom_rows if r['key'] == row['key'] and r['fact_id'] == f['fact_id']]
                    st = (recs[0]['atoms'].get(cp) if recs else {}) or {}
                    for i, a in enumerate([x.strip() for x in f['text'].replace('\n', ' ').split('. ')
                                           if len(x.strip()) > 3], 1):
                        r = cov(a, atom)
                        if best is None or r > best[0]:
                            best = (r, f['fact_id'], f['text'], a, st.get(f'a{i}'))
                pr_rec, pf_id, pf_text, pf_atom, pf_status = best if best else (0.0, None, '', '', None)
                if r_evid >= 0.8:
                    cause = 'gold labeller error'
                elif pr_rec >= 0.5 and pf_status == 'present':
                    cause = 'wording mismatch'
                else:
                    cause = 'proxy fact does not carry the atom'
                atoms.append({'atom': atom[:200], 'recall_entries': round(r_evid, 3),
                              'proxy_fact_id': pf_id, 'proxy_fact': pf_text[:200],
                              'proxy_atom': pf_atom[:160], 'proxy_atom_status': pf_status,
                              'recall_proxy_atom': round(pr_rec, 3), 'cause': cause})
            causes = Counter(a['cause'] for a in atoms)
            trace_cause = causes.most_common(1)[0][0] if causes else 'no absent atom'
            traces.append({'instance': inst, 'gold_stage': gs, 'proxy_stage': ps,
                           'checkpoint': cp, 'atoms': atoms, 'cause': trace_cause})
        out['samples'][name] = {'excluded_no_gold_stage': excluded, 'disagree': traces,
                                'by_cause': dict(Counter(t['cause'] for t in traces)),
                                'direction': dict(Counter('%s->%s' % (t['proxy_stage'], t['gold_stage'])
                                                          for t in traces))}

    # report
    lines = ['# Why the proxy and gold audit stages disagree', '',
             '2026-11-15. Rule `Proxy-gold-disagreement-causes.md` (sha `%s...`). $0, stored labels only. '
             'Population: traces of the three Q1 samples where the atom-level proxy stage and the gold stage both '
             'exist and differ. The labeller is Claude Haiku 5.5 on both sides: the gold labels use the atom-level '
             'point prompt v1 (sha `86d84ff6...`), the stored proxy checkpoint labels use the fact-level prompt v3 '
             '(sha `3f7f19bb...`), and the atom-level proxy fix uses prompt v1 again.' % rule_sha[:8], '',
             '| sample | direction (proxy to gold) | traces | gold labeller error | wording mismatch | '
             'proxy fact does not carry the atom | no gold-absent atom |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for name, s in out['samples'].items():
        for d, n in sorted(s['direction'].items()):
            c = Counter(t['cause'] for t in s['disagree']
                        if '%s->%s' % (t['proxy_stage'], t['gold_stage']) == d)
            lines.append('| %s | %s | %d | %d | %d | %d | %d |'
                         % (name, d, n, c.get('gold labeller error', 0),
                            c.get('wording mismatch', 0), c.get('proxy fact does not carry the atom', 0),
                            c.get('no gold-absent atom (gold reports all present)', 0)))
    lines += ['', '## Atom-level detail', '']
    for name, s in out['samples'].items():
        lines += ['### %s' % name, '']
        for t in s['disagree']:
            lines += ['**`%s`** — proxy %s, gold %s at %s; trace cause: %s.' %
                      (t['instance'], t['proxy_stage'], t['gold_stage'], t['checkpoint'], t['cause']), '']
            if not t['atoms']:
                lines += ['Gold marks no atom absent at either checkpoint. The proxy side fails first at %s on: %s.'
                          % (t['checkpoint'], '; '.join('`%s`: %s' % (a['fact_id'], a['atom'].replace('|', '/'))
                                                        for a in t.get('proxy_absent_atoms') or [])), '']
                continue
            lines += ['| gold atom (absent) | recalled from gold entries | closest proxy atom | in fact | '
                      'recalled from proxy atom | proxy atom status | cause |',
                      '| --- | ---: | --- | --- | ---: | --- | --- |']
            for a in t['atoms']:
                lines.append('| %s | %.3f | %s | `%s` | %.3f | %s | %s |'
                             % (a['atom'].replace('|', '/'), a['recall_entries'],
                                a['proxy_atom'].replace('|', '/'), a['proxy_fact_id'],
                                a['recall_proxy_atom'], a['proxy_atom_status'], a['cause']))
            lines.append('')
    lines += ['## Excluded', '',
              'Traces without a gold stage (a checkpoint failed the frozen parser, so the atom keys did not match) '
              'are outside the comparison: %s.'
              % ', '.join('%s %d' % (k, v['excluded_no_gold_stage']) for k, v in out['samples'].items())]
    (OUT / 'diagnosis.md').write_text('\n'.join(lines) + '\n')
    (OUT / 'diagnosis.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({k: {'disagree': len(v['disagree']), 'by_cause': v['by_cause'],
                          'direction': v['direction'], 'excluded': v['excluded_no_gold_stage']}
                      for k, v in out['samples'].items()}, indent=1))


if __name__ == '__main__':
    main()