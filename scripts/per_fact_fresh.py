"""Fresh carrier-label validation set for the per-fact labeller.

Rule: `rebuttal/pilots/20261113_per_fact_labeller/PER_FACT_RULE_V4.md`, frozen
before any call. The set is author-labelled traces not used in tuning, the
carrier-target rescoring, or the 5-instance reserve: four unused E1 anchor
instances (24 board comparisons) and the 20 E1 dev runs (40 board
comparisons). Author citations are audited against the board text under the
written correction rubric before the labeller is called; the original author
labels are kept beside the corrected ones.

    ./run.sh python -m scripts.per_fact_fresh --build
    ./run.sh python -m scripts.per_fact_fresh --run --cap-usd 5
    ./run.sh python -m scripts.per_fact_fresh --report
"""
import argparse
import glob
import hashlib
import json
from pathlib import Path

from scripts.coverage_validation import author_complete, load_returns
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.per_fact_labeller import (
    MAX_TOKENS, RESULTS as _OLD_RESULTS, call, file_sha, parse, render, sha,
    spent as old_spent,
)
from scripts.run_e1_anchor_matcher import anchor_ids
from src.audit.pilot_common import blind_view, digest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_per_fact_labeller'
RULE = OUT / 'PER_FACT_RULE_V4.md'
POP = OUT / 'population_fresh.json'
MANIFEST = OUT / 'fresh_manifest.json'
CALLS = OUT / 'calls_fresh.jsonl'
RESULTS = OUT / 'results_fresh.json'
CORRECTED = OUT / 'corrected_labels.json'
REPORT = OUT / 'fresh_report.md'
DEV = ROOT / 'rebuttal/annotation/labelling_20261108/returns/E1dev_*.json'
UNUSED = ('I-02_n5', 'II-13_n10', 'III-24_n5', 'III-27_n5')
CAP = 5.0


def str_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def row_from_trace(trace, model, source, annots, stratum):
    out = []
    for a, x in sorted(annots.items()):
        facts = json.loads(x['answers']['critical_facts_json'])
        if not isinstance(facts[0], dict):
            facts = [{'fact_id': f'f{i + 1}', 'text': t}
                     for i, t in enumerate(facts)]
        cars = json.loads(x['answers']['carriers_json'])
        board = [c for c in cars if c.get('checkpoint') == 'board']
        fid = {c['fact_id'] for c in board}
        units = {}
        for c in board:
            units.setdefault(c['fact_id'], set()).update(c.get('unit_ids') or [])
        out.append({'split': 'fresh', 'source': source, 'instance_id':
                    trace['instance_id'], 'model': model, 'stratum': stratum,
                    'checkpoint': 'board', 'checkpoint_name': 'shared board',
                    'annotator': a, 'author_complete': author_complete(x),
                    'question': trace['question'],
                    'facts': [{'fact_id': f['fact_id'], 'text': f['text']}
                              for f in facts],
                    'author_fidelity':
                        {c['fact_id']: c.get('fidelity') or 'absent'
                         for c in board if c['fact_id'] in fid},
                    'author_units': {f: sorted(v) for f, v in units.items()},
                    'entries': [{'unit_id': u['unit_id'],
                                 'agent_id': u['agent_id'],
                                 'text': u['text']}
                                for u in trace['checkpoints']['board']]})
    return out


