"""Per-fact labeller at the relay checkpoints (extraction pool, board).

Rule: `rebuttal/pilots/20261113_per_fact_labeller/PER_FACT_RULE.md`, frozen
before any call. The input is the audit's critical-fact list (matcher facts),
not the support documents. Pilot cap $5; every call logged.

    ./run.sh python -m scripts.per_fact_labeller --build
    ./run.sh python -m scripts.per_fact_labeller --dev --prompt v1 --cap-usd 5
    ./run.sh python -m scripts.per_fact_labeller --freeze --prompt v2
    ./run.sh python -m scripts.per_fact_labeller --validate
    ./run.sh python -m scripts.per_fact_labeller --report
"""
import argparse
import glob
import hashlib
import json
import math
import random
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.coverage_validation import author_complete, kappa_binary, load_returns
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.pilot_llm_labeller import MODEL_OPENROUTER, PRICE_IN, PRICE_OUT
from src.audit.pilot_common import blind_view, digest
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_per_fact_labeller'
RULE = OUT / 'PER_FACT_RULE.md'
MANIFEST = OUT / 'run_manifest.json'
SPLIT = OUT / 'split.json'
POP = OUT / 'population.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'
ANCHOR = ROOT / 'rebuttal/pilots/20261108_review7/e1_anchor_locked_manifest.json'
MATCHER = ROOT / 'rebuttal/results/batch1/E1_matcher_anchor/matcher'
MAX_TOKENS = 2000
CAP = 5.0
STATUS = {'present', 'partial', 'absent'}
FIDELITY = {'faithful', 'partial', 'distorted', 'absent'}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def split_counts(n):
    if n >= 8:
        tune = n // 2
        val = round((n - tune) * 0.6)
        return tune, val, n - tune - val
    return {3: (1, 1, 1), 2: (1, 1, 0), 1: (1, 0, 0)}[n]


def load_population():
    from scripts.build_final_author_packet import packages
    strata = {i: h for h, v in json.loads(ANCHOR.read_text())['strata'].items()
              for i in v['ids']}
    ids = set(strata)
    pk = packages(ids)
    ret = load_returns()
    recs = {}
    for p in sorted(MATCHER.glob('*.json')):
        r = json.loads(p.read_text())
        recs[(r['model'], r['instance_id'])] = r
    rows = []
    for (m, inst), t in sorted(pk.items()):
        rec = recs.get((m, inst))
        if not rec or rec.get('status') != 'ok':
            continue
        item_id = digest(blind_view(t))
        anns = ret.get(item_id) or {}
        if len(anns) != 2:
            continue
        for a, x in sorted(anns.items()):
            facts = [{'fact_id': f['fact_id'], 'text': f['text']}
                     for f in json.loads(x['answers']['critical_facts_json'])]
            cars = json.loads(x['answers']['carriers_json'])
            fids = {f['fact_id'] for f in facts}
            for cp, name, cpk in (('extraction', 'extraction pool', 'pool'),
                                  ('board', 'shared board', 'board')):
                entries = [{'unit_id': u['unit_id'], 'agent_id': u['agent_id'],
                            'text': u['text']}
                           for u in t['checkpoints'][cp]]
                fid_map = {c['fact_id']: c.get('fidelity') or 'absent'
                           for c in cars if c.get('checkpoint') == cpk
                           and c.get('fact_id') in fids}
                rows.append({'split': None, 'instance_id': inst, 'model': m,
                             'stratum': strata[inst], 'checkpoint': cp,
                             'checkpoint_name': name, 'annotator': a,
                             'author_complete': author_complete(x),
                             'question': t['question'], 'facts': facts,
                             'author_fidelity': {f: fid_map.get(f, 'absent')
                                                 for f in fids},
                             'entries': entries})
    return rows


