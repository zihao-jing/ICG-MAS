"""Validate the board-presence label on summary-exchange boards (rule: rebuttal/pilots/prereg/Summary-omission-label-v1.md).

    ./.conda-env/bin/python -m scripts.summary_omission_validate --build   # sample + manifest, no calls
    ./.conda-env/bin/python -m scripts.summary_omission_validate --pilot   # one reference call
    ./.conda-env/bin/python -m scripts.summary_omission_validate --run     # remaining calls, cap $1 API-equivalent
    ./.conda-env/bin/python -m scripts.summary_omission_validate --score   # $0
"""
import argparse
import hashlib
import json
import random
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from scripts.per_fact_labeller import parse, render

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / 'rebuttal/pilots'
OUT = P / '20261115_summary_omission_validate'
RULE = P / 'prereg/Summary-omission-label-v1.md'
PROMPT = P / '20261113_sb_presence_validation/labeller_prompt.json'
POP = P / '20261113_sb_presence_full/population.json'
LABELS = P / '20261113_sb_presence_full/results.json'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
SCORE = OUT / 'score.json'
REPORT = OUT / 'report.md'
MODEL = 'claude-opus-5-5'
PRICE = (4.0 / 1e6, 20.0 / 1e6)
CAP = 1.0
PER_STRATUM = 10
SEED = 43
TOOLS_OFF = ('Bash Edit Write Read Glob Grep WebFetch WebSearch Task NotebookEdit TodoWrite '
             'Agent Skill Workflow Monitor')


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca = Counter(a for a, _ in pairs)
    cb = Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def stored_labels():
    """(board key, fact_id) -> stored status for summary-exchange boards."""
    out = {}
    for x in json.loads(LABELS.read_text())['items']:
        if x['checkpoint'] != 'board' or x['protocol'] != 'summary_exchange' or not x.get('labeller'):
            continue
        for fid, d in x['labeller'].items():
            out[(x['key'], fid)] = d['status']
    return out


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    assert file_sha(RULE)  # rule must exist before build
    labels = stored_labels()
    rows = {r['key']: r for r in json.loads(POP.read_text()) if r['checkpoint'] == 'board' and r['protocol'] == 'summary_exchange'}
    strata = {'present': [], 'partial': [], 'absent': []}
    for (k, fid), st in labels.items():
        if k in rows:
            strata[st].append((sha(f'summary-omission-v1|{k}|{fid}'), k, fid))
    sample = []
    for st in ('present', 'partial', 'absent'):
        pool = sorted(strata[st])
        sample += [{'key': k, 'fact_id': fid, 'stored': st} for _, k, fid in pool[:PER_STRATUM]]
    boards = sorted({s['key'] for s in sample})
    man = {'recorded_before_any_call': True, 'rule_file': str(RULE.relative_to(ROOT)), 'rule_sha256': file_sha(RULE),
           'prompt_file': str(PROMPT.relative_to(ROOT)), 'prompt_sha256': file_sha(PROMPT),
           'population_sha256': file_sha(POP), 'labels_sha256': file_sha(LABELS),
           'model': MODEL, 'cap_usd_api_equiv': CAP, 'per_stratum': PER_STRATUM,
           'stratum_sizes_available': {k: len(v) for k, v in strata.items()},
           'sample': sample, 'boards': boards}
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps({'sample': len(sample), 'boards': len(boards),
                      'available': man['stratum_sizes_available']}, indent=1))


def spent():
    api = cli = 0.0
    if CALLS.exists():
        for l in CALLS.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                if r.get('event') == 'result':
                    api += r.get('api_equiv_usd') or 0.0
                    cli += r.get('cost_usd') or 0.0
    return api, cli


