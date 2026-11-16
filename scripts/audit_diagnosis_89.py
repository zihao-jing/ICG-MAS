"""Measured audit diagnosis on the 89 known-stage attribution cases.

Rule: `rebuttal/pilots/20261113_audit_diagnosis_89/AUDIT_DIAGNOSIS_RULE.md`,
frozen before any call. Cohort (59) reuses frozen matcher records, zero calls;
injected (30) run the audit's own matcher on the corrupted trace, cap $0.50.

    ./run.sh python -m scripts.audit_diagnosis_89 --build
    ./run.sh python -m scripts.audit_diagnosis_89 --run
    ./run.sh python -m scripts.audit_diagnosis_89 --report
"""
import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.missing_fact_repair_pilot import cp_ci
from scripts.run_e1_anchor_matcher import adapt
from scripts.run_expansion_stage2 import MATCHER_DIR, MODELS, packages
from src.audit.matcher_v2 import PROMPT_SHA256, VERSION, match_trace
from src.audit.pilot_common import CallLedger, digest, freeze
from src.audit.sharding_check import diagnose_with_sharding

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_audit_diagnosis_89'
CASES = ROOT / 'rebuttal/pilots/20261113_attribution_comparison/cases_v2.json'
SRC = ROOT / 'rebuttal/pilots/20261113_injected_distortion'
PRICING = ROOT / 'rebuttal/pilots/20261108_preflight/pricing.json'
RULE = OUT / 'AUDIT_DIAGNOSIS_RULE.md'
BUILD = OUT / 'build_manifest.json'
LEDGER = OUT / 'matcher_run'
RESULTS = OUT / 'audit_results.json'
REPORT = OUT / 'report.md'
MATCHER_MODEL = 'qwen/qwen3-235b-a22b-2507'
CAP = 0.50
MAX_CALLS = 200
STAGES = ('sharding', 'extraction', 'transmission', 'aggregation')
MAP = {
    'extraction_omission': 'extraction',
    'sharding_omission': 'sharding',
    'mixed_sharding_extraction': 'sharding',
    'selection_omission': 'transmission',
    'partial': 'transmission',
    'distortion': 'transmission',
    'candidate_aggregation': 'aggregation',
    'correct_control': None,
    'uncertain': None,
}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def records():
    out = {}
    for p in MATCHER_DIR.glob('*.json'):
        d = json.loads(p.read_text())
        out[(d['model'], d['instance_id'])] = d
    return out


def accepted():
    rows = json.loads((SRC / 'accepted.json').read_text())['accepted']
    return {(a['model'], a['instance_id']): a for a in rows}


def corrupted(case, acc):
    """Frozen package with the accepted unit's text replaced on board and transmission."""
    model, inst = case['key'].split('/')[1], case['key'].split('/')[2]
    t = copy.deepcopy(packages(model)[inst])
    bid = acc[(model, inst)]['unit_id']
    tid = bid.replace('board:', 'transmission:', 1)
    for u in t['checkpoints']['board']:
        if u['unit_id'] == bid:
            u['text'] = acc[(model, inst)]['corrupt']
    for u in t['checkpoints']['transmission']:
        if u['unit_id'] == tid:
            u['text'] = acc[(model, inst)]['corrupt']
    return t


def build():
    cases = json.loads(CASES.read_text())
    assert len(cases) == 89
    assert sum(c['population'] == 'injected' for c in cases) == 30
    acc = accepted()
    for c in cases:
        if c['population'] == 'injected':
            model, inst = c['key'].split('/')[1], c['key'].split('/')[2]
            assert (model, inst) in acc, c['key']
    recs = records()
    for c in cases:
        if c['population'] == 'cohort':
            model, inst = c['key'].split('/')[1], c['key'].split('/')[2]
            r = recs[(model, inst)]
            assert r.get('status') == 'ok', c['key']
    cfg = {'experiment': 'audit diagnosis on the 89 known-stage cases',
           'model': MATCHER_MODEL, 'temperature': 0, 'max_tokens': 4096,
           'max_calls': MAX_CALLS, 'pricing': str(PRICING),
           'prompt_sha256': PROMPT_SHA256, 'version': VERSION,
           'cases_sha256': file_sha(CASES)}
    freeze(OUT / 'matcher_config.json', cfg)
    freeze(BUILD, {
        'recorded_before_first_matcher_call': True,
        'rule_sha256': file_sha(RULE),
        'cases_sha256': file_sha(CASES),
        'accepted_sha256': file_sha(SRC / 'accepted.json'),
        'matcher_prompt_version': VERSION,
        'matcher_prompt_sha256': PROMPT_SHA256,
        'matcher_model': MATCHER_MODEL,
        'matcher_config_sha256': digest(cfg),
        'stage_mapping': MAP, 'cap_usd': CAP, 'max_calls': MAX_CALLS,
        'cohort_source': 'rebuttal/results/batch1/expansion_stage2/matcher',
        'injected_run': 'audit matcher on corrupted board + transmission'})
    print(json.dumps({'cases': len(cases), 'cap_usd': CAP,
                      'prompt_sha256': PROMPT_SHA256[:12]}, indent=1))