def build():
    rows = load_population()
    inst = {}
    for r in rows:
        inst.setdefault(r['instance_id'], r['stratum'])
    assign = {}
    by = {}
    for i, h in inst.items():
        by.setdefault(h, []).append(i)
    for h, ids in by.items():
        ids = sorted(ids, key=lambda x: sha(f'43|perfact|{x}'))
        t, v, r = split_counts(len(ids))
        for x in ids[:t]:
            assign[x] = 'tune'
        for x in ids[t:t + v]:
            assign[x] = 'validation'
        for x in ids[t + v:]:
            assign[x] = 'reserve'
    for r in rows:
        r['split'] = assign[r['instance_id']]
    OUT.mkdir(parents=True, exist_ok=True)
    SPLIT.write_text(json.dumps(
        {'assign': assign,
         'counts': {s: sum(1 for x in assign.values() if x == s)
                    for s in ('tune', 'validation', 'reserve')},
         'rule': str(RULE.relative_to(ROOT))}, indent=1))
    POP.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_sha256': file_sha(RULE),
        'split_sha256': file_sha(SPLIT),
        'population_sha256': file_sha(POP),
        'traces': len({(r['instance_id'], r['model']) for r in rows}),
        'instances': len(inst), 'max_tokens': MAX_TOKENS,
        'cap_usd': CAP,
    }, indent=1))
    print(json.dumps({'traces': len({(r['instance_id'], r['model']) for r in rows}),
                      'instances': len(inst),
                      'counts': json.loads(SPLIT.read_text())['counts']},
                     indent=1))


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') in ('result', 'skipped'))


def render(row):
    facts = '\n'.join(f"{f['fact_id']}: {f['text']}" for f in row['facts'])
    entries = '\n'.join(f"[{u['unit_id']}] (agent {u['agent_id']}) {u['text'][:1500]}"
                        for u in row['entries'])
    return (f"QUESTION\n{row['question']}\n\nCRITICAL FACTS\n{facts}\n\n"
            f"CHECKPOINT: {row['checkpoint_name']}\n{entries}")


def parse(content, fact_ids):
    obj = last_object(content or '')
    if not obj or not isinstance(obj.get('facts'), list):
        return None
    ids = [x.get('fact_id') for x in obj['facts'] if isinstance(x, dict)]
    if len(ids) != len(set(ids)) or set(ids) != fact_ids:
        return None
    out = {}
    for x in obj['facts']:
        if x.get('status') not in STATUS or x.get('fidelity') not in FIDELITY:
            return None
        if not isinstance(x.get('unit_ids'), list):
            return None
        out[x['fact_id']] = {'status': x['status'],
                             'fidelity': x['fidelity'],
                             'unit_ids': x['unit_ids'],
                             'reason': str(x.get('reason', ''))[:200]}
    return out


