"""Causes of proxy-vs-gold disagreements on the validated-renderer pair. No calls.

Same method as `Proxy-gold-disagreement-causes.md`, applied to the validated rerun records.

    ./run.sh python -m scripts.proxy_gold_diagnosis_validated
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
AMEND = PILOTS / 'prereg/Proxy-gold-disagreement-causes-amendment-2.md'
MQ = PILOTS / '20261115_proxy_support_mq'
RUN = PILOTS / '20261115_q1_validated_rerun/results.jsonl'
OUT = PILOTS / '20261115_proxy_vs_gold_stage'
SAMPLES = {'sample1_uniform': '20261115_q1_gold_stage',
           'sample2_coarse': '20261115_q1_gold_stage_2',
           'sample3_atom': '20261115_q1_gold_stage_3'}
STAGES = ('extraction', 'transmission', 'aggregation')


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def cov(text, atom):
    t = [x for x in normalize(atom) if x not in STOP]
    return 1.0 if not t else recall(text, ' '.join(t))


def atoms_of(text):
    return [a.strip() for a in text.replace('\n', ' ').split('. ') if len(a.strip()) > 3]


def side_stage(rows, cp):
    sts = [r['stages'].get(cp) for r in rows]
    return 'absent' in sts


def main():
    pop = {r['instance_id']: r for r in json.loads((MQ / 'population.json').read_text())
           if r['protocol'] == 'random_relay'}
    facts = json.loads((MQ / 'facts.json').read_text())
    recs = [json.loads(l) for l in RUN.read_text().splitlines() if l.strip()]
    by = {}
    for r in recs:
        by.setdefault(r['instance'], {'gold': [], 'proxy': []})[r['kind']].append(r)

    def stages(inst):
        d = by[inst]
        g = ('extraction' if side_stage(d['gold'], 'extraction') else
             'transmission' if side_stage(d['gold'], 'board') else 'aggregation')
        p = ('extraction' if side_stage(d['proxy'], 'extraction') else
             'transmission' if side_stage(d['proxy'], 'board') else 'aggregation')
        return g, p

    out = {'rule_sha256': file_sha(RULE), 'amendment_sha256': file_sha(AMEND), 'samples': {}}
    for name, dirname in SAMPLES.items():
        ids = list(json.loads((PILOTS / dirname / 'results.json').read_text()))
        traces = []
        for inst in ids:
            g, p = stages(inst)
            if g == p:
                continue
            row = pop[inst]
            if g == 'aggregation':
                cp = 'extraction' if side_stage(by[inst]['proxy'], 'extraction') else 'board'
                pa = []
                for r in by[inst]['proxy']:
                    for aid, st in (r['atoms'].get(cp) or {}).items():
                        if st == 'absent':
                            idx = int(aid[1:]) - 1
                            parts = atoms_of(next((f['text'] for f in facts[row['key']]['value']['facts']
                                                   if f['fact_id'] == r['fact_id']), ''))
                            pa.append({'atom': (parts[idx] if idx < len(parts) else aid)[:200],
                                       'fact_id': r['fact_id']})
                traces.append({'instance': inst, 'gold_stage': g, 'proxy_stage': p, 'checkpoint': cp,
                               'atoms': [], 'proxy_absent_atoms': pa,
                               'cause': 'no gold-absent atom (gold reports all present)'})
                continue
            cp = 'extraction' if g == 'extraction' else 'board'
            entries = '\n'.join(u['text'] for u in (row['checkpoints'].get(cp) or []))
            g_atoms = [(a, v) for a, v in (by[inst]['gold'][0]['atoms'].get(cp) or {}).items()]
            atoms = []
            for aid, status in g_atoms:
                if status != 'absent':
                    continue
                atom = atoms_of((row.get('gold_supports') or [{'text': ''}])[0]['text'])[int(aid[1:]) - 1]
                r_evid = cov(entries, atom)
                best = None
                for r in by[inst]['proxy']:
                    parts = atoms_of(next((f['text'] for f in facts[row['key']]['value']['facts']
                                           if f['fact_id'] == r['fact_id']), ''))
                    st = r['atoms'].get(cp) or {}
                    for i, part in enumerate(parts, 1):
                        v = cov(part, atom)
                        if best is None or v > best[0]:
                            best = (v, r['fact_id'], part, st.get(f'a{i}'))
                pr = best if best else (0.0, None, '', None)
                if r_evid >= 0.8:
                    cause = 'gold labeller error'
                elif pr[0] >= 0.5 and pr[3] == 'present':
                    cause = 'wording mismatch'
                else:
                    cause = 'proxy fact does not carry the atom'
                atoms.append({'atom': atom[:200], 'recall_entries': round(r_evid, 3),
                              'proxy_fact_id': pr[1], 'proxy_atom': pr[2][:160],
                              'proxy_atom_status': pr[3], 'recall_proxy_atom': round(pr[0], 3),
                              'cause': cause})
            c = Counter(a['cause'] for a in atoms)
            traces.append({'instance': inst, 'gold_stage': g, 'proxy_stage': p, 'checkpoint': cp,
                           'atoms': atoms, 'cause': c.most_common(1)[0][0] if c else 'no absent atom'})
        out['samples'][name] = {'disagree': traces,
                                'by_cause': dict(Counter(t['cause'] for t in traces)),
                                'atom_causes': dict(Counter(a['cause'] for t in traces for a in t['atoms'])),
                                'direction': dict(Counter('%s->%s' % (t['proxy_stage'], t['gold_stage'])
                                                          for t in traces))}
    lines = ['# Why the proxy and gold audit stages disagree (validated-renderer pair)', '',
             '2026-11-15. Rule `Proxy-gold-disagreement-causes.md` (sha `%s...`), amendment 2 (sha `%s...`); same '
             'method applied to the validated-renderer records. $0, stored labels only. Both sides labelled by Claude '
             'Haiku 5.5 with the atom-level point prompt v1 and `a1: text` ids.' %
             (out['rule_sha256'][:8], out['amendment_sha256'][:8]), '',
             '| sample | direction (proxy to gold) | traces | gold labeller error | wording mismatch | '
             'proxy fact does not carry the atom | no gold-absent atom |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for name, s in out['samples'].items():
        for d, n in sorted(s['direction'].items()):
            c = Counter(t['cause'] for t in s['disagree']
                        if '%s->%s' % (t['proxy_stage'], t['gold_stage']) == d)
            lines.append('| %s | %s | %d | %d | %d | %d | %d |'
                         % (name, d, n, c.get('gold labeller error', 0), c.get('wording mismatch', 0),
                            c.get('proxy fact does not carry the atom', 0),
                            c.get('no gold-absent atom (gold reports all present)', 0)))
    tot = Counter()
    for s in out['samples'].values():
        tot.update(s['by_cause'])
    ac = Counter()
    for s in out['samples'].values():
        ac.update(s['atom_causes'])
    lines += ['', '**All samples: %d disagreeing traces — proxy fact does not carry the atom %d, no gold-absent atom %d, '
              'wording mismatch %d, gold labeller error %d. At atom level: %s.**'
              % (sum(tot.values()), tot.get('proxy fact does not carry the atom', 0),
                 tot.get('no gold-absent atom (gold reports all present)', 0),
                 tot.get('wording mismatch', 0), tot.get('gold labeller error', 0),
                 ', '.join('%s %d' % (k, v) for k, v in ac.most_common())), '',
              '## Atom-level detail', '']
    for name, s in out['samples'].items():
        lines += ['### %s' % name, '']
        for t in s['disagree']:
            lines += ['**`%s`** — proxy %s, gold %s at %s; trace cause: %s.' %
                      (t['instance'], t['proxy_stage'], t['gold_stage'], t['checkpoint'], t['cause']), '']
            if not t['atoms']:
                lines += ['Gold marks no atom absent at either checkpoint. The proxy side fails first at %s on: %s.'
                          % (t['checkpoint'], '; '.join('`%s`: %s' % (a['fact_id'], a['atom'].replace('|', '/'))
                                                        for a in t['proxy_absent_atoms'] or [])), '']
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
    (OUT / 'diagnosis_validated.md').write_text('\n'.join(lines) + '\n')
    (OUT / 'diagnosis_validated.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({k: {'disagree': len(v['disagree']), 'by_cause': v['by_cause'],
                          'atom_causes': v['atom_causes'], 'direction': v['direction']}
                      for k, v in out['samples'].items()}, indent=1))


if __name__ == '__main__':
    main()