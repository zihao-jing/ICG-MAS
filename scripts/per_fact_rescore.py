"""Re-score the frozen per-fact labeller against the authors' carrier units.

Rule: `rebuttal/pilots/20261113_per_fact_labeller/PER_FACT_RULE_V2.md`, frozen
before this run. Zero model calls; reads logged v3 output and author returns.

    ./run.sh python -m scripts.per_fact_rescore
"""
import hashlib
import json
import random
from pathlib import Path

from scripts.build_final_author_packet import packages
from scripts.coverage_validation import kappa_binary, load_returns
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.run_e1_anchor_matcher import anchor_ids
from src.audit.pilot_common import blind_view, digest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_per_fact_labeller'
RULE = OUT / 'PER_FACT_RULE_V2.md'
RULE_RESERVE = OUT / 'PER_FACT_RULE_V3.md'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'revalidation.md'
SPLIT = OUT / 'split.json'


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def carriers():
    pk = packages(set(anchor_ids()))
    ret = load_returns()
    out = {}
    for (m, inst), t in pk.items():
        anns = ret.get(digest(blind_view(t))) or {}
        for a, x in anns.items():
            rows = json.loads(x['answers']['carriers_json'])
            d = {}
            for c in rows:
                if c.get('checkpoint') == 'board':
                    d.setdefault(c['fact_id'], set()).update(c['unit_ids'])
            out[(m, inst, a)] = d
    return out


def score(version='v3', split='validation'):
    auth = carriers()
    items = json.loads(RESULTS.read_text())['items']
    rows = [r for r in items if r['split'] == split
            and r['checkpoint'] == 'board' and r.get('labeller')
            and r.get('prompt_version') == version]
    pairs = []
    fact_n = fact_ok = 0
    detail = []
    for r in rows:
        au = auth[(r['model'], r['instance_id'], r['annotator'])]
        ok = True
        for f, v in r['labeller'].items():
            hit = v['status'] != 'absent' and bool(
                set(v['unit_ids']) & au.get(f, set()))
            fact_n += 1
            fact_ok += hit
            if not hit:
                ok = False
        pairs.append((ok, bool(r['author_complete']), r['instance_id']))
        detail.append({'instance_id': r['instance_id'], 'model': r['model'],
                       'annotator': r['annotator'], 'complete': ok,
                       'author_complete': bool(r['author_complete'])})
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
    klo, khi = (vals[int(.025 * len(vals))],
                vals[int(.975 * len(vals)) - 1]) if vals else (float('nan'),
                                                               float('nan'))
    return {'n': n, 'k': k, 'agreement': k / n, 'lo': lo, 'hi': hi,
            'kappa': kap, 'klo': klo, 'khi': khi,
            'fact_n': fact_n, 'fact_ok': fact_ok, 'detail': detail}


def main():
    import sys
    split = 'reserve' if '--reserve' in sys.argv else 'validation'
    s = score(split=split)
    rule = RULE_RESERVE if split == 'reserve' else RULE
    verdict = ('PASS' if s['agreement'] >= 0.80 and s['kappa'] >= 0.60
               else 'FAIL')
    title = ('# Per-fact carrier-target fresh check (reserve)\n'
             if split == 'reserve' else
             '# Per-fact carrier-target result (exploratory, n=48)\n')
    lines = [title,
             f"Rule `{rule.name}` (sha256 `{file_sha(rule)[:12]}`), " +
             ('frozen before the reserve calls; 60 reserve calls, spend '
              '$0.026698, zero model calls in this rescoring.'
              if split == 'reserve' else
              'frozen before this rescoring. Zero model calls; the frozen v3 '
              'output is re-scored.') +
             ' The semantic-target result stays in `report.md` as FAIL.\n' +
             ('' if split == 'reserve' else
              '**This n=48 result is exploratory**: the carrier target was '
              'chosen after these traces were seen, so it is not a validation '
              'of the labeller. The fresh reserve check is in '
              '`revalidation_reserve.md` and FAILS (20/30, kappa 0.194); the '
              'labeller stays unvalidated.\n'),
             'Target: the board `unit_ids` each author cites per fact '
             '(`carriers_json`, checkpoint board). A fact matches if the '
             'labeller\'s returned unit_ids intersect the author\'s; complete '
             'means every fact matches. Compared with `author_complete` on the '
             f'frozen {"reserve" if split == "reserve" else "validation"} split '
             f'({s["n"]} board comparisons).\n',
             f"Agreement **{s['k']}/{s['n']} = {s['agreement']:.3f}** "
             f"(95% CI {s['lo']:.3f}-{s['hi']:.3f}); kappa "
             f"**{s['kappa']:.3f}** ({s['klo']:.3f}-{s['khi']:.3f}) — "
             f"**{verdict}" + ('' if split == 'reserve'
                                else ' (exploratory, not a validation)') +
             "** against 0.80/0.60.\n",
             f"Per-fact carrier match: **{s['fact_ok']}/{s['fact_n']} = "
             f"{s['fact_ok'] / s['fact_n']:.3f}**.\n",
             '| instance | model | annotator | labeller complete | author complete |',
             '| --- | --- | --- | --- | --- |']
    for d in s['detail']:
        lines.append(f"| {d['instance_id']} | {d['model']} | "
                     f"{d['annotator']} | {d['complete']} | "
                     f"{d['author_complete']} |")
    what = ('This validates carrier-unit identification against the author '
            'records: the labeller finds the units the authors cited. It does '
            '**not** validate semantic fidelity, and the main-table coverage, '
            'recall, omission, fidelity and AF columns stay lexical: those '
            'need a semantic target the audit can apply to its own fact list.'
            if verdict == 'PASS' else
            'This fresh check **fails**: the carrier-identification target '
            'does not replicate on traces not used for the target change. The '
            'labeller stays unvalidated; the n=48 result is labelled '
            '"exploratory carrier-identification pass, n=48". It does not '
            'validate semantic fidelity or semantic coverage; the main-table '
            'coverage, recall, omission, fidelity and AF columns stay lexical '
            'or matcher.')
    lines += ['', '## What this result covers\n', what + ' The earlier semantic-target FAIL remains on record and is not retracted.']
    path = OUT / ('revalidation_reserve.md' if split == 'reserve'
                  else 'revalidation.md')
    path.write_text('\n'.join(lines) + '\n')
    print(json.dumps({k: s[k] for k in ('n', 'k', 'agreement', 'lo', 'hi',
                                        'kappa', 'klo', 'khi', 'fact_n',
                                        'fact_ok')}, indent=1))


if __name__ == '__main__':
    main()