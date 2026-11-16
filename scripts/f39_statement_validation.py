"""Validate the statement shard check (Haiku 5.5, Sharding-presence-semantic-v1) against Opus 5.5 on a fixed sample.

Rule: rebuttal/pilots/prereg/Statement-check-Opus-validation-v1.md (hashed in build_manifest.json before any call).
Population: the 71 (case, fact) statement-check jobs of rebuttal/pilots/20261115_sharding_semantic.
Reference: claude-opus-5-5 through the claude CLI, empty temp dir, tools off, same system and user prompt as Haiku.

    .conda-env/bin/python scripts/f39_statement_validation.py --sample   # no calls
    .conda-env/bin/python scripts/f39_statement_validation.py --run      # Opus calls, cap $5
    .conda-env/bin/python scripts/f39_statement_validation.py --score    # no calls
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.per_fact_points_build import atomize  # noqa: E402
from scripts.per_fact_points_run import parse  # noqa: E402
from scripts.sharding_semantic_run import jobs, rollup  # noqa: E402

PILOTS = ROOT / 'rebuttal/pilots'
RULE = PILOTS / 'prereg/Statement-check-Opus-validation-v1.md'
PROMPT = PILOTS / 'prereg/per_fact_points_prompt_v1.json'
HAIKU = PILOTS / '20261115_sharding_semantic/results.jsonl'
OUT = PILOTS / '20261116_statement_opus_validation'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
SAMPLE = OUT / 'sample.json'
OPUS = 'claude-opus-5-5'
CAP = 5.00
QUOTA = {'partial': 1, 'present': 14, 'absent': 15}
SEED = '47|f39|'
TOOLS_OFF = 'Bash,Edit,Write,Read,Glob,Grep,WebFetch,WebSearch,NotebookEdit,Task,TodoWrite'


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def haiku_labels():
    return {(r['key'], r['fact_id']): r for r in (json.loads(l) for l in HAIKU.read_text().splitlines() if l.strip())}


def population():
    hl = haiku_labels()
    out = []
    for j in jobs():
        h = hl.get((j['key'], j['fact_id']))
        if h is None:
            continue
        out.append({**j, 'haiku_statuses': h['statuses'], 'haiku_label': h['label']})
    return out


def sample(pop):
    ordered = sorted(pop, key=lambda j: hashlib.sha256((SEED + j['key'] + '|' + j['fact_id']).encode()).hexdigest())
    picked = []
    for lab, n in QUOTA.items():
        cands = [j for j in ordered if j['haiku_label'] == lab]
        picked += cands[:n]
    return picked


def user_text(spec, j):
    atoms = '\n'.join(f'a{i}: {t}' for i, t in enumerate(j['atoms'], 1))
    return spec['user'].format(question=j['question'], fact=j['fact'], atoms=atoms, entries=j['entries'])


def cmd_sample():
    pop = population()
    s = sample(pop)
    print(json.dumps({'population': len(pop), 'population_labels': dict(Counter(j['haiku_label'] for j in pop)),
                      'sample': len(s), 'sample_labels': dict(Counter(j['haiku_label'] for j in s))}, indent=1))
    OUT.mkdir(parents=True, exist_ok=True)
    SAMPLE.write_text(json.dumps([{'key': j['key'], 'fact_id': j['fact_id'], 'haiku_label': j['haiku_label']}
                                  for j in s], indent=1))
    for j in s:
        print(j['haiku_label'], j['key'], j['fact_id'])


def cmd_run():
    man = json.loads(MANIFEST.read_text())
    assert sha_file(RULE) == man['rule_sha256'], 'rule changed after hashing'
    assert sha_file(PROMPT) == man['prompt_sha256'], 'prompt changed after hashing'
    spec = json.loads(PROMPT.read_text())
    s = sample(population())
    done = set()
    if RESULTS.exists():
        done = {(r['key'], r['fact_id']) for r in map(json.loads, RESULTS.read_text().splitlines()) if r.strip()}
    spent = 0.0
    if CALLS.exists():
        spent = sum(json.loads(l).get('cost_usd', 0) for l in CALLS.read_text().splitlines()
                    if l.strip() and json.loads(l).get('event') == 'result')
    tmp = Path(tempfile.mkdtemp(prefix='f39_opus_'))
    sp = tmp / 'system.txt'
    sp.write_text(spec['system'])
    costs = []
    for j in s:
        if (j['key'], j['fact_id']) in done:
            continue
        est = (sum(costs) / len(costs)) if costs else 0.05
        if spent + est > CAP:
            print(json.dumps({'stopped': 'cap', 'spent': round(spent, 6)}))
            return
        user = user_text(spec, j)
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'intent', 'key': j['key'], 'fact': j['fact_id'], 'model': OPUS,
                                'transport': 'claude-cli'}) + '\n')
        cmd = ['claude', '-p', user, '--output-format', 'json', '--model', OPUS,
               '--system-prompt-file', str(sp), '--exclude-dynamic-system-prompt-sections',
               '--disallowedTools', TOOLS_OFF]
        p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=900)
        try:
            obj = json.loads(p.stdout)
        except json.JSONDecodeError:
            obj = None
        if obj is None:
            cost, content, ok = 0.0, '', False
        else:
            cost = float(obj.get('total_cost_usd') or 0.0)
            content, ok = obj.get('result') or '', True
        lab = parse(content, {f'a{i}' for i in range(1, len(j['atoms']) + 1)}) if ok else None
        statuses = {} if lab is None else {k: v['status'] for k, v in lab.items()}
        rec = {'key': j['key'], 'fact_id': j['fact_id'], 'haiku_label': j['haiku_label'],
               'opus_statuses': statuses, 'opus_label': rollup(statuses) if lab is not None else 'invalid',
               'valid': lab is not None, 'cost_usd': round(cost, 8)}
        spent += cost
        costs.append(cost)
        with RESULTS.open('a') as f:
            f.write(json.dumps(rec) + '\n')
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'result', 'key': j['key'], 'fact': j['fact_id'], 'success': ok,
                                'valid': rec['valid'], 'cost_usd': round(cost, 8),
                                'content': content}, ensure_ascii=False) + '\n')
        print(json.dumps({'key': j['key'][:30], 'fact': j['fact_id'], 'haiku': j['haiku_label'],
                          'opus': rec['opus_label'], 'spent': round(spent, 6)}), flush=True)
    print(json.dumps({'spent': round(spent, 6)}))


def kappa(pairs, labels=('present', 'partial', 'absent')):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca = Counter(a for a, _ in pairs)
    cb = Counter(b for _, b in pairs)
    pe = sum((ca[l] / n) * (cb[l] / n) for l in labels)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def wilson(k, n, z=1.959964):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5 / d
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def cmd_score():
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    valid = [r for r in rows if r['valid']]
    n = len(valid)
    pairs = [(r['haiku_label'], r['opus_label']) for r in valid]
    agree = sum(a == b for a, b in pairs)
    bin_agree = sum((a == 'absent') == (b == 'absent') for a, b in pairs)
    h_abs = [r for r in valid if r['haiku_label'] == 'absent']
    abs_prec = sum(r['opus_label'] == 'absent' for r in h_abs)
    out = {
        'rows': len(rows), 'valid_opus': n, 'invalid_opus': len(rows) - n,
        'agreement_3class': {'k': agree, 'n': n, 'rate': round(agree / n, 3) if n else None, 'wilson95': wilson(agree, n)},
        'kappa_unweighted_3class': round(kappa(pairs), 3) if n else None,
        'agreement_absent_vs_not': {'k': bin_agree, 'n': n, 'rate': round(bin_agree / n, 3) if n else None,
                                     'wilson95': wilson(bin_agree, n)},
        'absent_precision_haiku_absent': {'k': abs_prec, 'n': len(h_abs),
                                          'rate': round(abs_prec / len(h_abs), 3) if h_abs else None,
                                          'wilson95': wilson(abs_prec, len(h_abs))},
        'cost_usd': round(sum(r['cost_usd'] for r in rows), 6),
        'confusion_haiku_to_opus': {f'{a}->{b}': sum(1 for x, y in pairs if x == a and y == b)
                                    for a in ('present', 'partial', 'absent') for b in ('present', 'partial', 'absent')},
    }
    bars = {'valid_opus>=28': len(valid) >= 28, 'agreement_3class>=0.85': out['agreement_3class']['rate'] is not None and out['agreement_3class']['rate'] >= 0.85,
            'kappa>=0.70': out['kappa_unweighted_3class'] is not None and out['kappa_unweighted_3class'] >= 0.70,
            'agreement_absent_vs_not>=0.90': out['agreement_absent_vs_not']['rate'] is not None and out['agreement_absent_vs_not']['rate'] >= 0.90,
            'absent_precision>=0.85': out['absent_precision_haiku_absent']['rate'] is not None and out['absent_precision_haiku_absent']['rate'] >= 0.85}
    out['bars'] = bars
    out['pass'] = all(bars.values())
    (OUT / 'score.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.sample:
        cmd_sample()
    if a.run:
        cmd_run()
    if a.score:
        cmd_score()


if __name__ == '__main__':
    main()
