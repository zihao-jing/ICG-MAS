"""Part B step 2: Opus runs on the 30 fresh validation traces through the local CLI, scored under the
multi-stage truth rule against the stored Gemini labels.

Rule `prereg/Part-B-step2-truth-rule.md` (hashed before any call). Cap $0.50 at API-equivalent prices.

    ./run.sh python -m scripts.part_b_step2_cli --build
    ./run.sh python -m scripts.part_b_step2_cli --run
    ./run.sh python -m scripts.part_b_step2_cli --score
"""
import argparse
import hashlib
import json
import random
import re
import subprocess
import tempfile
from pathlib import Path

from src.audit.judge_render import trace_text

ROOT = Path(__file__).resolve().parent.parent
K1 = ROOT / 'rebuttal/pilots/20261114_part_b_k1'
OUT = ROOT / 'rebuttal/pilots/20261115_part_b_step2'
RULE = ROOT / 'rebuttal/pilots/prereg/Part-B-step2-truth-rule.md'
PROMPT = ROOT / 'rebuttal/judge/E2-judge-v2.json'
ITEMS = K1 / 'extra/fresh_items.json'
GEMINI = K1 / 'reval/gemini.json'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
SCORE = OUT / 'score.json'
REPORT = OUT / 'report.md'
MODEL = 'claude-opus-5-5'
PRICE = (4.0 / 1e6, 20.0 / 1e6)
CAP = 2.5
TOOLS_OFF = ('Bash Edit Write Read Glob Grep WebFetch WebSearch Task NotebookEdit TodoWrite '
             'Agent Skill Workflow Monitor')


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
            api += x.get('api_equiv_usd', 0.0)
            cli += x.get('cost_usd', 0.0)
    return api, cli


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE),
           'prompt_sha256': file_sha(PROMPT), 'items_sha256': file_sha(ITEMS),
           'gemini_labels_sha256': file_sha(GEMINI), 'model': MODEL, 'transport': 'claude-cli',
           'cap_usd_api_equiv': CAP, 'traces': 30,
           'amendment_sha256': file_sha(Path('rebuttal/pilots/prereg/Part-B-step2-amendment-1.md'))}
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def check():
    m = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == m['rule_sha256'], 'rule changed'
    am = Path('rebuttal/pilots/prereg/Part-B-step2-amendment-1.md')
    assert file_sha(am) == m['amendment_sha256'], 'amendment changed'
    assert file_sha(PROMPT) == m['prompt_sha256'], 'prompt changed'
    assert file_sha(ITEMS) == m['items_sha256'], 'items changed'
    return m


def parse(text):
    s = re.sub(r'^```(?:json)?\s*|\s*```$', '', (text or '').strip())
    a, b = s.find('{'), s.rfind('}')
    if a < 0 or b < a:
        return None
    try:
        o = json.loads(s[a:b + 1])
    except Exception:
        return None
    return o if o.get('class') in ('single', 'multiple', 'indeterminate') else None


