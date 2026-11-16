"""E2-A stage-1 gate: judge vs author on the 12 wave-1 spot-check items.

Reads the frozen judge outputs and the authors' returned spot-check labels. Reports counts with exact
Clopper-Pearson 95% CIs for `defect_free` agreement and for the target-fact checks on the nine
evidence-type items, plus Cohen kappa with its prevalence. The gate is E2-A-v5: more than 2 of 12
disagreements on `defect_free` stops scaling.

Also checks drift: every call succeeded, every response's resolved model is the frozen judge, and the
ledger holds 12 results under one config hash.

Run: python -m scripts.analyze_e2_stage1_gate
"""
import json, math
from pathlib import Path

OUT = Path('rebuttal/results/batch1/E2_stage1_judge')
RET = Path('rebuttal/annotation/returns')
MANIFEST = Path('rebuttal/pilots/20261108_review8/e2_spotcheck_wave1_manifest.json')
CFG = Path('rebuttal/pilots/configs/E2-stage1-judge-frozen.json')
TOL = 2


# ---- exact statistics (no scipy in the env) ----
def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 300, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    if abs(d) < FPMIN: d = FPMIN
    d = 1 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        if abs(d) < FPMIN: d = FPMIN
        c = 1 + aa / c
        if abs(c) < FPMIN: c = FPMIN
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        if abs(d) < FPMIN: d = FPMIN
        c = 1 + aa / c
        if abs(c) < FPMIN: c = FPMIN
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1) < EPS: break
    return h


