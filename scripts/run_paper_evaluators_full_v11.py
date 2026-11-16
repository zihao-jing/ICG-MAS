"""Full paper-evaluator run under Paper-evaluators-v1.1 (lexical set widened; judge rows unchanged).

Same prompt, model, temperature, seed, max_tokens, mapping, collapse and call structure as v1.0; the
only differences are the pre-registration file, the fuller lexical scope (computed after the run by
`scripts/analyze_paper_evaluators.py`), the output directory and the call cap (852). One call per
judge-eligible row, no retry, failed calls logged and unscored.

  python -m scripts.run_paper_evaluators_full_v11 --execute
"""
import argparse, collections, json
from pathlib import Path

from src.audit.pilot_common import CallLedger, digest
from scripts.run_paper_evaluators import (SYSTEM, USER, LABELS, COLLAPSE, rows, utc, sha)

PREREG = Path('rebuttal/pilots/prereg/Paper-evaluators-v1.1.md')
CFG = Path('rebuttal/pilots/configs/Paper-evaluators-v1.1.json')
OUT = Path('rebuttal/results/batch1/Paper_evaluators_full_v11')
PROMPT_SHA = '66ef5e82296f77fef2d281b3f269eefa99dc7e3d91ca71e091796a6e669e24ef'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true')
    a = ap.parse_args()
    cfg = json.loads(CFG.read_text())
    assert cfg['prereg_sha256'] == sha(PREREG), 'pre-registration changed since it was frozen'
    assert cfg["prompt_sha256"] == digest([SYSTEM, USER]) == cfg['paper_prompt_sha256'] == PROMPT_SHA
    assert cfg['model'] == 'qwen/qwen3-235b-a22b-2507' and cfg['temperature'] == 0
    all_rows = rows()
    plan = [r for r in all_rows if r['unique_argmax']]
    assert len(plan) == cfg['expected_calls'], 'eligible row count changed since the config was frozen'
    print(json.dumps({'rows_all': len(all_rows), 'eligible': len(plan), 'selected': len(plan),
                      'checkpoints': dict(collections.Counter(r['checkpoint'] for r in plan)),
                      'author_fidelity': dict(collections.Counter(r['author_fidelity'] for r in plan)),
                      'lexical_covered': dict(collections.Counter(r['lexical_covered'] for r in plan)),
                      'execute': a.execute, 'start_utc': utc()}), flush=True)
    if not a.execute:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = CallLedger(OUT, cfg, PREREG, len(plan))
    assert not (ledger.done), 'output directory already has calls; use a fresh run'
    done = {'planned': len(plan), 'valid': 0, 'failed': 0, 'failed_reason': {},
            'model': cfg['model'], 'temperature': cfg['temperature'], 'max_tokens': cfg['max_tokens'],
            'pilot': False, 'start_utc': utc()}
    try:
        for i, r in enumerate(plan, 1):
            spent = sum((x.get('cost_usd') or 0) for x in ledger.done.values())
            if spent > cfg['cost_cap_usd']:
                raise RuntimeError('Cost cap reached')
            msgs = [{'role': 'system', 'content': SYSTEM},
                    {'role': 'user', 'content': USER.replace('{gold}', r['gold_text']).replace('{cand}', r['candidate_text'])}]
            try:
                raw = ledger.call(r['row_id'], cfg['model'], msgs, max_tokens=cfg['max_tokens'],
                                  temperature=0, response_format={'type': 'json_object'})
                label = json.loads(raw)['label'].strip().upper()
                if label not in LABELS:
                    raise ValueError('label not in the five')
                r['judge_label'] = label
                r['judge_presence'], r['judge_fidelity'] = COLLAPSE[label]
                r['judge_valid'] = True
                done['valid'] += 1
            except Exception as exc:
                r['judge_label'] = None
                r['judge_valid'] = False
                r['judge_error'] = type(exc).__name__ + ': ' + str(exc)
                done['failed'] += 1
                done['failed_reason'][type(exc).__name__] = done['failed_reason'].get(type(exc).__name__, 0) + 1
            print(f"{i}/{len(plan)} {'ok' if r['judge_valid'] else 'failed'} {r['judge_label']} "
                  f"{r['instance']} {r['checkpoint']} {utc()}", flush=True)
    finally:
        ledger.close()
    res = [json.loads(l) for l in (OUT / 'calls.jsonl').read_text().splitlines() if l.strip()]
    res = [x for x in res if x['event'] == 'result']
    done.update({'calls': len(res), 'calls_failed': sum(not x['success'] for x in res),
                 'cost_usd': round(sum(x.get('cost_usd') or 0 for x in res), 6), 'end_utc': utc(),
                 'runner_sha256': sha(__file__), 'config_sha256': digest(cfg),
                 'prereg_sha256': sha(PREREG)})
    (OUT / 'rows.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in plan))
    (OUT / 'summary.json').write_text(json.dumps(done, indent=2, default=str) + '\n')
    print(json.dumps({k: done[k] for k in ('planned', 'valid', 'failed', 'calls', 'calls_failed', 'cost_usd')}))


if __name__ == '__main__':
    main()