def ledger_cost():
    p = LEDGER / 'calls.jsonl'
    if not p.exists():
        return 0.0
    return sum((r.get('cost_usd') or 0.0)
               for r in map(json.loads, p.read_text().splitlines())
               if r.get('event') == 'result')


def run(limit=None):
    man = json.loads(BUILD.read_text())
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(CASES) == man['cases_sha256']
    cases = json.loads(CASES.read_text())
    recs = records()
    acc = accepted()
    pk = {m: packages(m) for m in MODELS}
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in
                json.loads(RESULTS.read_text())['items']}
    # cohort: zero-call audit diagnosis on frozen matcher records
    for c in cases:
        if c['population'] != 'cohort' or c['key'] in done:
            continue
        model, inst = c['key'].split('/')[1], c['key'].split('/')[2]
        r = recs[(model, inst)]
        new, detail = diagnose_with_sharding(
            r['facts'], r['carriers'], pk[model][inst], correct=False)
        done[c['key']] = {'key': c['key'], 'population': 'cohort',
                          'known_stage': c['known_stage'],
                          'audit_label': new,
                          'audit_stage': MAP.get(new),
                          'audit_old': detail['old'],
                          'facts': detail.get('facts', {}),
                          'status': 'ok', 'calls': 0}
        RESULTS.write_text(json.dumps({'items': list(done.values())},
                                      indent=1, ensure_ascii=False))
    print(json.dumps({'cohort_done': sum(1 for r in done.values()
                                        if r['population'] == 'cohort')}))
    # injected: audit matcher on the corrupted trace
    todo = [c for c in cases if c['population'] == 'injected'
            and c['key'] not in done]
    if limit:
        todo = todo[:limit]
    if todo:
        cfg = json.loads((OUT / 'matcher_config.json').read_text())
        ledger = CallLedger(LEDGER, cfg, RULE, MAX_CALLS)
        try:
            for c in todo:
                if ledger_cost() > CAP:
                    print(json.dumps({'stopped': 'cap',
                                      'spent_usd': round(ledger_cost(), 6)}))
                    break
                model, inst = c['key'].split('/')[1], c['key'].split('/')[2]
                t = corrupted(c, acc)
                key = 'audit-inj/' + model + '/' + inst
                try:
                    res = match_trace(ledger, key, adapt(t), MATCHER_MODEL)
                    if res.get('status') != 'ok':
                        done[c['key']] = {
                            'key': c['key'], 'population': 'injected',
                            'known_stage': c['known_stage'],
                            'audit_label': None, 'audit_stage': None,
                            'status': 'matcher_failed', 'calls': 2,
                            'error': res.get('failure_stage')}
                    else:
                        new, detail = diagnose_with_sharding(
                            res['facts'], res['carriers'], t, correct=False)
                        done[c['key']] = {
                            'key': c['key'], 'population': 'injected',
                            'known_stage': c['known_stage'],
                            'audit_label': new,
                            'audit_stage': MAP.get(new),
                            'audit_old': detail['old'],
                            'facts': detail.get('facts', {}),
                            'status': 'ok', 'calls': 2,
                            'retried': bool(res.get('carrier_call', {})
                                            .get('retried'))}
                except Exception as exc:
                    done[c['key']] = {
                        'key': c['key'], 'population': 'injected',
                        'known_stage': c['known_stage'],
                        'audit_label': None, 'audit_stage': None,
                        'status': 'error', 'calls': 0,
                        'error': type(exc).__name__ + ': ' + str(exc)}
                RESULTS.write_text(json.dumps({'items': list(done.values())},
                                              indent=1, ensure_ascii=False))
                print(json.dumps({'done': len(done), 'of': 89,
                                  'spent_usd': round(ledger_cost(), 6)}),
                      flush=True)
        finally:
            ledger.close()
    print(json.dumps({'items': len(done), 'spent_usd': round(ledger_cost(), 8)},
                     indent=1))