def call(key, spec, user, cap, total):
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    est = est_in * PRICE_IN + MAX_TOKENS * PRICE_OUT
    if total + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                'cost_usd': 0.0}) + '\n')
        return None, total
    call_id = sha('|'.join([key, spec['system'], user, str(MAX_TOKENS)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': call_id,
                            'model': spec['model'],
                            'system_sha256': sha(spec['system']),
                            'user_sha256': sha(user), 'max_tokens': MAX_TOKENS,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=spec['system'], user_query=user,
                     model=spec['model'], max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'per_fact_labeller', 'key': key,
                               'openrouter_reasoning': False})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
            + usage.get('completion_tokens', 0) * PRICE_OUT)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': call_id,
                            'model': spec['model'], 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def run_split(split, prompt_path, cap):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(SPLIT) == man['split_sha256'], 'split changed'
    assert file_sha(POP) == man['population_sha256'], 'population changed'
    spec = json.loads(prompt_path.read_text())
    rows = [r for r in json.loads(POP.read_text()) if r['split'] == split]
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in json.loads(RESULTS.read_text())['items']}
    out = list(done.values())
    total = spent()
    for r in rows:
        key = (f"{split}/{spec['version']}/{r['model']}/{r['instance_id']}/"
               f"{r['annotator']}/{r['checkpoint']}")
        if key in done:
            continue
        user = render(r)
        resp, total = call(key, spec, user, cap, total)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        lab = parse(resp.content, {f['fact_id'] for f in r['facts']}) \
            if resp.success else None
        rec = {'key': key, 'split': split, 'instance_id': r['instance_id'],
               'model': r['model'], 'stratum': r['stratum'],
               'checkpoint': r['checkpoint'], 'annotator': r['annotator'],
               'author_complete': bool(r['author_complete']),
               'author_fidelity': r['author_fidelity'],
               'prompt_version': spec['version'],
               'prompt_file_sha256': file_sha(prompt_path),
               'prompt_system_sha256': sha(spec['system']),
               'success': resp.success, 'error': resp.error,
               'labeller': lab,
               'complete': (all(x['fidelity'] == 'faithful'
                                for x in lab.values()) if lab else None),
               }
        out.append(rec)
        RESULTS.write_text(json.dumps({'items': out}, indent=1,
                                      ensure_ascii=False))
        print(json.dumps({'key': key, 'valid': lab is not None,
                          'complete': rec['complete'],
                          'spent_usd': round(total, 6)}), flush=True)
    RESULTS.write_text(json.dumps({'items': out}, indent=1, ensure_ascii=False))
    print(json.dumps({'split': split, 'rows': len(rows),
                      'spent_usd': round(spent(), 8)}, indent=1))


def freeze(prompt_path):
    spec = json.loads(prompt_path.read_text())
    man = json.loads(MANIFEST.read_text())
    man.update({'frozen_prompt_file': str(prompt_path.relative_to(ROOT)),
                'frozen_prompt_file_sha256': file_sha(prompt_path),
                'frozen_prompt_system_sha256': sha(spec['system']),
                'frozen_prompt_version': spec['version'],
                'frozen_before_validation': True})
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps({k: man[k] for k in ('frozen_prompt_file',
                                          'frozen_prompt_version',
                                          'frozen_prompt_system_sha256')},
                     indent=1))


def items_for(split):
    d = json.loads(RESULTS.read_text())['items']
    return [r for r in d if r['split'] == split]


def pairs(rows):
    out = []
    return [(bool(r['complete']), bool(r['author_complete']),
             r['instance_id'], r) for r in rows
            if r.get('labeller') and 'author_complete' in r]


def kappa_ci(ps, seed):
    by = {}
    for x, y, inst, _ in ps:
        by.setdefault(inst, []).append((x, y))
    keys = sorted(by)
    rng = random.Random(seed)
    vals = []
    for _ in range(10000):
        draw = []
        for _ in keys:
            draw += by[keys[rng.randrange(len(keys))]]
        vals.append(kappa_binary([(x, y) for x, y in draw]))
    vals = [v for v in vals if v == v]
    if not vals:
        return float('nan'), float('nan')
    vals.sort()
    return vals[int(.025 * len(vals))], vals[int(.975 * len(vals)) - 1]


def score(split, checkpoint='board', version=None):
    rows = [r for r in items_for(split) if r['checkpoint'] == checkpoint]
    if version:
        rows = [r for r in rows if r.get('prompt_version') == version]
    if split != 'tune':
        frozen = json.loads(MANIFEST.read_text()).get(
            'frozen_prompt_system_sha256')
        rows = [r for r in rows
                if r.get('prompt_system_sha256') == frozen]
    ps = pairs(rows)
    n = len(ps)
    k = sum(x == y for x, y, _, _ in ps)
    lo, hi = cp_ci(k, n)
    kap = kappa_binary([(x, y) for x, y, _, _ in ps])
    klo, khi = kappa_ci(ps, 43)
    invalid = sum(1 for r in rows if not r.get('labeller'))
    calls = len(rows)
    return {'calls': calls, 'valid': calls - invalid, 'invalid': invalid,
            'comparisons': n, 'agree': k, 'agreement': k / n if n else None,
            'agree_lo': lo, 'agree_hi': hi, 'kappa': kap,
            'kappa_lo': klo, 'kappa_hi': khi, 'pairs': ps, 'rows': rows}


