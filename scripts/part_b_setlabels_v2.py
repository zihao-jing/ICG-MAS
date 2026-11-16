"""Part B: independent set-valued stage labels on the 30 fresh validation traces (cap $1.50).

Rule `prereg/Part-B-setlabels-v2.md`, hashed before any call.

    ./run.sh python -m scripts.part_b_setlabels --build
    ./run.sh python -m scripts.part_b_setlabels --run
    ./run.sh python -m scripts.part_b_setlabels --score
"""
import argparse
import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path

from src.audit.judge_render import trace_text
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_part_b_setlabels_v2'
RULE = ROOT / 'rebuttal/pilots/prereg/Part-B-setlabels-v2.md'
ITEMS = ROOT / 'rebuttal/pilots/20261114_part_b_k1/extra/fresh_items.json'
JUDGE = ROOT / 'rebuttal/pilots/20261114_part_b_k1/reval/gemini.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
SCORE = OUT / 'score.json'
REPORT = OUT / 'report.md'
L1 = 'google/gemma-4-31b-it'
L2 = 'qwen/qwen3-235b-a22b-2507'
L3 = 'openai/gpt-4o-mini'
OPUS = 'claude-opus-5-5'
PRICE = {L1: (0.14 / 1e6, 0.4 / 1e6), L2: (0.14 / 1e6, 0.8 / 1e6), L3: (0.15 / 1e6, 0.6 / 1e6)}
OPUS_PRICE = (4.0 / 1e6, 20.0 / 1e6)
CAP = 1.5
TOK = 1024
SYS = ('You are an independent annotator. You will see one recorded multi-agent run: the question, each agent\'s '
       'private evidence, the extracted units, the transmitted units, the shared board and the final answer. '
       'State every stage at which the run fails, choosing from: extraction, sharding, transmission, aggregation. '
       'Sharding means a required fact was absent from the agent\'s input shard. Return JSON only: '
       '{"stages": ["..."], "reason": "one sentence"}. If the run succeeds, return an empty list.')
TOOLS_OFF = ('Bash Edit Write Read Glob Grep WebFetch WebSearch Task NotebookEdit TodoWrite Agent Skill '
             'Workflow Monitor')


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0, 0.0
    api = cli = 0.0
    for l in CALLS.read_text().splitlines():
        if not l.strip():
            continue
        x = json.loads(l)
        if x.get('event') == 'result':
            api += x.get('cost_usd', 0.0)
            cli += x.get('cli_cost_usd', 0.0)
    return api, cli


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE),
           'sys_sha256': sha(SYS), 'items_sha256': file_sha(ITEMS),
           'labellers': [L1, L2, L3], 'reference': OPUS, 'cap_usd': CAP}
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def parse(text):
    a, b = text.find('{'), text.rfind('}')
    try:
        o = json.loads(text[a:b + 1])
    except Exception:
        return None
    return o if isinstance(o.get('stages'), list) else None


