"""Part B first-missing-checkpoint labels from stored validated presence records, plus a small Opus check.

    ./run.sh python -m scripts.part_b_validated_labels --labels
    ./run.sh python -m scripts.part_b_validated_labels --build
    ./run.sh python -m scripts.part_b_validated_labels --run
    ./run.sh python -m scripts.part_b_validated_labels --score
"""
import argparse
import hashlib
import json
import math
import random
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import scripts.b5_attribution_2x2 as B

ROOT = Path(__file__).resolve().parent.parent
PILOTS = ROOT / 'rebuttal/pilots'
RULE = PILOTS / 'prereg/Part-B-validated-label.md'
CARRIERS = PILOTS / '20261115_b5_qwen_design_a/calls.jsonl'
OUT = PILOTS / '20261115_part_b_validated_label'
LAB = OUT / 'labels.json'
CALLS = OUT / 'opus_calls.jsonl'
RESULTS = OUT / 'opus_results.jsonl'
SCORE = OUT / 'score.json'
MODEL = 'claude-opus-5-5'
PRICE = (4.0 / 1e6, 20.0 / 1e6)
CAP = 5.00
TOOLS_OFF = ('Bash Edit Write Read Glob Grep WebFetch WebSearch Task NotebookEdit TodoWrite Agent Skill Workflow Monitor')
SYS = ('You are an evidence-flow annotator. You are given one trace and one fact the answer needs. Name the FIRST '
       'checkpoint where that fact is missing, in this order: shard (absent from the owning agent\'s input), '
       'extraction (absent from the extracted pool), board (absent from the transmitted board), answer (present in '
       'the board but the answer is wrong). Return JSON only: {"stage": "sharding|extraction|transmission|aggregation", '
       '"reason": "one sentence"}.')


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def labels():
    cases = {c['key']: c for c in json.loads(B.CASES.read_text())}
    carriers = {}
    for l in CARRIERS.read_text().splitlines():
        if not l.strip():
            continue
        e = json.loads(l)
        if e.get('event') != 'result' or not e.get('success'):
            continue
        key = e['key'].split('/carriers/')[0]
        if key.startswith('qa/'):
            key = key[3:]
        if key in cases:
            try:
                carriers[key] = json.loads(e['content'])
            except Exception:
                pass
    rows = []
    for key, c in cases.items():
        car = carriers.get(key)
        if not car:
            continue
        for f in car['facts']:
            def status(cp):
                cs = f.get(cp) or []
                if any(x.get('fidelity') == 'faithful' for x in cs):
                    return 'present'
                return 'partial' if cs else 'absent'
            se, sb = status('extraction'), status('board')
            if se == 'absent':
                st = 'extraction'
            elif sb == 'absent':
                st = 'transmission'
            else:
                st = 'aggregation'
            rows.append({'key': key, 'fact_id': f['fact_id'], 'stage': st,
                         'population': c['population'], 'extraction': se, 'board': sb})
    OUT.mkdir(parents=True, exist_ok=True)
    LAB.write_text(json.dumps(rows, indent=1))
    by = {}
    for r in rows:
        by.setdefault(r['key'], set()).add(r['stage'])
    pops = Counter((r['population'], r['key']) for r in rows)
    keys = {k: pop for (pop, k) in pops}
    multi = Counter()
    n = Counter()
    for k, s in by.items():
        p = keys[k]
        n[p] += 1
        if len(s) > 1:
            multi[p] += 1
    out = {'facts': len(rows), 'by_population': {p: {'traces': n[p], 'multi': multi[p],
                                                     'rate': multi[p] / n[p]} for p in n},
           'all': {'traces': sum(n.values()), 'multi': sum(multi.values()),
                   'rate': sum(multi.values()) / sum(n.values())},
           'rows': rows}
    (OUT / 'counts.json').write_text(json.dumps({k: v for k, v in out.items() if k != 'rows'}, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, indent=1))


def build():
    rows = json.loads(LAB.read_text())
    rng = random.Random(43)
    sample = []
    for st in ('extraction', 'transmission', 'aggregation'):
        pool = [r for r in rows if r['stage'] == st]
        rng.shuffle(pool)
        sample += pool[:10]
    sample = sample[:30]
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE), 'sys_sha256': sha(SYS), 'amendment_sha256': file_sha(PILOTS / 'prereg/Part-B-validated-label-amendment-1.md'),
           'model': MODEL, 'cap_usd': CAP, 'sample': [(r['key'], r['fact_id'], r['stage']) for r in sample]}
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps({k: v for k, v in man.items() if k != 'sample'}, indent=1), len(sample))


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


