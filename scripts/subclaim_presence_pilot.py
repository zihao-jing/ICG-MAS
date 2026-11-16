"""Sub-claim presence rule B: 20-case pilot on saved MuSiQue checkpoints.

Rule: `rebuttal/pilots/20261113_subclaim_presence_pilot/SUB_CLAIM_RULE.md`,
frozen before any call. Reuses the frozen full MuSiQue presence population and
results; no new relay runs.

    ./run.sh python -m scripts.subclaim_presence_pilot --build
    ./run.sh python -m scripts.subclaim_presence_pilot --run --cap-usd 5
    ./run.sh python -m scripts.subclaim_presence_pilot --report
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.per_fact_labeller import render as render_a

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / 'rebuttal/pilots/20261113_musique_presence_full'
OUT = ROOT / 'rebuttal/pilots/20261113_subclaim_presence_pilot'
RULE = OUT / 'SUB_CLAIM_RULE.md'
PROMPT = OUT / 'subclaim_prompt.json'
POP = OUT / 'population.json'
MANIFEST = OUT / 'run_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'
HAIKU = 'anthropic/claude-haiku-5.5'
PRICE_IN = 0.10 / 1_000_000
PRICE_OUT = 0.50 / 1_000_000
MAX_LAB = 4096
CAP = 5.0
SEED = 43
STATUS = {'present', 'partial', 'absent'}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render(row):
    facts = '\n'.join(f"{f['fact_id']}: {f['text']}"
                      for f in row['facts'])
    entries = '\n'.join(f"[{u['unit_id']}] (agent {u['agent_id']}) "
                        f"{u['text'][:1500]}" for u in row['entries'])
    return (f"QUESTION\n{row['question']}\n\nCRITICAL FACTS\n{facts}\n\n"
            f"CHECKPOINT: {row['checkpoint_name']}\n{entries}")


def a_complete(row):
    labs = row.get('labeller') or {}
    return all(labs.get(f['fact_id'], {}).get('status')
               in ('present', 'partial') for f in row['facts'])


def build():
    pop = {r['key']: r for r in json.loads(
        (FULL / 'population.json').read_text())}
    items = {r['key']: r for r in json.loads(
        (FULL / 'results.json').read_text())['items'] if r.get('labeller')}
    complete, incomplete = [], []
    for key, r in items.items():
        if key not in pop:
            continue
        row = dict(pop[key], a_complete=a_complete(r),
                   a_status={f['fact_id']:
                             r['labeller'].get(f['fact_id'], {})
                             .get('status') for f in r['facts']})
        (complete if row['a_complete'] else incomplete).append(row)
    for rows in (complete, incomplete):
        rows.sort(key=lambda r: sha('43|b-pilot|' + r['key']))
    chosen, seen = [], set()
    for pool, n in ((complete, 10), (incomplete, 10)):
        k = 0
        for r in pool:
            if r['instance_id'] in seen:
                continue
            chosen.append(r)
            seen.add(r['instance_id'])
            k += 1
            if k == n:
                break
        assert k == n, (n, k)
    chosen.sort(key=lambda r: r['key'])
    assert len(chosen) == 20
    POP.write_text(json.dumps(chosen, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_sha256': file_sha(RULE),
        'prompt_sha256': file_sha(PROMPT),
        'population_sha256': file_sha(POP),
        'full_population_sha256': file_sha(FULL / 'population.json'),
        'full_results_sha256': file_sha(FULL / 'results.json'),
        'rows': len(chosen), 'strata': {'a_complete': 10,
                                        'a_not_complete': 10},
        'cap_usd': CAP, 'model': HAIKU, 'seed': SEED}, indent=1))
    print(json.dumps({'rows': len(chosen),
                      'a_complete': sum(r['a_complete'] for r in chosen),
                      'facts': sum(len(r['facts']) for r in chosen),
                      'population_sha256': file_sha(POP)[:12]}, indent=1))


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def parse(content, fact_ids):
    obj = last_object(content or '')
    if not isinstance(obj, dict) or not isinstance(obj.get('facts'), list):
        return None
    ids = [x.get('fact_id') for x in obj['facts'] if isinstance(x, dict)]
    if len(ids) != len(set(ids)) or set(ids) != fact_ids:
        return None
    out = {}
    for x in obj['facts']:
        if x.get('status') not in STATUS:
            return None
        if x.get('central_claim_status') not in STATUS:
            return None
        subs = x.get('subclaims')
        if not isinstance(subs, list) or not subs:
            return None
        for s in subs:
            if (not isinstance(s, dict) or s.get('status') not in STATUS
                    or not isinstance(s.get('text'), str)
                    or not isinstance(s.get('unit_ids'), list)):
                return None
        if not isinstance(x.get('missing'), list):
            return None
        out[x['fact_id']] = {
            'status': x['status'],
            'central_claim_status': x['central_claim_status'],
            'subclaims': [{'text': str(s['text'])[:300],
                           'status': s['status'],
                           'unit_ids': [u for u in s['unit_ids']
                                        if isinstance(u, str)]}
                          for s in subs],
            'missing': [str(m)[:200] for m in x['missing']],
            'unit_ids': [u for u in (x.get('unit_ids') or [])
                         if isinstance(u, str)],
            'reason': str(x.get('reason', ''))[:200]}
    return out


def call(key, system, user, cap):
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * PRICE_IN + MAX_LAB * PRICE_OUT
    if spent() + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key,
                                'cost_usd': 0.0}) + '\n')
        return None
    cid = sha('|'.join([key, HAIKU, system, user, str(MAX_LAB)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid,
                            'model': HAIKU, 'system_sha256': sha(system),
                            'user_sha256': sha(user),
                            'max_tokens': MAX_LAB,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    from utility.apis.base import APIRequest
    req = APIRequest(system_query=system, user_query=user, model=HAIKU,
                     max_tokens=MAX_LAB, temperature=0,
                     metadata={'pilot': 'subclaim_presence',
                               'key': key})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = 0.0 if not resp.success else (
        usage.get('prompt_tokens', est_in) * PRICE_IN
        + usage.get('completion_tokens', 0) * PRICE_OUT)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid,
                            'model': HAIKU, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage,
                            'cost_usd': round(cost, 8)}) + '\n')
    return resp


def run(cap):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(POP) == man['population_sha256']
    spec = json.loads(PROMPT.read_text())
    rows = json.loads(POP.read_text())
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in json.loads(RESULTS.read_text())['items']
                if r.get('labeller')}
    for r in rows:
        if r['key'] in done:
            continue
        resp = call(f"sub/{r['key']}", spec['system'], render(r), cap)
        lab = parse(resp.content, {f['fact_id'] for f in r['facts']}) \
            if resp and resp.success else None
        done[r['key']] = {'key': r['key'], 'model': r['model'],
                          'protocol': r['protocol'],
                          'instance_id': r['instance_id'],
                          'checkpoint': r['checkpoint'],
                          'a_complete': r['a_complete'],
                          'a_status': r['a_status'],
                          'facts': r['facts'],
                          'b': lab}
        RESULTS.write_text(json.dumps({'items': list(done.values())},
                                      indent=1, ensure_ascii=False))
        print(json.dumps({'done': len(done), 'of': len(rows),
                          'spent_usd': round(spent(), 6)}), flush=True)


def report():
    man = json.loads(MANIFEST.read_text())
    items = json.loads(RESULTS.read_text())['items']
    valid = [r for r in items if r.get('b')]
    spend = spent()
    per_case = spend / len(items) if items else 0.0
    full_rows = 2100
    est_full = per_case * full_rows
    nfacts = sum(len(r['facts']) for r in valid)
    b_present = sum(1 for r in valid for f in r['facts']
                    if r['b'][f['fact_id']]['status'] == 'present')
    b_partial = sum(1 for r in valid for f in r['facts']
                    if r['b'][f['fact_id']]['status'] == 'partial')
    b_absent = sum(1 for r in valid for f in r['facts']
                   if r['b'][f['fact_id']]['status'] == 'absent')
    subs = sum(len(r['b'][f['fact_id']]['subclaims'])
               for r in valid for f in r['facts'])
    miss = sum(len(r['b'][f['fact_id']]['missing'])
               for r in valid for f in r['facts'])
    a_facts = sum(1 for r in valid for f in r['facts']
                  if r['a_status'].get(f['fact_id']) in ('present', 'partial'))
    lines = [
        '# Sub-claim presence rule B: 20-case pilot\n',
        f"Rule `SUB_CLAIM_RULE.md` (sha256 `{file_sha(RULE)[:12]}`), prompt "
        f"`subclaim_prompt.json` (sha256 `{file_sha(PROMPT)[:12]}`). Claude "
        f"Haiku 5.5, temperature 0. {len(items)} saved MuSiQue checkpoint "
        f"cases (10 where A says complete, 10 where A does not; distinct "
        f"instances), {nfacts} facts. Spend **${spend:.6f}**, cap $5.00. "
        f"Stage: relay checkpoints (extraction pool / shared board).\n",
        f"Price per case **${per_case:.6f}**; full-run estimate for 2,100 "
        f"rows at this price **${est_full:.2f}** (not run; needs approval).\n",
        '| measure | count |', '| --- | ---: |',
        f"| facts labelled present by B | {b_present} |",
        f"| facts partial by B | {b_partial} |",
        f"| facts absent by B | {b_absent} |",
        f"| facts A carried (present/partial) | {a_facts} |",
        f"| atomic sub-claims split | {subs} |",
        f"| sub-claims listed missing | {miss} |",
        '', '| key | A complete | A statuses | B statuses | sub-claims | missing |',
        '| --- | --- | --- | --- | ---: | ---: |']
    for r in valid:
        a_s = ', '.join(f"{f['fact_id']}:{r['a_status'].get(f['fact_id'])}"
                        for f in r['facts'])
        b_s = ', '.join(f"{f['fact_id']}:{r['b'][f['fact_id']]['status']}"
                        for f in r['facts'])
        ns = sum(len(r['b'][f['fact_id']]['subclaims']) for f in r['facts'])
        nm = sum(len(r['b'][f['fact_id']]['missing']) for f in r['facts'])
        lines.append(f"| `{r['key']}` | {int(r['a_complete'])} | {a_s} | "
                     f"{b_s} | {ns} | {nm} |")
    lines += ['', '## Examples of sub-claims B finds missing while A credits the fact\n']
    shown = 0
    for r in valid:
        for f in r['facts']:
            x = r['b'][f['fact_id']]
            if r['a_status'].get(f['fact_id']) in ('present', 'partial') \
                    and x['status'] != 'present' and x['missing'] and shown < 8:
                lines.append(f"- `{r['key']}` / {f['fact_id']}: A="
                             f"{r['a_status'].get(f['fact_id'])}, B="
                             f"{x['status']}; missing: "
                             + '; '.join(x['missing'][:6]))
                shown += 1
    lines += ['', 'Pilot only: B is **not validated** against the stronger '
              'reference and is not a table column. A remains the validated '
              'label with the central-claim qualifier. The full run is not '
              'started; the estimate above is the decision input.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'cases': len(items), 'facts': nfacts,
                      'b_present': b_present, 'b_partial': b_partial,
                      'b_absent': b_absent, 'a_carried': a_facts,
                      'price_per_case': round(per_case, 8),
                      'full_estimate_usd': round(est_full, 2),
                      'spend_usd': round(spend, 6)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    for f in ('build', 'run', 'report'):
        ap.add_argument('--' + f, action='store_true', dest=f)
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.build:
        build()
    if a.run:
        run(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()