def _betai(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                  + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1 - bt * _betacf(b, a, 1 - x) / b


def _beta_ppf(p, a, b):
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _betai(a, b, mid) < p: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def cp(k, n):
    """Exact Clopper-Pearson 95% interval for k successes in n trials."""
    lo = 0.0 if k == 0 else _beta_ppf(0.025, k, n - k + 1)
    hi = 1.0 if k == n else _beta_ppf(0.975, k + 1, n - k)
    return [round(lo, 4), round(hi, 4)]


def kappa(a, b):
    """Cohen kappa for two binary label lists; None when the marginals are degenerate."""
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa = sum(a) / n; pb = sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe == 1: return None
    return round((po - pe) / (1 - pe), 4)


def norm(v):
    return str(v).strip().lower()


def load_author():
    rows = {}
    for f in sorted(RET.glob('E2spotcheck1_*_labelling-v1.0.json')):
        for r in json.loads(f.read_text()):
            rows[r['item_id']] = r
    assert len(rows) == 12, len(rows)
    return rows


def main():
    cfg = json.loads(CFG.read_text())
    man = json.loads(MANIFEST.read_text())
    authors = load_author()
    out = {}
    for f in sorted((OUT / 'outputs').glob('*.json')):
        d = json.loads(f.read_text())
        out[d['packet_item_id']] = d
    assert len(out) == 12, len(out)

    rows = []
    for item in sorted(man['wave1_items'], key=lambda x: x['position']):
        # packet_item_id is recovered from the runner output, joined back by position
        d = next(v for v in out.values() if v['position'] == item['position'])
        a = authors[d['packet_item_id']]
        j = d.get('parsed') or {}
        a_df = a['answers'].get('defect_free')
        j_df = j.get('defect_free')
        row = {'position': item['position'], 'fault_type': item['fault_type'],
               'author': item['author'], 'target_agent': item['target_agent'],
               'judge_status': d['status'], 'judge_defect_free': j_df, 'author_defect_free': a_df,
               'agree_defect_free': (norm(j_df) == norm(a_df)) if j_df is not None else None}
        if item['fault_type'] != 'aggregation':
            tc = next((t for t in (j.get('target_checks') or [])
                       if t.get('agent_id') == item['target_agent']), None)
            if tc:
                vals = [norm(tc.get('in_every_sufficient_set')) == norm(a['answers'].get('fact_in_every_sufficient_set')),
                        norm(tc.get('carrier_outside_agent')) != norm(a['answers'].get('no_carrier_outside_target_agent')),
                        (item['fault_type'] in (tc.get('feasible_fault_types') or [])) == (norm(a['answers'].get('feasible_for_this_fault_type')) == 'yes')]
                row['target_check_agreement'] = vals
                row['target_checks_agree'] = all(vals)
        rows.append(row)

    n = len([r for r in rows if r['agree_defect_free'] is not None])
    k = sum(1 for r in rows if r['agree_defect_free'])
    disagreements = [r for r in rows if r['agree_defect_free'] is False]
    jb = [1 if norm(r['judge_defect_free']) == 'yes' else 0 for r in rows]
    ab = [1 if norm(r['author_defect_free']) == 'yes' else 0 for r in rows]
    trows = [r for r in rows if 'target_checks_agree' in r]
    tk = sum(1 for r in trows if r['target_checks_agree'])
    gate = {'n': n, 'agree': k, 'disagree': n - k, 'disagreements': disagreements,
            'agreement_proportion': round(k / n, 4), 'cp95': cp(k, n),
            'judge_yes': sum(jb), 'author_yes': sum(ab), 'kappa': kappa(jb, ab),
            'target_checks': {'n_evidence_items': 9, 'n_compared': len(trows), 'unavailable': 9 - len(trows),
                      'agree': tk, 'cp95': cp(tk, len(trows))},
            'rule': 'more than 2 of 12 disagreements stops scaling',
            'passed': (n - k) <= TOL}

    # Judge-quality measures pre-registered in Judge-labelling-v5, wave 1.
    def tc_pass(tc, ft):
        return (norm(tc.get('in_every_sufficient_set')) == 'yes'
                and norm(tc.get('carrier_outside_agent')) == 'no'
                and ft in (tc.get('feasible_fault_types') or []))
    q = {'eligible_field_disagrees_with_rule': 0, 'self_contradictions': 0, 'n': len(rows)}
    for r in rows:
        d = next(v for v in out.values() if v['position'] == r['position'])
        j = d.get('parsed') or {}
        checks = j.get('target_checks') or []
        rule = norm(j.get('defect_free')) == 'yes' and bool(checks) and all(
            tc_pass(t, r['fault_type']) for t in checks)
        if (norm(j.get('eligible')) == 'yes') != rule:
            q['eligible_field_disagrees_with_rule'] += 1
        if norm(j.get('eligible')) == 'yes' and norm(j.get('defect_free')) != 'yes':
            q['self_contradictions'] += 1
        if norm(j.get('defect_free')) == 'yes' and norm(j.get('any_partial_or_distorted_carrier')) == 'yes':
            q['self_contradictions'] += 1

    calls = [json.loads(l) for l in (OUT / 'calls.jsonl').read_text().splitlines() if l.strip()]
    res = [c for c in calls if c['event'] == 'result']
    drift = {'results': len(res), 'failed_calls': sum(not r['success'] for r in res),
             'resolved_models': sorted({r.get('resolved_model') for r in res if r.get('resolved_model')}),
             'config_hashes': sorted({r['config_sha256'] for r in res}),
             'prereg_hashes': sorted({r['prereg_sha256'] for r in res}),
             'unexpected_model': any(r.get('resolved_model') != cfg['model'] for r in res)}
    drift['clean'] = (drift['results'] == 12 and drift['failed_calls'] == 0
                      and drift['resolved_models'] == [cfg['model']]
                      and len(drift['config_hashes']) == 1 and not drift['unexpected_model'])

    payload = {'gate': gate, 'judge_quality': q, 'rows': rows, 'drift': drift,
               'judge_config_sha256': json.loads((OUT / 'run_identity.json').read_text()),
               'prereg': cfg['prereg'], 'prereg_sha256': cfg['prereg_sha256']}
    (OUT / 'gate.json').write_text(json.dumps(payload, indent=1) + '\n')

    lines = ['# E2-A stage-1 gate (12 wave-1 spot-check items)', '',
             f"Judge: `{cfg['model']}`, frozen prompt `{cfg['task']}`, one call per item, "
             f"frozen {cfg['frozen_utc']}. Author: one label per item by the assigned author.",
             '', '| Pos | Fault type | Author | Judge defect_free | Author defect_free | Agree |',
             '|---:|---|---|---|---|---|']
    lines += [f"| {r['position']} | {r['fault_type']} | {r['author']} | {r['judge_defect_free']} | "
              f"{r['author_defect_free']} | {'yes' if r['agree_defect_free'] else 'no'} |" for r in rows]
    lines += ['', f"**defect_free agreement:** {k}/{n} = {gate['agreement_proportion']:.3f}, "
                  f"exact 95% CI {gate['cp95']}; Cohen kappa {gate['kappa']} "
                  f"(judge yes {gate['judge_yes']}, author yes {gate['author_yes']}).",
              f"**Target-fact checks:** the 9 evidence-type items had a target check for the manifest's target agent "
              f"in {len(trows)} of 9 ({9 - len(trows)} unavailable: the judge returned no check for that agent); "
              f"{tk}/{len(trows)} of those agree, exact 95% CI {cp(tk, len(trows))}.",
              f"**Gate:** {n - k} disagreements; the rule stops at more than {TOL}. "
              f"Result: **{'PASS — wave 1 may scale' if gate['passed'] else 'STOP — do not scale'}**.",
              '', f"**Judge quality (wave 1):** eligible field disagrees with the derived rule in "
              f"{q['eligible_field_disagrees_with_rule']} of {q['n']}; self-contradictions "
              f"{q['self_contradictions']} of {q['n']}.",
              f"**Drift:** {drift['results']} results, {drift['failed_calls']} failed, "
              f"resolved models {drift['resolved_models']}, one config hash; clean = {drift['clean']}."]
    if disagreements:
        lines += ['', 'Disagreements:']
        for r in disagreements:
            lines.append(f"- pos {r['position']} ({r['fault_type']}, author {r['author']}): "
                         f"judge `{r['judge_defect_free']}`, author `{r['author_defect_free']}`")
    (OUT / 'gate.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(gate, indent=1))
    print(json.dumps(drift, indent=1))


if __name__ == '__main__':
    main()