def report():
    man = json.loads(MANIFEST.read_text())
    lines = ['# Per-fact labeller at the relay checkpoints\n',
             f"Rule `PER_FACT_RULE.md` (sha256 `{file_sha(RULE)[:12]}`); split "
             f"`split.json` (sha256 `{man['split_sha256'][:12]}`); frozen prompt "
             f"`{man.get('frozen_prompt_file')}` (system sha256 "
             f"`{(man.get('frozen_prompt_system_sha256') or '')[:12]}`). Pilot "
             f"cap ${CAP:.2f}; spend ${spent():.6f}.\n",
             'Stage: relay checkpoints (extraction pool and shared board). '
             'Input: the critical-fact list (Amendment 1: the annotator '
             '`critical_facts_json` for the validation population; the first '
             'matcher-fact pass stays on record); support documents not shown. '
             'Complete coverage: every fact faithful at the board (authors\' '
             'rule).\n']
    for split in ('tune', 'validation', 'reserve'):
        versions = (sorted({r.get('prompt_version') for r in items_for('tune')})
                    if split == 'tune' else [None])
        for ver in versions:
            s = score(split, version=ver)
            if not s['calls']:
                continue
            label = f"## {split}" + (f" — prompt {ver}" if ver else "")
            if s['comparisons']:
                verdict = ('PASS' if s['agreement'] >= 0.80 and
                           s['kappa'] >= 0.60 else 'FAIL')
                lines.append(
                    f"{label}\n\nCalls {s['calls']} ({s['invalid']} invalid). "
                    f"Comparisons {s['comparisons']}: agreement "
                    f"{s['agree']}/{s['comparisons']} = {s['agreement']:.3f} "
                    f"(95% CI {s['agree_lo']:.3f}-{s['agree_hi']:.3f}); kappa "
                    f"{s['kappa']:.3f} ({s['kappa_lo']:.3f}-{s['kappa_hi']:.3f})"
                    + (f" — **{verdict}**" if split != 'tune' else '') + '.\n')
                if split in ('validation', 'reserve'):
                    bad = [(x, y, rr) for x, y, _, rr in s['pairs'] if x != y]
                    if bad:
                        lines.append('Disagreements (labeller complete, '
                                     'author complete):\n')
                        for x, y, rr in bad:
                            lines.append(
                                f"- {rr['instance_id']} / {rr['model']} / "
                                f"{rr['checkpoint']}: labeller {x}, author "
                                f"{y}; " + ', '.join(
                                    f"{f}: {v['status']}/{v['fidelity']} "
                                    f"(author "
                                    f"{rr.get('author_fidelity', {}).get(f, '?')})"
                                    for f, v in rr['labeller'].items()))
            else:
                lines.append(f"{label}\n\nNo comparisons.\n")
    if man.get('frozen_prompt_system_sha256'):
        s = score('validation')
        verdict = ('pass' if s['comparisons'] and s['agreement'] >= 0.80 and
                   s['kappa'] >= 0.60 else 'fail') if s['comparisons'] else 'void'
        lines += ['', '## Decision\n',
                  f"Validation **{verdict}** under the frozen rule "
                  '(agreement >= 0.80 and kappa >= 0.60). '
                  + ('The labeller is validated for board complete coverage; '
                     'main-table columns may be redone beside the old values.'
                     if verdict == 'pass' else
                     'The labeller is not validated on the semantic target; '
                     'lexical coverage remains the reported figure. The '
                     'carrier-target n=48 result is exploratory '
                     '(`revalidation.md`); the fresh reserve check under '
                     '`PER_FACT_RULE_V3.md` FAILS (20/30, kappa 0.194), so the '
                     'labeller is not validated for carrier identification '
                     'either. The semantic FAIL stays on record beside it.')]
        vr = [r for r in items_for('validation')
              if r['checkpoint'] == 'board' and r.get('labeller')
              and 'author_complete' in r]
        conf = {}
        facts = {'author': 0, 'labeller': 0, 'n': 0}
        for r in vr:
            conf[(bool(r['complete']), bool(r['author_complete']))] = \
                conf.get((bool(r['complete']), bool(r['author_complete'])), 0) + 1
            for f, v in r['labeller'].items():
                a = r['author_fidelity'].get(f, '?')
                facts['n'] += 1
                facts['author'] += a == 'faithful'
                facts['labeller'] += v['fidelity'] == 'faithful'
        bad = [r for r in vr
               if r['author_complete'] and not r['complete']]
        lines += ['', '## Diagnosis\n',
                  f"Validation confusion (labeller complete, author complete): "
                  f"both true {conf.get((True, True), 0)}, labeller false / "
                  f"author true {conf.get((False, True), 0)}, both false "
                  f"{conf.get((False, False), 0)}, labeller true / author "
                  f"false {conf.get((True, False), 0)}. Every disagreement in "
                  'this validation is the labeller calling a trace incomplete '
                  'that the authors call complete. At the fact level the '
                  f"authors label {facts['author']} of {facts['n']} board "
                  f"carriers faithful; the labeller labels "
                  f"{facts['labeller']} faithful. The author label is near "
                  'constant, and its carrier records mark facts faithful whose '
                  'cited board units do not state them.\n',
                  'Examples from the validation disagreements:']
        for r in bad[:3]:
            fl = [f"{f}: board {', '.join(v['unit_ids']) or 'none'} -> "
                  f"labeller {v['status']}/{v['fidelity']}"
                  for f, v in r['labeller'].items() if v['fidelity'] != 'faithful']
            lines.append(f"- {r['instance_id']} / {r['model']} / "
                         f"{r['annotator']}: author complete; " + '; '.join(fl))
        lines += ['',
                  'The clearest case is 2hop__28287_89399 / gemma31b / C: the '
                  'author lists "It is thought that annelids were originally '
                  'animals with two separate sexes, which released ova and '
                  'sperm into the water via their nephridia" and marks it '
                  'faithful with board:a1:u0, whose text is "Annelid '
                  'fertilized eggs develop into trochophore larvae, which live '
                  'as plankton." That unit does not state the listed fact. A '
                  'labeller that reproduces this label would have to call an '
                  'unsupported carrier faithful.\n',
                  'Prompt revisions tried on the tune split: matcher-fact v1 '
                  '0.603 (47/78, kappa 0.221); author-fact v2 0.400; '
                  'decisive-content v3 0.397; question-relevance v4 0.436. The '
                  'change from the audit matcher facts to the annotator list '
                  '(Amendment 1) did not raise agreement, and neither wording '
                  'change did, because the remaining gap is the reference '
                  'label, not the prompt. The reserve split is held unused: '
                  'the rule allows it only for re-validation after a cause is '
                  'fixed, and no labeller-side fix addresses a reference that '
                  'marks unsupported carriers faithful.']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({s: {k: score(s)[k] for k in
                          ('calls', 'invalid', 'comparisons', 'agreement',
                           'kappa')} for s in ('tune', 'validation', 'reserve')},
                     indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--dev', action='store_true')
    ap.add_argument('--freeze', action='store_true')
    ap.add_argument('--validate', action='store_true')
    ap.add_argument('--reserve', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--prompt', default='v1')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.build:
        build()
    if a.dev:
        run_split('tune', OUT / f'per_fact_prompt_{a.prompt}.json', a.cap_usd)
    if a.freeze:
        freeze(OUT / f'per_fact_prompt_{a.prompt}.json')
    if a.validate:
        man = json.loads(MANIFEST.read_text())
        spec = json.loads((ROOT / man['frozen_prompt_file']).read_text())
        assert sha(spec['system']) == man['frozen_prompt_system_sha256']
        run_split('reserve' if a.reserve else 'validation',
                  ROOT / man['frozen_prompt_file'], a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()