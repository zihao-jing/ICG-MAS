"""Part B fact-level stages: presence rule labels at $0, Opus CLI reference on a stratified sample (cap $1).

    ./run.sh python -m scripts.part_b_factlevel --build
    ./run.sh python -m scripts.part_b_factlevel --run
    ./run.sh python -m scripts.part_b_factlevel --score
"""
import argparse, hashlib, json, math, random, subprocess, tempfile
from pathlib import Path
from src.audit.e4_fix_gates import STOP, recall
from src.eval.evaluate import normalize

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_part_b_factlevel'
RULE = ROOT / 'rebuttal/pilots/prereg/Part-B-factlevel.md'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
SCORE = OUT / 'score.json'
REPORT = OUT / 'report.md'
MODEL = 'claude-opus-5-5'
PRICE = (4.0 / 1e6, 20.0 / 1e6)
CAP = 1.0
TOOLS_OFF = ('Bash Edit Write Read Glob Grep WebFetch WebSearch Task NotebookEdit TodoWrite Agent Skill Workflow Monitor')
SYS = ('You are an evidence-flow annotator. You are given one trace and one fact the answer needs. Name the FIRST '
       'checkpoint where that fact is missing, in this order: shard (absent from the owning agent\'s input), '
       'extraction (absent from the extracted pool), board (absent from the transmitted board), answer (present in '
       'the board but the answer is wrong). Return JSON only: {"stage": "sharding|extraction|transmission|aggregation", '
       '"reason": "one sentence"}.')


def sha(s): return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists(): return 0.0, 0.0
    api = cli = 0.0
    for l in CALLS.read_text().splitlines():
        if not l.strip(): continue
        x = json.loads(l)
        if x.get('event') == 'result':
            api += x.get('cost_usd', 0.0); cli += x.get('cli_cost_usd', 0.0)
    return api, cli


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE), 'sys_sha256': sha(SYS),
           'model': MODEL, 'cap_usd': CAP, 'sample': 'stratified 3 per predicted stage, seed 43'}
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def labels():
    from scripts.b5_attribution_2x2 import CASES, qwen_facts_carriers
    cases = {c['key']: c for c in json.loads(CASES.read_text())}
    qf = qwen_facts_carriers()
    def present(text, fact):
        ft = [t for t in normalize(fact) if t not in STOP]
        return True if not ft else recall(text, ' '.join(ft)) >= 0.8
    out = []
    for k, c in cases.items():
        facts = ((qf.get(k) or {}).get('facts') or {}).get('facts') or []
        src = ' '.join(str(v) for v in (c.get('source') or {}).values())
        ext = ' '.join(u.get('text', '') for u in (c.get('extraction') or []))
        board = ' '.join(u.get('text', '') for u in (c.get('board') or []))
        for f in facts:
            if not present(src, f['text']): st = 'sharding'
            elif not present(ext, f['text']): st = 'extraction'
            elif not present(board, f['text']): st = 'transmission'
            else: st = 'aggregation'
            out.append({'key': k, 'fact_id': f['fact_id'], 'fact': f['text'], 'rule_stage': st,
                        'question': c.get('question'), 'source': c.get('source'),
                        'extraction': c.get('extraction'), 'board': c.get('board'), 'answer': c.get('answer')})
    return out


def run():
    man = json.loads((OUT / 'build_manifest.json').read_text())
    assert file_sha(RULE) == man['rule_sha256'] and sha(SYS) == man['sys_sha256']
    rows = labels()
    rng = random.Random(43)
    sample = []
    for st in ('sharding', 'extraction', 'transmission', 'aggregation'):
        pool = [r for r in rows if r['rule_stage'] == st]
        rng.shuffle(pool)
        sample += pool[:3]
    api, cli = spent()
    tmp = Path(tempfile.mkdtemp(prefix='factlevel_'))
    for r in sample:
        body = (f"Question: {r['question']}\nFact: {r['fact']}\n"
                f"Shard: {r['source']}\nExtraction pool: {r['extraction']}\nBoard: {r['board']}\n"
                f"Final answer: {r['answer']}")
        sp = tmp / 'system.txt'; sp.write_text(SYS)
        cmd = ['claude', '-p', body, '--output-format', 'json', '--model', MODEL,
               '--system-prompt-file', str(sp), '--exclude-dynamic-system-prompt-sections',
               '--disallowedTools', TOOLS_OFF]
        p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=900)
        try:
            obj = json.loads(p.stdout); u = obj.get('usage') or {}
            pin = u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0)
            cost = pin * PRICE[0] + u.get('output_tokens', 0) * PRICE[1]
            ccost = obj.get('total_cost_usd') or 0.0
            txt = obj.get('result') or ''
        except Exception:
            cost = ccost = 0.0; txt = ''
        if api + cost > CAP:
            print(json.dumps({'stop': 'cap', 'api': round(api, 4)})); return
        a, b = txt.find('{'), txt.rfind('}')
        try: lab = json.loads(txt[a:b + 1])
        except Exception: lab = None
        rec = {'key': r['key'], 'fact_id': r['fact_id'], 'rule_stage': r['rule_stage'],
               'opus_stage': (lab or {}).get('stage'), 'raw': txt[:300]}
        api += cost; cli += ccost
        with RESULTS.open('a') as f: f.write(json.dumps(rec) + '\n')
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'result', 'key': r['key'] + '/' + r['fact_id'],
                                'cost_usd': round(cost, 8), 'cli_cost_usd': round(ccost, 8)}) + '\n')
        print(json.dumps({'key': r['key'][:20], 'fact': r['fact_id'], 'rule': r['rule_stage'],
                          'opus': rec['opus_stage'], 'api': round(api, 4)}), flush=True)
    print(json.dumps({'api': round(api, 4), 'cli': round(cli, 4)}))


def score():
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    ok = [r for r in rows if r['opus_stage'] in ('sharding', 'extraction', 'transmission', 'aggregation')]
    agree = sum(1 for r in ok if r['opus_stage'] == r['rule_stage'])
    api, cli = spent()
    out = {'n': len(ok), 'rule_vs_opus_agreement': agree / len(ok) if ok else None,
           'api_equiv_usd': round(api, 6), 'cli_usd': round(cli, 6)}
    SCORE.write_text(json.dumps(out, indent=1))
    lines = ['# Part B fact-level labels: presence rule vs Opus reference (stratified sample)', '',
             '2026-11-15. Rule `Part-B-factlevel.md` (sha `%s...`); Opus 5.5 via CLI. API-equivalent $%.4f, CLI $%.4f, cap $1.00.'
             % (file_sha(RULE)[:8], api, cli), '',
             '| quantity | value |', '| --- | ---: |', '| facts labelled | %d |' % len(ok),
             '| presence rule vs Opus | %d/%d = %.3f |' % (agree, len(ok), out['rule_vs_opus_agreement'] or 0), '',
             'The presence rule is used to derive per-fact stages on all 277 facts only if this sample supports it. '
             'Per-fact method accuracy is reported only after that check.', '', '## Ledger',
             'API-equivalent $%.6f; CLI $%.6f.' % (api, cli)]
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true'); ap.add_argument('--run', action='store_true'); ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.build: build()
    if a.run: run()
    if a.score: score()