def build():
    from scripts.build_final_author_packet import packages
    strata = {i: h for h, v in json.loads(
        (ROOT / 'rebuttal/pilots/20261108_review7/e1_anchor_locked_manifest.json')
        .read_text())['strata'].items() for i in v['ids']}
    pk = packages(set(UNUSED))
    ret = load_returns()
    rows = []
    for (m, inst), t in sorted(pk.items()):
        anns = ret.get(digest(blind_view(t))) or {}
        if len(anns) != 2:
            continue
        rows += row_from_trace(t, m, 'anchor', anns,
                               strata.get(inst) or 'anchor')
    dev = [r for p in sorted(glob.glob(str(DEV)))
           for r in json.load(open(p))]
    by = {}
    for r in dev:
        by.setdefault(r['item_id'], {})[r['annotator_id']] = r
    for item in sorted(by):
        anns = by[item]
        trace = next(iter(anns.values()))['trace']
        rows += row_from_trace(trace, 'dev', 'dev', anns, 'E1dev')
    OUT.mkdir(parents=True, exist_ok=True)
    POP.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True, 'rule_sha256': file_sha(RULE),
        'population_sha256': file_sha(POP), 'n': len(rows),
        'instances': len({(r['source'], r['instance_id']) for r in rows}),
        'cap_usd': CAP, 'prompt': 'v3 (unchanged)'}, indent=1))
    print(json.dumps({'n': len(rows),
                      'by_source': {s: sum(r['source'] == s for r in rows)
                                    for s in ('anchor', 'dev')},
                      'by_annotator': {a: sum(r['annotator'] == a
                                              for r in rows)
                                       for a in 'ABCD'}}, indent=1))


def check():
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(POP) == man['population_sha256'], 'population changed'
    return json.loads(POP.read_text())


def run(cap):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(POP) == man['population_sha256'], 'population changed'
    spec = json.loads((OUT / 'per_fact_prompt_v3.json').read_text())
    rows = json.loads(POP.read_text())
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in json.loads(RESULTS.read_text())['items']}
    out = list(done.values())
    total = sum(json.loads(l).get('cost_usd', 0.0)
                for l in CALLS.read_text().splitlines()
                if l.strip() and json.loads(l).get('event') == 'result') \
        if CALLS.exists() else 0.0
    for r in rows:
        key = (f"fresh/v3/{r['source']}/{r['model']}/{r['instance_id']}/"
               f"{r['annotator']}")
        if key in done:
            continue
        # calls are logged to calls_fresh.jsonl by a local copy of `call`
        resp, total = call_fresh(key, spec, render(r), cap, total)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        lab = parse(resp.content, {f['fact_id'] for f in r['facts']}) \
            if resp.success else None
        rec = {**{k: r[k] for k in ('source', 'instance_id', 'model',
                                    'stratum', 'checkpoint', 'annotator',
                                    'author_complete', 'author_fidelity',
                                    'facts')},
               'key': key, 'prompt_version': 'v3',
               'prompt_file_sha256': file_sha(OUT / 'per_fact_prompt_v3.json'),
               'prompt_system_sha256': str_sha(spec['system']),
               'success': resp.success, 'error': resp.error, 'labeller': lab}
        out.append(rec)
        RESULTS.write_text(json.dumps({'items': out}, indent=1,
                                      ensure_ascii=False))
        print(json.dumps({'key': key, 'valid': lab is not None,
                          'spent_usd': round(total, 6)}), flush=True)
    RESULTS.write_text(json.dumps({'items': out}, indent=1, ensure_ascii=False))
    print(json.dumps({'rows': len(rows), 'spent_usd': round(total, 8)},
                     indent=1))


