"""A2 scoring (step 39): judge alone (stored outputs) vs judge + audit evidence, on the 82 and 51 runs.

Rule: rebuttal/pilots/prereg/Stage-naming-A2-judge-with-audit-v1.md. Reads stored outputs; no calls.
Output: rebuttal/pilots/20261116_stage_naming/a2_score.json
"""
import json
import math
from collections import Counter
from pathlib import Path
from math import comb

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / 'rebuttal/pilots'
OUT = P / '20261116_stage_naming'
DELETED_DROP = {'2hop__826864_17335', '2hop__434218_29898', '2hop__189094_612080',
                '2hop__301587_233146', '3hop2__88342_93066_90766', '3hop1__163654_503371_21711'}


def wilson(k, n, z=1.959964):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def stored_judges():
    """(key, backbone) -> judge stage, from the stored outputs for the 82 runs."""
    out = {}
    for it in json.loads((P / '20261115_b5_attribution_2x2/judge_qwen.json').read_text())['items']:
        out[(it['key'], 'qwen')] = it.get('stage')
    for it in json.loads((P / '20261113_attribution_comparison/results_v2.json').read_text())['items']:
        if it.get('key', '').startswith('inj/') and 'judge' in it:
            out[(it['key'], 'gemini')] = it['judge'].get('stage')
    res = json.loads((P / '20261115_injection_amendA3/results.json').read_text())
    for c in res['cases']:
        if c.get('kept') in (True, 'True') and c['instance'] not in DELETED_DROP:
            m = c['methods'] if isinstance(c['methods'], dict) else __import__('ast').literal_eval(c['methods'])
            key = f"case/{c['type']}/{c['model']}/{c['instance']}"
            out[(key, 'qwen')] = m.get('judge_qwen')
            out[(key, 'gemini')] = m.get('judge_gemini')
    return out


def main():
    rows = json.loads((OUT / 'fact_tables.json').read_text())
    known = {}
    for r in rows:
        known[r['key']] = r['known_stage']
    # all 82 runs: every case (41) with both backbones, whether or not its fact matched
    runs82 = sorted((key, bb) for key in known for bb in ('qwen', 'gemini'))
    judges = stored_judges()
    matched = {(r['key'], r['backbone']) for r in rows if 'backbone' in r and 'excluded' not in r}
    a2 = {}
    p = OUT / 'a2_results.jsonl'
    if p.exists():
        for l in p.read_text().splitlines():
            if l.strip():
                e = json.loads(l)
                a2[(e['key'], e['backbone'])] = e['judge_with_audit']

    def correct(key, bb, src):
        st = src.get((key, bb))
        return st == known[key]

    out = {'runs_82': len(runs82), 'runs_51_matched': len(matched)}
    for label, sel in (('82', runs82), ('51', sorted(matched))):
        k = sum(correct(key, bb, judges) for key, bb in sel)
        out[f'judge_alone_{label}'] = {'k': k, 'n': len(sel), 'rate': round(k / len(sel), 3), 'wilson95': wilson(k, len(sel))}
        for bb in ('qwen', 'gemini'):
            s2 = [(key, b) for key, b in sel if b == bb]
            kk = sum(correct(key, b, judges) for key, b in s2)
            out[f'judge_alone_{label}_{bb}'] = {'k': kk, 'n': len(s2), 'rate': round(kk / len(s2), 3), 'wilson95': wilson(kk, len(s2))}
    done = [(key, bb) for key, bb in sorted(matched) if (key, bb) in a2]
    if done:
        k_alone = sum(correct(key, bb, judges) for key, bb in done)
        k_aud = sum(1 for key, bb in done if a2[(key, bb)] == known[key])
        b = sum(1 for key, bb in done if correct(key, bb, judges) and a2[(key, bb)] != known[key])
        c = sum(1 for key, bb in done if (not correct(key, bb, judges)) and a2[(key, bb)] == known[key])
        out['judge_with_audit'] = {'n': len(done), 'alone_correct': k_alone, 'with_audit_correct': k_aud,
                                   'with_audit_rate': round(k_aud / len(done), 3), 'wilson95': wilson(k_aud, len(done)),
                                   'alone_only_correct': b, 'audit_only_correct': c,
                                   'mcnemar_exact_p': mcnemar(c, b)}
    out['cost_note'] = 'see a2_calls.jsonl (per-call cost); pilot and full run logged there'
    (OUT / 'a2_score.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