def run():
    check()
    prof = json.loads(PROMPT.read_text())
    items = json.loads(ITEMS.read_text())['items']
    done = set()
    if RESULTS.exists():
        done = {(x.get('trace_id') or x.get('key')) for x in json.loads(RESULTS.read_text())['items']}
    api, cli = spent()
    tmp = Path(tempfile.mkdtemp(prefix='partb_step2_'))
    for it in items:
        if it['trace_id'] in done:
            continue
        sysmsg = prof['system']
        user = prof['user_template'].format(trace=trace_text(it['trace']))
        sp = tmp / 'system.txt'
        sp.write_text(sysmsg)
        cmd = ['claude', '-p', user, '--output-format', 'json', '--model', MODEL,
               '--system-prompt-file', str(sp), '--exclude-dynamic-system-prompt-sections',
               '--disallowedTools', TOOLS_OFF]
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'intent', 'key': it['trace_id'], 'model': MODEL,
                                'transport': 'claude-cli', 'system_sha256': sha(sysmsg),
                                'user_sha256': sha(user)}) + '\n')
        p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=900)
        rec = {'event': 'result', 'key': it['trace_id'], 'model': MODEL, 'transport': 'claude-cli',
               'returncode': p.returncode, 'stderr': p.stderr[-500:]}
        try:
            obj = json.loads(p.stdout)
            u = obj.get('usage') or {}
            # API-equivalent: uncached prompt tokens at $4/M (cache creation counts as prompt)
            pin = (u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0)
                   + u.get('cache_read_input_tokens', 0))
            pout = u.get('output_tokens', 0)
            rec['api_equiv_usd'] = round(pin * PRICE[0] + pout * PRICE[1], 8)
            rec['cost_usd'] = round(obj.get('total_cost_usd') or 0.0, 8)
            rec['usage'] = u
            lab = parse(obj.get('result'))
            rec['parsed'] = lab
            rec['class'] = lab.get('class') if lab else None
            rec['stages'] = sorted({d.get('stage') for d in (lab or {}).get('defects') or []})
            api += rec['api_equiv_usd']; cli += rec['cost_usd']
        except json.JSONDecodeError:
            rec['class'] = None
        with CALLS.open('a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        items_out = json.loads(RESULTS.read_text())['items'] if RESULTS.exists() else []
        items_out.append({k: rec.get(k) for k in ('key', 'class', 'stages', 'api_equiv_usd', 'cost_usd')})
        RESULTS.write_text(json.dumps({'items': items_out}, indent=1))
        print(json.dumps({'key': it['trace_id'], 'class': rec.get('class'),
                          'api_equiv': round(api, 6), 'cli': round(cli, 6)}), flush=True)
        if api > CAP:
            print(json.dumps({'stop': 'api-equivalent cap', 'api_equiv': round(api, 6)}))
            return


def boot(vals, draws=2000, seed=43):
    rng = random.Random(seed)
    out = sorted(sum(vals[rng.randrange(len(vals))] for _ in vals) / len(vals) for _ in range(draws))
    return out[int(0.025 * draws)], out[int(0.975 * draws) - 1]


def kappa(a, b):
    n = len(a); po = sum(x == y for x, y in zip(a, b)) / n
    from collections import Counter
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def score():
    check()
    items = json.loads(ITEMS.read_text())['items']
    mine = {x['key']: x for x in json.loads(RESULTS.read_text())['items']}
    gem = {x['trace_id']: x for x in json.loads(GEMINI.read_text())}
    rows = []
    for it in items:
        t = it['trace_id']
        if t not in mine or t not in gem:
            continue
        rows.append((t, mine[t], gem[t]))
    cls_mine = [r[1]['class'] for r in rows]
    cls_gem = [r[2]['parsed']['class'] for r in rows]
    agree = [a == b for a, b in zip(cls_mine, cls_gem)]
    k = kappa(cls_mine, cls_gem)
    lo, hi = boot([1.0 if a else 0.0 for a in agree])
    # truth rule: Gemini right if any of its stages is in Opus's stage set
    def stages(x):
        return set(x.get('stages') or []) or {d.get('stage') for d in (x.get('parsed') or {}).get('defects') or []}
    right = sum(1 for _, m, g in rows
                if stages(m) & {d.get('stage') for d in (g['parsed'].get('defects') or [])})
    api, cli = spent()
    out = {'n': len(rows), 'class_agreement': sum(agree) / len(rows) if rows else None,
           'class_agreement_ci': [lo, hi], 'kappa': k, 'truth_rule_right': right,
           'api_equiv_usd': round(api, 6), 'cli_usd': round(cli, 6)}
    SCORE.write_text(json.dumps(out, indent=1))
    lines = ['# Part B step 2: Opus via CLI on the 30 validation traces', '',
             '2026-11-15. Rule `Part-B-step2-truth-rule.md` (sha `%s...`), prompt `E2-judge-v2.json`. '
             'Opus 5.5 through `claude -p`, API-equivalent cost $%.4f (CLI charge $%.4f), cap $0.50.'
             % (file_sha(RULE)[:8], api, cli), '',
             '| quantity | value |', '| --- | ---: |',
             '| traces | %d |' % out['n'],
             '| class agreement | %s |' % (('%.3f [%.3f, %.3f]' %
                                             (out['class_agreement'], lo, hi))
                                            if out['class_agreement'] is not None else '—'),
             '| kappa | %.3f |' % k,
             '| Gemini labels naming a valid stage | %d/%d |' % (right, out['n']), '',
             'The truth rule scores a method right when it names any stage the reference names. The class'
             ' columns are the original single/multiple call. Transport deviation: this route is the local'
             ' CLI, not the OpenRouter API; per-call costs use the API-equivalent price and the CLI charge is'
             ' shown beside it.', '', '## Ledger', 'API-equivalent $%.6f; CLI $%.6f.' % (api, cli)]
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.run:
        run()
    if a.score:
        score()