def call_board(key, system, user, tmp):
    sp = tmp / 'system.txt'
    sp.write_text(system)
    cmd = ['claude', '-p', user, '--output-format', 'json', '--model', MODEL,
           '--system-prompt-file', str(sp), '--exclude-dynamic-system-prompt-sections',
           '--disallowedTools', TOOLS_OFF]
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'model': MODEL, 'transport': 'claude-cli',
                            'system_sha256': sha(system), 'user_sha256': sha(user)}) + '\n')
    p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=900)
    rec = {'event': 'result', 'key': key, 'model': MODEL, 'transport': 'claude-cli',
           'returncode': p.returncode, 'stderr': p.stderr[-300:]}
    try:
        obj = json.loads(p.stdout)
        u = obj.get('usage') or {}
        pin = u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0)
        pout = u.get('output_tokens', 0)
        rec['api_equiv_usd'] = round(pin * PRICE[0] + pout * PRICE[1], 8)
        rec['cost_usd'] = round(obj.get('total_cost_usd') or 0.0, 8)
        rec['usage'] = u
        rec['content'] = obj.get('result') or ''
        rec['is_error'] = obj.get('is_error')
    except json.JSONDecodeError:
        rec['api_equiv_usd'] = 0.0
        rec['cost_usd'] = 0.0
        rec['content'] = ''
    with CALLS.open('a') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    return rec


def run(limit=None):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(PROMPT) == man['prompt_sha256'], 'prompt changed'
    assert file_sha(POP) == man['population_sha256'], 'population changed'
    spec = json.loads(PROMPT.read_text())
    rows = {r['key']: r for r in json.loads(POP.read_text())}
    done = {}
    if RESULTS.exists():
        done = {x['key']: x for x in json.loads(RESULTS.read_text())['items']}
    todo = [k for k in man['boards'] if k not in done][:limit]
    tmp = Path(tempfile.mkdtemp(prefix='summary_omission_'))
    for k in todo:
        api, _ = spent()
        if api >= CAP:
            print(json.dumps({'stop': 'cap', 'api_equiv': round(api, 6)}), flush=True)
            break
        rec = call_board(k, spec['system'], render(rows[k]), tmp)
        lab = parse(rec.get('content'), {f['fact_id'] for f in rows[k]['facts']})
        done[k] = {'key': k, 'parsed': lab, 'api_equiv_usd': rec.get('api_equiv_usd'), 'cost_usd': rec.get('cost_usd')}
        RESULTS.write_text(json.dumps({'items': list(done.values())}, indent=1, ensure_ascii=False))
        api, cli = spent()
        print(json.dumps({'board': k, 'parsed': lab is not None, 'api_equiv_total': round(api, 6),
                          'cli_total': round(cli, 6)}), flush=True)


def score():
    man = json.loads(MANIFEST.read_text())
    res = {x['key']: x for x in json.loads(RESULTS.read_text())['items']}
    pairs, three, bycl, missing = [], [], {}, 0
    for s in man['sample']:
        lab = (res.get(s['key']) or {}).get('parsed')
        if not lab or s['fact_id'] not in lab:
            missing += 1
            continue
        ref = lab[s['fact_id']]['status']
        pairs.append((s['stored'] == 'present', ref == 'present'))
        three.append((s['stored'], ref))
        bycl.setdefault(s['key'], []).append(pairs[-1])
    n = len(pairs)
    agree = sum(a == b for a, b in pairs)
    kap = kappa(pairs)
    rng = random.Random(SEED)
    keys = list(bycl)
    boots = []
    for _ in range(2000):
        draw = [p for _ in keys for p in bycl[rng.choice(keys)]]
        if draw:
            boots.append(kappa(draw))
    boots.sort()
    kci = [round(boots[int(0.025 * len(boots))], 3), round(boots[int(0.975 * len(boots)) - 1], 3)]
    exact3 = sum(a == b for a, b in three)
    api, cli = spent()
    out = {'rule_sha256': man['rule_sha256'], 'n_facts': n, 'missing': missing, 'boards': len({s['key'] for s in man['sample']}),
           'agreement': {'k': agree, 'n': n, 'rate': round(agree / n, 3), 'wilson95': wilson(agree, n)},
           'kappa': {'value': round(kap, 3), 'cluster_bootstrap95': kci},
           'three_class_agreement': {'k': exact3, 'n': n, 'rate': round(exact3 / n, 3)},
           'confusion_binary': {f'stored_{a}|ref_{b}': sum(1 for p in pairs if p == (a, b))
                                for a in (True, False) for b in (True, False)},
           'verdict': 'PASS' if (agree / n >= 0.80 and kap >= 0.60) else 'FAIL',
           'spend_api_equiv_usd': round(api, 6), 'spend_cli_usd': round(cli, 6)}
    SCORE.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.pilot:
        run(limit=1)
    if a.run:
        run()
    if a.score:
        score()
