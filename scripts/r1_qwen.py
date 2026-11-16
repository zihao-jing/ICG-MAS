"""[R1] released prompt and parser on the 89 known-stage cases, Qwen-235B backbone. Cap $1.00.

Same rule (`R1-coordinate-stage-map.md`, sha 2015e084…), prompt, parser and mode->stage map as
`r1_full.py`, which ran Gemini 3.6 Flash. Build prints the projection before any call.

    ./run.sh python -m scripts.r1_qwen --build
    ./run.sh python -m scripts.r1_qwen --run
    ./run.sh python -m scripts.r1_qwen --score
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.audit_diagnosis_89 import accepted, corrupted, packages
from scripts.b5_attribution_2x2 import CASES, adapt
from src.audit.official_adapters import parse_r1, r1_prompt
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_r1_qwen'
RULE = ROOT / 'rebuttal/pilots/prereg/R1-coordinate-stage-map.md'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
SCORE = OUT / 'score.json'
MODEL = 'qwen/qwen3-235b-a22b-2507'
PRICE = (0.14 / 1e6, 0.8 / 1e6)
CAP = 1.00
TOK = 4096
OUT_TOK = 500

MODE_STAGE = {
    'P.1': 'extraction', 'P.2': 'extraction', 'R.1': 'aggregation', 'R.2': 'aggregation',
    'R.3': 'aggregation', 'R.4': 'aggregation', 'PL.1': 'aggregation', 'PL.2': 'aggregation',
    'A.1': 'extraction', 'A.2': 'extraction', 'A.3': 'aggregation', 'A.4': 'aggregation',
    'V.1': 'transmission', 'V.2': 'aggregation', 'C.1': 'aggregation', 'C.2': 'transmission',
    'C.3': 'aggregation'}


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0) or 0 for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def render_all():
    cases = json.loads(CASES.read_text())
    acc = accepted()
    pk = {m: packages(m) for m in {c['key'].split('/')[1] for c in cases}}
    out = []
    for c in cases:
        model, inst = c['key'].split('/')[1], c['key'].split('/')[2]
        t = corrupted(c, acc) if c['population'] == 'injected' else adapt(pk[model][inst])
        t['answer_text'] = c.get('answer') or ''
        t['gold_answer'] = acc.get((model, inst), {}).get('gold', '') if c['population'] == 'injected' else (c.get('gold') or '')
        t.setdefault('question', c['question'])
        msgs, steps = r1_prompt(trace=t, gold=False)
        user = msgs[0]['content'] if isinstance(msgs[0], dict) else msgs[0]
        if isinstance(user, list):
            user = '\n'.join(b.get('text', '') for b in user if isinstance(b, dict))
        out.append({'key': c['key'], 'known_stage': c['known_stage'], 'user': user, 'steps': steps,
                    'population': c['population']})
    return out


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    rows = render_all()
    projection = sum(math.ceil(len(r['user']) / 4) * PRICE[0] + OUT_TOK * PRICE[1] for r in rows)
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE),
           'prompt_sha256': file_sha(ROOT / 'rebuttal/external/whowhen_eval/prompts.py'),
           'taxonomy_sha256': file_sha(ROOT / 'rebuttal/external/taxonomy.yaml'),
           'mode_stage_map_sha256': sha(json.dumps(MODE_STAGE, sort_keys=True)),
           'model': MODEL, 'cases': len(rows), 'cap_usd': CAP,
           'projection_usd': round(projection, 4), 'projection_out_tokens_per_call': OUT_TOK}
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def run():
    man = json.loads((OUT / 'build_manifest.json').read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert sha(json.dumps(MODE_STAGE, sort_keys=True)) == man['mode_stage_map_sha256'], 'map changed'
    done = ({json.loads(l)['trace_id'] for l in RESULTS.read_text().splitlines() if l.strip()}
            if RESULTS.exists() else set())
    total = spent()
    for r in render_all():
        if r['key'] in done:
            continue
        est = math.ceil(len(r['user']) / 4)
        if total + est * PRICE[0] + OUT_TOK * PRICE[1] > CAP:
            print(json.dumps({'stop': 'cap', 'spent': round(total, 6)})); return
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'intent', 'key': r['key'], 'model': MODEL,
                                'user_sha256': sha(r['user'])}) + '\n')
        resp = single_request(APIRequest(system_query='', user_query=r['user'], model=MODEL,
                                         max_tokens=TOK, temperature=0,
                                         metadata={'pilot': 'r1_qwen'}))
        u = resp.usage or {}
        cost = u.get('prompt_tokens', est) * PRICE[0] + u.get('completion_tokens', 0) * PRICE[1]
        parsed = parse_r1(resp.content or '', r['steps']) if resp.success else {}
        mode = (parsed or {}).get('mode') or ''
        rec = {'trace_id': r['key'], 'known_stage': r['known_stage'], 'population': r['population'],
               'mode': mode, 'stage': MODE_STAGE.get(mode, 'unmapped'),
               'parses': (parsed or {}).get('parses'), 'agent': (parsed or {}).get('agent'),
               'step': (parsed or {}).get('step'), 'raw': (resp.content or '')[:1200]}
        with RESULTS.open('a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'result', 'key': r['key'], 'model': MODEL,
                                'success': resp.success, 'usage': u, 'cost_usd': round(cost, 8)}) + '\n')
        total += cost
        print(json.dumps({'key': r['key'], 'mode': mode, 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


def coordinate_stage(step, n_agents):
    import re
    m = re.search(r'(\d+)', str(step))
    if not m or not n_agents:
        return 'unmapped'
    s = int(m.group(1))
    if 1 <= s <= n_agents:
        return 'extraction'
    if n_agents < s <= 2 * n_agents:
        return 'transmission'
    if s in (2 * n_agents + 1, 2 * n_agents + 2):
        return 'aggregation'
    return 'unmapped'


def score():
    cases = {c['key']: c for c in json.loads(CASES.read_text())}
    acc = accepted()
    pk = {m: packages(m) for m in {c['key'].split('/')[1] for c in cases.values()}}
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    n = len(rows)
    right = 0
    by = {}
    for r in rows:
        c = cases[r['trace_id']]
        model, inst = r['trace_id'].split('/')[1], r['trace_id'].split('/')[2]
        t = corrupted(c, acc) if c['population'] == 'injected' else pk[model][inst]
        n_agents = len(t.get('source_contexts') or [])
        st = coordinate_stage(r['step'], n_agents)
        good = st == r['known_stage']
        right += good
        pop = 'injected' if r['trace_id'].startswith('inj/') else 'cohort'
        b = by.setdefault(pop, {'n': 0, 'right': 0})
        b['n'] += 1; b['right'] += good
    out = {'n': n, 'right': right, 'accuracy': right / n if n else None, 'by_population': by,
           'map': 'step coordinate, rule 2015e084', 'spend_usd': round(spent(), 6)}
    SCORE.write_text(json.dumps(out, indent=1))
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