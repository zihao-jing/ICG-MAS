"""Freeze the E4 direct-insertion spans from frozen inputs, before any call.

No model call, no outcome read. For each of the 17 extraction cases the targeted fact is taken from
the frozen action manifest (first fact with an empty extraction carrier), and the donor control is
the contiguous donor-source passage fixed by amendment A3. The plan is hashed before the run.

    python -m scripts.build_e4_insertion_plan
"""
import json
import re
from pathlib import Path

from src.audit.base_tokenizers import count_added_tokens, volume_match
from src.audit.pilot_common import digest, freeze

from scripts.run_frozen_repair import original_prompt

ACTIONS = Path('rebuttal/pilots/20261110_e4_phase1/actions_phase1.json')
PREREG = Path('rebuttal/pilots/prereg/E4-direct-insertion-A3.md')
OUT = Path('rebuttal/pilots/20261110_e4_insert/insertion_plan.json')
LO, HI = 0.90, 1.10


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if s.strip()]


def evidence_sentences(text):
    out = []
    for s in sentences(text):
        if s.startswith('Question:') or s == 'You hold the following evidence:' or s.startswith('[Document:'):
            continue
        out.append(s)
    return out


def trim_words(text, hi, tok):
    words = text.split()
    while words and tok(' '.join(words)) > hi:
        words.pop()
    return ' '.join(words)


def choose_control(context, target_tokens, tok):
    """Amendment A3 rule: accepted contiguous sentence run closest to T, ties by start then length."""
    ss = evidence_sentences(context)
    lo, hi = LO * target_tokens, HI * target_tokens
    best = None
    for i in range(len(ss)):
        acc = ''
        for j in range(i, len(ss)):
            acc = (acc + ' ' + ss[j]).strip()
            n = tok(acc)
            if n < lo:
                if n > hi:
                    break
                continue
            if n <= hi:
                cand, cn, trunc = acc, n, False
            else:
                cand = trim_words(acc, hi, tok)
                cn, trunc = tok(cand), True
                if cn < lo:
                    break
            key = (abs(cn - target_tokens), i, j - i)
            if best is None or key < best['key']:
                best = {'key': key, 'text': cand, 'tokens': cn, 'start': i, 'end': j,
                        'truncated': trunc, 'raw_tokens': n}
            break
    return best


def main():
    rows = json.loads(ACTIONS.read_text())
    ext = [r for r in rows if r['group'] == 'extraction_omission']
    assert len(ext) == 17, len(ext)
    cases = []
    for r in ext:
        car = {c['fact_id']: c for c in r['carriers']['facts']}
        fid = next(c['fact_id'] for c in r['carriers']['facts'] if not c['extraction'])
        fact = next(f for f in r['facts']['facts'] if f['fact_id'] == fid)
        tok = lambda text: count_added_tokens(r['model'], text)
        target_tokens = tok(fact['text'])
        dctx = next(s['text'] for s in r['source_contexts'] if s['agent_id'] == r['donor_agent'])
        best = choose_control(dctx, target_tokens, tok)
        repair = {'unit_id': 'R-ins:0', 'agent_id': r['target_agent'], 'text': fact['text']}
        row = {'trace_id': r['trace_id'], 'instance_id': r['instance_id'], 'model': r['model'],
               'benchmark': r['benchmark'], 'target_agent': r['target_agent'],
               'donor_agent': r['donor_agent'], 'fact_id': fid, 'fact_source_ids': fact['source_ids'],
               'repair_unit': repair, 'repair_tokens': target_tokens,
               'board_sha256': r['board_sha256'],
               'donor_context_sha256': digest(dctx),
               'donor_fallback': None, 'control_unit': None, 'control_tokens': None,
               'volume_matched': False, 'ratio': None, 'control_unmatched': True,
               'control_rule': {'lo': LO, 'hi': HI, 'start': None, 'end': None,
                                'truncated': None, 'raw_tokens': None}}
        if best is not None and best['tokens'] > 0:
            ctl = {'unit_id': 'V-ins:0', 'agent_id': r['donor_agent'], 'text': best['text']}
            m = volume_match(r['model'], [repair], [ctl])
            row.update(control_unit=ctl, control_tokens=m['control_tokens'],
                       volume_matched=m['matched'], ratio=round(m['control_tokens'] / target_tokens, 4),
                       control_unmatched=not m['matched'],
                       control_rule={'lo': LO, 'hi': HI, 'start': best['start'], 'end': best['end'],
                                     'truncated': best['truncated'], 'raw_tokens': best['raw_tokens']})
        # strict manipulation precheck on the actual aggregator input
        checks = {}
        for arm, unit in (('R-ins', repair), ('V-ins', row['control_unit'])):
            if unit is None:
                checks[arm] = None
                continue
            board = [dict(u) for u in r['board_units']] + [unit]
            _, user = original_prompt(r, board)
            norm = lambda s: ' '.join(''.join(ch if ch.isalnum() else ' ' for ch in s.casefold()).split())
            checks[arm] = norm(unit['text']) in norm(user)
        row['manipulation_precheck'] = checks
        cases.append(row)
    man = {(c['instance'], c['model']): c
           for c in json.loads(Path('rebuttal/results/batch1/E4_manifest/manifest.json').read_text())['cases']}
    fam = {'qwen/qwen3-235b-a22b-2507': 'qwen235b', 'openai/gpt-4o-mini': 'gpt4omini',
           'google/gemma-4-31b-it': 'gemma31b'}
    for row in cases:
        row['donor_fallback'] = man[(row['instance_id'], fam[row['model']])]['donor_fallback']
    plan = {'purpose': 'E4 direct insertion: frozen spans, no call, no outcome',
            'amendment': str(PREREG), 'amendment_sha256': digest(PREREG.read_bytes()),
            'actions': str(ACTIONS), 'actions_sha256': digest(ACTIONS.read_bytes()),
            'cases': cases}
    freeze(OUT, plan)
    print(json.dumps({'cases': len(cases), 'planned_calls': 2 * len(cases),
                      'volume_matched': sum(c['volume_matched'] for c in cases),
                      'unmatched': [c['instance_id'] for c in cases if c['control_unmatched']],
                      'fallback': sum(c['donor_fallback'] for c in cases),
                      'manipulation_precheck_failed': [c['instance_id'] for c in cases
                                                       if not all(c['manipulation_precheck'].values())],
                      'plan_sha256': digest(OUT.read_bytes())}, indent=1))


if __name__ == '__main__':
    main()