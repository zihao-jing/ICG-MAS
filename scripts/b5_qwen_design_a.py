"""B5 follow-up check: the Qwen audit cell through the design-A pipeline, plus the two Gemini retries.

Frozen facts from the Qwen matcher; the same CARRIER_PROMPT, the same diagnose_with_sharding. Cap $1.00.
The two Gemini carrier_failed cases are retried once more; if they fail again they are reported missing.

    ./run.sh python -m scripts.b5_qwen_design_a --run
"""
import argparse
import json
from pathlib import Path

import scripts.b5_attribution_2x2 as B
from scripts.audit_diagnosis_89 import accepted, corrupted, packages
from src.audit.sharding_check import diagnose_with_sharding

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_b5_qwen_design_a'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
CAP = 1.0


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = json.loads(B.CASES.read_text())
    acc = accepted()
    pk = {m: packages(m) for m in {c['key'].split('/')[1] for c in cases}}
    qfc = B.qwen_facts_carriers()
    have = ({r['key']: r for r in json.loads(RESULTS.read_text())['items']}
            if RESULTS.exists() else {})
    ledger = B.Ledger(CALLS, CAP)
    print(json.dumps({'todo': len([c for c in cases if c['key'] not in have]),
                      'spent': round(ledger.spent, 6)}), flush=True)
    for c in cases:
        if c['key'] in have:
            continue
        model, inst = c['key'].split('/')[1], c['key'].split('/')[2]
        t = corrupted(c, acc) if c['population'] == 'injected' else pk[model][inst]
        qf = qfc[c['key']]
        try:
            res = B.carrier_step(ledger, 'qa/' + c['key'], B.adapt(t), qf['facts'], B.QWEN)
        except RuntimeError as exc:
            print(json.dumps({'stopped': str(exc), 'spent': round(ledger.spent, 6)}))
            RESULTS.write_text(json.dumps({'items': list(have.values())}, indent=1))
            return
        if res.get('status') != 'ok':
            rec = {'key': c['key'], 'population': c['population'],
                   'known_stage': c['known_stage'], 'status': 'carrier_failed'}
        else:
            new, _ = diagnose_with_sharding(qf['facts'], res['value'], t, correct=False)
            rec = {'key': c['key'], 'population': c['population'], 'known_stage': c['known_stage'],
                   'status': 'ok', 'stage': B.stage_of(new), 'label': new}
        have[c['key']] = rec
        RESULTS.write_text(json.dumps({'items': list(have.values())}, indent=1))
        print(json.dumps({'key': c['key'], 'stage': rec.get('stage'), 'spent': round(ledger.spent, 6)}),
              flush=True)
    print(json.dumps({'spent': round(ledger.spent, 6), 'done': len(have)}))
    # the two Gemini carrier_failed cases, one retry each
    for key in ('inj/gpt4omini/4hop1__93963_170667_443779_52195',
                'inj/gemma31b/4hop1__151903_5274_458768_33677'):
        c = next(x for x in cases if x['key'] == key)
        model, inst = key.split('/')[1], key.split('/')[2]
        t = corrupted(c, acc)
        qf = qfc[key]
        try:
            res = B.carrier_step(ledger, 'gretry/' + key, B.adapt(t), qf['facts'], B.GEMINI)
            print(json.dumps({'gemini_retry': key, 'status': res.get('status'),
                              'spent': round(ledger.spent, 6)}), flush=True)
            with (OUT / 'gemini_retries.jsonl').open('a') as f:
                f.write(json.dumps({'key': key, 'status': res.get('status')}) + '\n')
        except RuntimeError as exc:
            print(json.dumps({'stopped': str(exc), 'spent': round(ledger.spent, 6)}))
            return


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    if ap.parse_args().run:
        run()