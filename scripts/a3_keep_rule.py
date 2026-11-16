"""Keep rule check for every kept A3/A4 case (step 10b). $0, reads stored records only.

Keep only if: exactly one critical fact is removed, at the intended stage, and the intended fact has no surviving copy.
Fact presence uses the injection plan's own test: content-token coverage >= COVER (injection_amendA.COVER = 0.5)
of a fact's tokens (length > 2) in a unit (extraction) or a sentence (source shard).
  - base_present[f]: some unit (extraction case) or sentence (sharding case) in the untouched trace covers f.
  - after_present[f]: some remaining unit / sentence in the modified trace covers f.
  - removed facts = base_present and not after_present. Pass iff removed == {intended fact} and not after_present[intended].
    ./.conda-env/bin/python -m scripts.a3_keep_rule
Output: rebuttal/pilots/20261115_injection_amendA3/keep_rule.json
"""
import json
from pathlib import Path

import scripts.injection_amendA as A
import scripts.injection_experiment as X

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / 'rebuttal/pilots/20261115_injection_amendA3/results.json'
OUT = ROOT / 'rebuttal/pilots/20261115_injection_amendA3/keep_rule.json'


def covered(F, text):
    return bool(F) and len(F & A.content(text)) / len(F) >= A.COVER


def check(c):
    pkg = A.pkgs(c['model'])[c['instance']]
    rec = A.recs()[(c['model'], c['instance'])]
    facts = rec['facts']['facts']
    intended = c['plan']['fact_id']
    if c['type'] == 'extraction':
        removed = set(c['meta']['removed_units'])
        units = {u['unit_id']: u['text'] for u in pkg['checkpoints']['extraction']}
        base_texts = list(units.values())
        after_texts = [t for uid, t in units.items() if uid not in removed]
    else:
        # sharding: the modified contexts (plan deletion applied to the same sentences)
        # same deletion as injection_amendA.make_case: plain replace of each target sentence, then re-split
        base_texts = [s for ctx in pkg['source_contexts'] for s in X.sentences(ctx['text'])]
        after_texts = []
        for ctx in pkg['source_contexts']:
            txt = ctx['text']
            for t in c['plan']['targets']:
                if t['agent'] == ctx['agent_id']:
                    txt = txt.replace(t['sentence'], '')
            after_texts += X.sentences(txt)
    base_p, after_p = {}, {}
    for f in facts:
        F = A.content(f['text'])
        base_p[f['fact_id']] = any(covered(F, t) for t in base_texts)
        after_p[f['fact_id']] = any(covered(F, t) for t in after_texts)
    removed_facts = sorted(f for f in base_p if base_p[f] and not after_p[f])
    ok = removed_facts == [intended] and not after_p[intended]
    return {'model': c['model'], 'instance': c['instance'], 'type': c['type'], 'intended': intended,
            'base_present': sorted(f for f in base_p if base_p[f]),
            'removed_facts': removed_facts,
            'surviving_copy_of_intended': after_p[intended],
            'pass': ok}


def main():
    cases = [c for c in json.loads(RES.read_text())['cases'] if c.get('kept')]
    out = [check(c) for c in cases]
    OUT.write_text(json.dumps(out, indent=1) + '\n')
    for o in out:
        print(json.dumps(o))
    print('pass', sum(o['pass'] for o in out), 'of', len(out))


if __name__ == '__main__':
    main()