def run():
    man = json.loads((OUT / 'build_manifest.json').read_text())
    assert file_sha(RULE) == man['rule_sha256'] and sha(SYS) == man['sys_sha256']
    cases = {c['key']: c for c in json.loads(B.CASES.read_text())}
    facts = json.loads(LAB.read_text())
    by = {(r['key'], r['fact_id']): r for r in facts}
    api, cli = spent()
    done = set()
    if RESULTS.exists():
        for l in RESULTS.read_text().splitlines():
            if l.strip():
                e = json.loads(l)
                done.add((e['key'], e['fact_id']))
    tmp = Path(tempfile.mkdtemp(prefix='partb_val_'))
    for key, fid, _ in man['sample']:
        if (key, fid) in done:
            continue
        c = cases[key]
        ftext = next(f['text'] for f in ((B.qwen_facts_carriers().get(key) or {}).get('facts') or {}).get('facts', [])
                     if f['fact_id'] == fid)
        body = (f"Question: {c['question']}\nFact: {ftext}\n"
                f"Shard: {' '.join(str(v) for v in (c.get('source') or {}).values())}\n"
                f"Extraction pool: {' '.join(u.get('text', '') for u in (c.get('extraction') or []))}\n"
                f"Board: {' '.join(u.get('text', '') for u in (c.get('board') or []))}\n"
                f"Final answer: {c.get('answer')}")
        est_in = math.ceil(len(SYS + body) / 4)
        if api + est_in * PRICE[0] + 300 * PRICE[1] > CAP:
            print(json.dumps({'stop': 'cap', 'api': round(api, 6)})); return
        sp = tmp / 'system.txt'; sp.write_text(SYS)
        cmd = ['claude', '-p', body, '--output-format', 'json', '--model', MODEL,
               '--system-prompt-file', str(sp), '--exclude-dynamic-system-prompt-sections',
               '--disallowedTools', TOOLS_OFF]
        p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=900)
        try:
            obj = json.loads(p.stdout)
            u = obj.get('usage') or {}
            pin = u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0)
            cost = pin * PRICE[0] + u.get('output_tokens', 0) * PRICE[1]
            ccost = obj.get('total_cost_usd') or 0.0
            txt = obj.get('result') or ''
        except Exception:
            cost = ccost = 0.0; txt = ''
        if api + cost > CAP:
            print(json.dumps({'stop': 'cap-after-call', 'api': round(api, 6)})); return
        api += cost; cli += ccost
        a, b = txt.find('{'), txt.rfind('}')
        try:
            lab = json.loads(txt[a:b + 1]).get('stage')
        except Exception:
            lab = None
        rec = {'key': key, 'fact_id': fid, 'stage': by[(key, fid)]['stage'], 'opus_stage': lab,
               'population': by[(key, fid)]['population']}
        with RESULTS.open('a') as f:
            f.write(json.dumps(rec) + '\n')
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'result', 'key': f'{key}/{fid}', 'cost_usd': round(cost, 8),
                                'cli_cost_usd': round(ccost, 8)}) + '\n')
        print(json.dumps({'key': key[:20], 'fact': fid, 'stage': rec['stage'], 'opus': lab,
                          'api': round(api, 6)}), flush=True)
    print(json.dumps({'api': round(spent()[0], 6), 'cli': round(spent()[1], 6)}))


def score():
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    ok = [r for r in rows if r['opus_stage'] in ('sharding', 'extraction', 'transmission', 'aggregation')]
    agree = sum(1 for r in ok if r['opus_stage'] == r['stage'])
    a = [r['stage'] for r in ok]; b = [r['opus_stage'] for r in ok]
    n = len(ok)
    po = agree / n if n else 0.0
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n) if n else 0.0
    kappa = (po - pe) / (1 - pe) if n and pe < 1 else None
    api, cli = spent()
    out = {'n': n, 'agreement': po, 'kappa': kappa, 'api_equiv_usd': round(api, 6),
           'cli_usd': round(cli, 6)}
    SCORE.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--labels', action='store_true')
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.labels: labels()
    if a.build: build()
    if a.run: run()
    if a.score: score()