def report():
    items = json.loads(RESULTS.read_text())['items']
    scored = [r for r in items if r.get('audit_stage')]
    lines = ['# Audit\'s own diagnosis measured on the 89 known-stage cases\n',
             f"Rule `AUDIT_DIAGNOSIS_RULE.md` (sha256 `{file_sha(RULE)[:12]}`), "
             f"matcher `matcher_config.json` (Qwen-235B, `{VERSION}`, prompt "
             f"`{PROMPT_SHA256[:12]}`), cases `cases_v2.json`. Cohort (59): "
             f"frozen Stage-2 matcher record + `diagnose_with_sharding`, zero "
             f"calls. Injected (30): audit matcher rerun on the corrupted board; "
             f"spend **${ledger_cost():.6f}**, cap $0.50.\n"]
    by = {}
    for r in items:
        by.setdefault(r['population'], []).append(r)
    lines += ['| population | known stage | n | audit correct | accuracy [95% CI] | excluded |',
              '| --- | --- | ---: | ---: | --- | ---: |']
    for pop, label in (('injected', 'transmission'),
                       ('cohort', 'extraction/sharding')):
        rs = by.get(pop, [])
        ok = [r for r in rs if r['audit_stage']]
        k = sum(r['audit_stage'] == r['known_stage'] for r in ok)
        n = len(ok)
        lo, hi = cp_ci(k, n) if n else (0, 0)
        lines.append(f"| {pop} | {label} | {len(rs)} | {k} | {k}/{n} = "
                     f"{k / n:.3f} [{lo:.3f}, {hi:.3f}] | {len(rs) - n} |")
    k = sum(r['audit_stage'] == r['known_stage'] for r in scored)
    n = len(scored)
    lo, hi = cp_ci(k, n) if n else (0, 0)
    lines += ['', f"**Overall audit stage accuracy {k}/{n} = {k / n:.3f} "
              f"[{lo:.3f}, {hi:.3f}]** (excluded {len(items) - n}).\n",
              '| known \\ audit | sharding | extraction | transmission | aggregation | excluded |',
              '| --- | ---: | ---: | ---: | ---: | ---: |']
    for ks in ('sharding', 'extraction', 'transmission'):
        cells = [sum(1 for r in items if r['known_stage'] == ks
                     and r['audit_stage'] == js) for js in STAGES]
        exc = sum(1 for r in items if r['known_stage'] == ks
                  and not r['audit_stage'])
        lines.append(f"| {ks} | {cells[0]} | {cells[1]} | {cells[2]} | "
                     f"{cells[3]} | {exc} |")
    lines += ['', '## Audit labels behind the stage mapping\n',
              '| audit label | label count | mapped stage |',
              '| --- | ---: | --- |']
    for lab, cnt in sorted(Counter(r['audit_label']
                                   for r in items if r['audit_label']).items()):
        lines.append(f"| `{lab}` | {cnt} | {MAP.get(lab) or 'excluded'} |")
    lines += ['', '## Errors\n',
              'Injected errors (4): two cases the audit labels '
              '`candidate_aggregation` (the corrupted unit is not on the '
              'chosen support path, or an alternative faithful carrier '
              'remains), and two cases it labels `extraction_omission` (a '
              'different fact in the chosen support set is missing from the '
              'extraction pool, so the corrupted board unit is not the '
              'diagnosed fault). The audit sees only the corrupted trace; the '
              'truth is transmission by construction.\n',
              'Cohort errors (15 of 20 sharding-truth cases): the audit labels '
              'them `extraction_omission` because its input-presence check '
              'uses the automatic 0.8/0.4 content-recall rule. Fourteen of '
              'the 15 are cases where the frozen cohort label is a **manual '
              'adjudication** over that automatic rule (a sentence credits '
              'the fact at >=0.8 recall but does not state the relation); the '
              'audit has no access to those adjudications. The remaining case '
              '(`2hop__342746_679190`) is automatic. This is why the cohort '
              'row is a consistency check, not independent accuracy.\n',
              '', 'Cohort note: the audit\'s input-presence check and the cohort '
              'truth share the same 0.8/0.4 content-recall rule, so the cohort '
              'row is a consistency check against a shared rule, not an '
              'independent accuracy estimate. The injected row is independent: '
              'the truth is set by construction and the audit sees only the '
              'corrupted trace. Errors are listed per case in '
              '`audit_results.json` (`audit_label`, `facts`).\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'scored': n, 'correct': k,
                      'spent_usd': round(ledger_cost(), 8)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=None)
    for f in ('build', 'run', 'report'):
        ap.add_argument('--' + f, action='store_true', dest=f)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.build:
        build()
    if a.run:
        run(a.limit)
    if a.report:
        report()


if __name__ == '__main__':
    main()