def call_fresh(key, spec, user, cap, total):
    """Same call as per_fact_labeller.call, logging to calls_fresh.jsonl."""
    import math
    from scripts.pilot_llm_labeller import PRICE_IN, PRICE_OUT
    from utility.apis.base import APIRequest
    global CALLS
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    est = est_in * PRICE_IN + MAX_TOKENS * PRICE_OUT
    if total + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key,
                                'reason': 'cap', 'cost_usd': 0.0}) + '\n')
        return None, total
    call_id = str_sha('|'.join([key, spec['system'], user, str(MAX_TOKENS)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key,
                            'call_id': call_id, 'model': spec['model'],
                            'system_sha256': str_sha(spec['system']),
                            'user_sha256': str_sha(user),
                            'max_tokens': MAX_TOKENS, 'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=spec['system'], user_query=user,
                     model=spec['model'], max_tokens=MAX_TOKENS,
                     temperature=0,
                     metadata={'pilot': 'per_fact_fresh', 'key': key,
                               'openrouter_reasoning': False})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
            + usage.get('completion_tokens', 0) * PRICE_OUT)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key,
                            'call_id': call_id, 'model': spec['model'],
                            'success': resp.success, 'error': resp.error,
                            'content': resp.content, 'usage': usage,
                            'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def score():
    import random
    from scripts.coverage_validation import kappa_binary
    rows = json.loads(RESULTS.read_text())['items']
    corr = json.loads(CORRECTED.read_text())['labels']
    pop = {}
    for p in json.loads(POP.read_text()):
        pop[f"fresh/v3/{p['source']}/{p['model']}/{p['instance_id']}/"
            f"{p['annotator']}"] = p
    pairs, fact_n, fact_ok = [], 0, 0
    pairs_c, fact_nc, fact_okc = [], 0, 0
    detail = []
    for r in rows:
        if not r.get('labeller'):
            continue
        key = r['key']
        au = {f: set(v) for f, v in
              (corr.get(key) or {}).get('units', {}).items()}
        corrected_complete = bool((corr.get(key) or {}).get('complete'))
        ok = okc = True
        for fact in r['facts']:
            f = fact['fact_id']
            v = r['labeller'].get(f) or {'status': 'absent', 'unit_ids': []}
            au_c = au.get(f, set())
            hit = ((v['status'] == 'absent') if not au_c else
                   (v['status'] != 'absent'
                    and bool(set(v['unit_ids']) & au_c)))
            fact_nc += 1
            fact_okc += hit
            okc = okc and bool(au_c) and hit
            au0 = set((pop[key].get('author_units') or {}).get(f) or [])
            orighit = (pop[key]['author_fidelity'].get(f) == 'faithful'
                       and v['status'] != 'absent'
                       and bool(set(v['unit_ids']) & au0))
            fact_n += 1
            fact_ok += orighit
            ok = ok and orighit
        pairs.append((ok, bool(r['author_complete']), r['instance_id']))
        pairs_c.append((okc, corrected_complete, r['instance_id']))
        detail.append({'key': key, 'source': r['source'],
                       'instance_id': r['instance_id'], 'model': r['model'],
                       'annotator': r['annotator'], 'complete': ok,
                       'author_complete': bool(r['author_complete']),
                       'corrected_complete': corrected_complete,
                       'corrected_match': okc})

    def agg(pairs):
        n = len(pairs)
        k = sum(x == y for x, y in ((x, y) for x, y, _ in pairs))
        lo, hi = cp_ci(k, n)
        kap = kappa_binary([(x, y) for x, y, _ in pairs])
        by = {}
        for x, y, i in pairs:
            by.setdefault(i, []).append((x, y))
        keys = sorted(by)
        rng = random.Random(43)
        vals = []
        for _ in range(10000):
            draw = []
            for _ in keys:
                draw += by[keys[rng.randrange(len(keys))]]
            vals.append(kappa_binary(draw))
        vals = [v for v in vals if v == v]
        vals.sort()
        klo, khi = ((vals[int(.025 * len(vals))],
                     vals[int(.975 * len(vals)) - 1]) if vals
                    else (float('nan'), float('nan')))
        return {'n': n, 'k': k, 'agreement': k / n, 'lo': lo, 'hi': hi,
                'kappa': kap, 'klo': klo, 'khi': khi}
    a = agg(pairs)
    c = agg(pairs_c)
    return a, c, fact_n, fact_ok, fact_nc, fact_okc, detail


def report():
    man = json.loads(MANIFEST.read_text())
    assert file_sha(CORRECTED) == man.get('corrected_sha256'), \
        'corrected labels not frozen'
    a, c, fn, fok, fnc, fokc, detail = score()
    spend = sum(json.loads(l).get('cost_usd', 0.0)
                for l in CALLS.read_text().splitlines()
                if l.strip() and json.loads(l).get('event') == 'result') \
        if CALLS.exists() else 0.0
    verdict = ('PASS' if a['agreement'] >= 0.80 and a['kappa'] >= 0.60
               else 'FAIL')
    lines = ['# Per-fact carrier-target fresh check (original labels)\n',
             f"Rule `PER_FACT_RULE_V4.md` (sha256 `{file_sha(RULE)[:12]}`), "
             f"frozen before the calls. Validation is against the authors' "
             f"original labels. {a['n']} board comparisons "
             f"({sum(d['source'] == 'anchor' for d in detail)} anchor + "
             f"{sum(d['source'] == 'dev' for d in detail)} dev); spend "
             f"${spend:.6f}, cap ${CAP:.2f}.\n",
             '## Validation against the authors\' original labels\n',
             f"Agreement **{a['k']}/{a['n']} = {a['agreement']:.3f}** "
             f"(95% CI {a['lo']:.3f}-{a['hi']:.3f}); kappa **{a['kappa']:.3f}** "
             f"({a['klo']:.3f}-{a['khi']:.3f}) - **{verdict}** against "
             f'0.80/0.60. Per-fact **{fok}/{fn}**. The labeller stays '
             f'unvalidated even for carrier identification.\n',
             '## Post-hoc corrected-label audit (not a validation)\n',
             f"Against `corrected_labels.json` (sha256 "
             f"`{file_sha(CORRECTED)[:12]}`), audited after the calls: "
             f"agreement **{c['k']}/{c['n']} = {c['agreement']:.3f}** "
             f"(95% CI {c['lo']:.3f}-{c['hi']:.3f}); kappa "
             f"**{c['kappa']:.3f}** ({c['klo']:.3f}-{c['khi']:.3f}); per-fact "
             f"**{fokc}/{fnc}**. This is not a validation: the references were "
             f'corrected after the labeller output was seen, and 40 of the 64 '
             f'rows are E1 dev rows used in labeller development.\n',
             '| key | source | labeller | author | corrected |',
             '| --- | --- | --- | --- | --- |']
    for d in detail:
        lines.append(f"| {d['source']}/{d['model']}/{d['instance_id']}/"
                     f"{d['annotator']} | {d['source']} | "
                     f"{d['complete']} | {d['author_complete']} | "
                     f"{d['corrected_complete']} |")
    lines += ['', '## What this covers, and what it does not\n',
              'The target is carrier identification: whether the labeller '
              'returns the board units that state each critical fact. It is '
              'not semantic fidelity or coverage, and the main-table columns '
              'stay lexical or matcher. The 24 anchor rows were not used before; '
              'the 40 dev rows were used in labeller development, so this set '
              'cannot be a clean validation of the prompt.\n',
              'Composition: all 64 comparisons are Silo-Bench, not MuSiQue - '
              '24 from four unused synthetic E1 anchor instances (I-02, '
              'II-13, III-24, III-27) and 40 from the 20 E1 dev runs. The '
              'reserve failures that motivated the audit were MuSiQue. No '
              'unused MuSiQue author labels remain, so MuSiQue carrier '
              'identification stays unvalidated; the pass above covers '
              'Silo-Bench carrier identification only.\n',
              'The corrected labels are ours, audited from the board text '
              'under `PER_FACT_RULE_V4.md` and `author_citation_audit.md`; '
              'the authors\' original labels are reported beside them and stay '
              'on record. Because the audit was made after the fresh calls and '
              'on a candidate set the labeller also saw, a row where author '
              'and labeller are wrong in the same way is not corrected and '
              'counts as agreement. The audited label is read from the text, '
              'not copied from the labeller, but this is not an independent '
              'author re-annotation.']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'author': a, 'corrected': c, 'per_fact_author':
                      [fok, fn], 'per_fact_corrected': [fokc, fnc],
                      'verdict': verdict, 'spend_usd': spend}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    if a.build:
        build()
    if a.run:
        run(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()