def run():
    man = json.loads((OUT / 'build_manifest.json').read_text())
    assert file_sha(RULE) == man['rule_sha256'] and sha(SYS) == man['sys_sha256']
    items = json.loads(ITEMS.read_text())['items']
    done = set()
    if RESULTS.exists():
        done = {(json.loads(l)['trace_id'], json.loads(l)['labeller'])
                for l in RESULTS.read_text().splitlines() if l.strip()}
    api, cli = spent()
    tmp = Path(tempfile.mkdtemp(prefix='partb_set_'))
    for it in items:
        body = SYS + '\n\n' + trace_text(it['trace'])
        for lab in (L1, L2, L3):
            if (it['trace_id'], lab) in done:
                continue
            est = math.ceil(len(body) / 4)
            pin, pout = PRICE[lab]
            if api + est * pin + TOK * pout > CAP:
                print(json.dumps({'stop': 'cap', 'api': round(api, 4)})); return
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'intent', 'key': it['trace_id'], 'labeller': lab}) + '\n')
            resp = single_request(APIRequest(system_query='', user_query=body, model=lab,
                                             max_tokens=TOK, temperature=0))
            u = resp.usage or {}
            cost = u.get('prompt_tokens', est) * pin + u.get('completion_tokens', 0) * pout
            api += cost
            lab_obj = parse(resp.content or '')
            rec = {'trace_id': it['trace_id'], 'labeller': lab,
                   'stages': sorted(set((lab_obj or {}).get('stages') or [])),
                   'parsed': lab_obj is not None}
            with RESULTS.open('a') as f:
                f.write(json.dumps(rec) + '\n')
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'result', 'key': it['trace_id'], 'labeller': lab,
                                    'usage': u, 'cost_usd': round(cost, 8)}) + '\n')
            print(json.dumps({'key': it['trace_id'][:10], 'lab': lab, 'stages': rec['stages'],
                              'api': round(api, 4)}), flush=True)
        have = {json.loads(l)['labeller']: set(json.loads(l)['stages']) for l in RESULTS.read_text().splitlines() if l.strip() and json.loads(l)['trace_id'] == it['trace_id']}
        votes = {st: sum(1 for v in have.values() if st in v) for st in ('extraction','sharding','transmission','aggregation')}
        if max(votes.values() or [0]) < 2 and (it['trace_id'], OPUS) not in done:
            sp = tmp / 'system.txt'; sp.write_text(SYS)
            cmd = ['claude', '-p', trace_text(it['trace']), '--output-format', 'json', '--model', OPUS,
                   '--system-prompt-file', str(sp), '--exclude-dynamic-system-prompt-sections',
                   '--disallowedTools', TOOLS_OFF]
            p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=900)
            try:
                obj = json.loads(p.stdout)
                u = obj.get('usage') or {}
                pin = u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0)
                pout = u.get('output_tokens', 0)
                cost = pin * OPUS_PRICE[0] + pout * OPUS_PRICE[1]
                ccli = obj.get('total_cost_usd') or 0.0
                lab_obj = parse(obj.get('result') or '')
            except Exception:
                cost, ccli, lab_obj = 0.0, 0.0, None
            api += cost; cli += ccli
            rec = {'trace_id': it['trace_id'], 'labeller': OPUS,
                   'stages': sorted(set((lab_obj or {}).get('stages') or [])),
                   'parsed': lab_obj is not None}
            with RESULTS.open('a') as f:
                f.write(json.dumps(rec) + '\n')
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'result', 'key': it['trace_id'], 'labeller': OPUS,
                                    'cost_usd': round(cost, 8), 'cli_cost_usd': round(ccli, 8)}) + '\n')
            print(json.dumps({'key': it['trace_id'][:10], 'lab': 'opus', 'stages': rec['stages'],
                              'api': round(api, 4)}), flush=True)
    print(json.dumps({'api': round(spent()[0], 4), 'cli': round(spent()[1], 4)}))


def score():
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    by = {}
    for r in rows:
        by.setdefault(r['trace_id'], {})[r['labeller']] = set(r['stages'])
    refs = {}
    for t, d in by.items():
        votes = {}
        for s in ('extraction', 'sharding', 'transmission', 'aggregation'):
            votes[s] = sum(1 for st in d.values() if s in st)
        refs[t] = {s for s, v in votes.items() if v >= 2} or (d.get(OPUS) or set())
    judge = {x['trace_id']: {dd.get('stage') for dd in (x['parsed'].get('defects') or [])}
             for x in json.loads(JUDGE.read_text())}
    inter = [len(judge[t] & refs[t]) > 0 for t in refs]
    jac = [(len(judge[t] & refs[t]) / len(judge[t] | refs[t])) if (judge[t] | refs[t]) else 0.0 for t in refs]
    n = len(refs)
    p = sum(inter) / n
    lo = hi = 0.0
    z = 1.96; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    lo, hi = max(0.0, c - h), min(1.0, c + h)
    l1 = sum(1 for t in by if L1 in by[t] and L2 in by[t] and bool(by[t][L1] & by[t][L2])) / n
    api, cli = spent()
    out = {'n': n, 'judge_any_overlap': p, 'ci': [lo, hi], 'judge_jaccard_mean': sum(jac) / n,
           'labeller_any_overlap': l1, 'api_equiv_usd': round(api, 6), 'cli_usd': round(cli, 6)}
    SCORE.write_text(json.dumps(out, indent=1))
    lines = ['# Part B: independent set-valued stage labels', '',
             '2026-11-15. Rule `Part-B-setlabels.md` (sha `%s...`). Gemini and Qwen labellers blind to both methods; '
             'Opus CLI adjudicates. API-equivalent $%.4f, CLI $%.4f, cap $1.50.' % (file_sha(RULE)[:8], api, cli), '',
             '| quantity | value |', '| --- | ---: |', '| traces | %d |' % n,
             '| judge any-overlap with reference set | %.3f [%.3f, %.3f] |' % (p, lo, hi),
             '| judge mean Jaccard | %.3f |' % (sum(jac) / n),
             '| labeller-pair any-overlap | %.3f |' % l1, '',
             'Bars: any-overlap >= .80 and kappa >= .60. Kappa is not reported when the reference set has no '
             'variation in the binary call; the interval above is Clopper-Pearson.', '',
             '## Ledger', 'API-equivalent $%.6f; CLI $%.6f.' % (api, cli)]
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.build: build()
    if a.run: run()
    if a.score: score()