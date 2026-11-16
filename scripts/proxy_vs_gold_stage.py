"""Proxy-fact vs gold-fact audit stage agreement on the three Q1 samples. No calls.

Rule `prereg/Proxy-vs-gold-stage.md`, hashed before this script runs.

    ./run.sh python -m scripts.proxy_vs_gold_stage
"""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from scripts.proxy_support_run import STAGE, carriers_for
from src.audit.sharding_check import diagnose_with_sharding

ROOT = Path(__file__).resolve().parent.parent
PILOTS = ROOT / 'rebuttal/pilots'
RULE = PILOTS / 'prereg/Proxy-vs-gold-stage.md'
AMEND = PILOTS / 'prereg/Proxy-vs-gold-stage-amendment-1.md'
OUT = PILOTS / '20261115_proxy_vs_gold_stage'
MQ = PILOTS / '20261115_proxy_support_mq'
SAMPLES = {'sample1_uniform': '20261115_q1_gold_stage',
           'sample2_coarse': '20261115_q1_gold_stage_2',
           'sample3_atom': '20261115_q1_gold_stage_3'}
STAGES = ('extraction', 'transmission', 'aggregation')


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def proxy_stages():
    pop = json.loads((MQ / 'population.json').read_text())
    facts = json.loads((MQ / 'facts.json').read_text())
    labels = json.loads((MQ / 'labels.json').read_text())
    out = {}
    for r in pop:
        if not r.get('has_extraction'):
            continue
        f = facts.get(r['key'], {})
        if f.get('status') != 'ok':
            continue
        labs, ok = {}, True
        for chk in ('extraction', 'board'):
            rec = labels.get(f"audit/{r['key']}/{chk}", {})
            if rec.get('status') != 'ok':
                ok = False
                break
            for fid, lab in rec['value'].items():
                labs[f'{chk}/{fid}'] = lab
        if not ok:
            continue
        fids = [x['fact_id'] for x in f['value']['facts']]
        trace = {'question': r['question'],
                 'source_contexts': [{'context_id': d['unit_id'], 'text': d['text']}
                                     for d in r['documents']]}
        lab, _ = diagnose_with_sharding({'facts': f['value']['facts'],
                                         'support_sets': f['value']['support_sets']},
                                        carriers_for(labs, fids), trace, correct=False)
        out[r['key']] = {'instance': r['instance_id'], 'protocol': r['protocol'],
                         'stage': STAGE.get(lab, lab)}
    return out


def gold_stages(dirname):
    items = json.loads((PILOTS / dirname / 'results.json').read_text())
    STATUS = {'present', 'partial', 'absent'}

    def valid(labels, atoms):
        A = set(atoms)
        return (isinstance(labels, dict) and set(labels) == A
                and all(isinstance(v, dict) and v.get('status') in STATUS
                        and isinstance(v.get('unit_ids'), list) for v in labels.values()))

    out = {}
    for inst, rec in items.items():
        e, b = rec['labels'].get('extraction'), rec['labels'].get('board')
        if not (valid(e, rec['atoms']) and valid(b, rec['atoms'])):
            out[inst] = None
        elif any(v['status'] == 'absent' for v in e.values()):
            out[inst] = 'extraction'
        elif any(v['status'] == 'absent' for v in b.values()):
            out[inst] = 'transmission'
        else:
            out[inst] = 'aggregation'
    return out


def main():
    actual = file_sha(RULE)
    OUT.mkdir(parents=True, exist_ok=True)
    px = proxy_stages()
    # self-check: this path must reproduce the stored random_relay distribution
    stored = json.loads((MQ / 'results.json').read_text())['stage_distribution']['random_relay']
    mine = Counter(v['stage'] for v in px.values() if v['protocol'] == 'random_relay')
    check = {s: [mine.get(s, 0), stored.get(s, 0)] for s in set(mine) | set(stored)}
    ok_check = all(a == b for a, b in check.values())

    am_actual = file_sha(AMEND)
    out = {'rule_sha256': actual, 'amendment_sha256': am_actual, 'self_check_ok': ok_check, 'self_check': check, 'samples': {}}
    for name, dirname in SAMPLES.items():
        gold = gold_stages(dirname)
        pairs = []
        for inst, g in gold.items():
            p = px.get(f'qwen235b|MQ|results/run_qwen235b_musique|random_relay|{inst}')
            pairs.append((inst, (p or {}).get('stage'), g))
        both = [(i, p, g) for i, p, g in pairs if p in STAGES and g in STAGES]
        conf = {p: {g: 0 for g in STAGES} for p in STAGES}
        for _, p, g in both:
            conf[p][g] += 1
        k = sum(1 for _, p, g in both if p == g)
        lo, hi = wilson(k, len(both))
        out['samples'][name] = {'n_gold': sum(1 for _, _, g in pairs if g in STAGES),
                                'n_both': len(both), 'agree': k,
                                'rate': k / len(both) if both else None,
                                'wilson': [lo, hi],
                                'no_proxy_stage': sum(1 for _, p, g in pairs if p not in STAGES),
                                'no_gold_stage': sum(1 for _, p, g in pairs if g not in STAGES),
                                'confusion': conf}
    (OUT / 'score.json').write_text(json.dumps(out, indent=1))

    lines = ['# Proxy-fact vs gold-fact audit stage agreement', '',
             '2026-11-15. Rule `Proxy-vs-gold-stage.md` (sha `%s...`), amendment 1 (sha `%s...`). No calls, $0. The quantity is '
             'agreement between two audit computations on the same traces, not accuracy against a true stage.'
             % (actual[:8], am_actual[:8]),
             '',
             '| sample | gold stage | both stages | agree | rate [95% Wilson] | no proxy stage |',
             '| --- | ---: | ---: | ---: | --- | ---: |']
    for name, s in out['samples'].items():
        r = '%.3f [%.3f, %.3f]' % (s['rate'], s['wilson'][0], s['wilson'][1]) if s['rate'] is not None else '—'
        lines.append('| %s | %d | %d | %d | %s | %d |'
                     % (name, s['n_gold'], s['n_both'], s['agree'], r, s['no_proxy_stage']))
    lines += ['', 'The gold stage column is the number of traces with a gold stage (13, 11, 15 after amendment 1); '
              'the both-stages column is one fewer per sample because one trace has no proxy stage. The agreement '
              'denominator is the both-stages column.']
    lines += ['', '## Confusion, proxy stage (rows) by gold stage (columns)', '']
    for name, s in out['samples'].items():
        lines += ['### %s' % name, '', '| proxy \\ gold | extraction | transmission | aggregation |',
                  '| --- | ---: | ---: | ---: |']
        for p in STAGES:
            lines.append('| %s | %s |' % (p, ' | '.join(str(s['confusion'][p][g]) for g in STAGES)))
        lines.append('')
    lines += ['## Checks and caveats', '',
              'The proxy stage path reproduces the stored `random_relay` distribution: %s.'
              % ('yes' if ok_check else 'NO — do not read the rates'),
              '',
              'The same labeller labels both fact sets at the same checkpoints, so shared labeller error inflates '
              'the rate. Samples 2 and 3 draw traces by a lexical-loss filter and share their 30 traces.']
    (OUT / 'report.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()