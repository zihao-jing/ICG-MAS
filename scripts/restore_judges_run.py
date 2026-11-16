"""Restore check: Sonnet 5.5 judge on all 184 restore-pilot answers; Opus 5.5 adjudicates Sonnet-vs-Gemini disagreements.

Rule: rebuttal/pilots/prereg/Restore-judges-Sonnet-Opus-v1.md (hashed in build_manifest.json before any call).

    .conda-env/bin/python scripts/restore_judges_run.py --build   # writes prompt and items, hashes them, no calls
    .conda-env/bin/python scripts/restore_judges_run.py --run     # CLI calls, caps $2 Sonnet / $3 Opus
    .conda-env/bin/python scripts/restore_judges_run.py --score   # no calls
"""
import argparse
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TOOLS_OFF = ('Bash Edit Write Read Glob Grep WebFetch WebSearch Task NotebookEdit TodoWrite '
             'Agent Skill Workflow Monitor')  # same string as scripts/opus_checker_check.py

PILOTS = ROOT / 'rebuttal/pilots'
RESTORE = PILOTS / '20261116_restore_equiv_gemini/restore_results.jsonl'
CASES = PILOTS / '20261113_restore_source/cases.json'
OUT = PILOTS / '20261116_restore_judges_sonnet_opus'
RULE = PILOTS / 'prereg/Restore-judges-Sonnet-Opus-v1.md'
PROMPT = OUT / 'prompt.txt'
ITEMS = OUT / 'items.json'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
SONNET = 'claude-sonnet-5-5'
OPUS = 'claude-opus-5-5'
CAP = {'sonnet': 2.0, 'opus': 3.0}

SYSTEM = (
    "You are a strict answer checker. You get a QUESTION, a GOLD ANSWER and a SYSTEM ANSWER. "
    "Decide whether the SYSTEM ANSWER gives the GOLD ANSWER: the same entity, number or date. "
    "Ignore capitalisation, articles and punctuation. An answer that names a different entity, "
    "says it cannot tell, or is empty is incorrect. "
    'Reply with one JSON object only: {"verdict": "correct"} or {"verdict": "incorrect"}.'
)


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def norm(s):
    import re
    s = re.sub(r'\b(the|a|an)\b', ' ', (s or '').lower())
    return ' '.join(re.sub(r'[^a-z0-9 ]+', ' ', s).split())


def build():
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    OUT.mkdir(parents=True, exist_ok=True)
    PROMPT.write_text(SYSTEM)
    cases = {c['key']: c for c in json.loads(CASES.read_text())}
    rows = [json.loads(l) for l in RESTORE.read_text().splitlines() if l.strip()]
    items = []
    for r in rows:
        c = cases[r['key']]
        assert norm(c['gold']) == norm(r['gold']), r['key']
        items.append({'item_id': f"{r['key']}|{r['arm']}", 'key': r['key'], 'arm': r['arm'],
                      'question': c['question'], 'gold': c['gold'], 'answer': r['answer'],
                      'gemini': 'correct' if r['verdict'] == 'EQUIVALENT' else 'incorrect'})
    ITEMS.write_text(json.dumps(items, indent=1, ensure_ascii=False))
    man = {'recorded_before_any_call': True, 'rule': str(RULE.relative_to(ROOT)),
           'rule_sha256': sha_bytes(RULE.read_bytes()), 'prompt_sha256': sha_bytes(PROMPT.read_bytes()),
           'items_sha256': sha_bytes(ITEMS.read_bytes()), 'n_items': len(items),
           'arms': dict(Counter(i['arm'] for i in items)), 'caps_usd': CAP}
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def check_manifest():
    man = json.loads(MANIFEST.read_text())
    assert sha_bytes(RULE.read_bytes()) == man['rule_sha256'], 'rule changed'
    assert sha_bytes(PROMPT.read_bytes()) == man['prompt_sha256'], 'prompt changed'
    assert sha_bytes(ITEMS.read_bytes()) == man['items_sha256'], 'items changed'
    return man


def spent(model):
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result' and json.loads(l).get('model') == model)


def parse_verdict(text):
    import re
    for raw in reversed(re.findall(r'\{[^{}]*\}', text or '')):
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        v = str(d.get('verdict', '')).lower().strip()
        if v in ('correct', 'incorrect'):
            return v
    return None


def call(model, user, tmp):
    cmd = ['claude', '-p', user, '--output-format', 'json', '--model', model,
           '--system-prompt-file', str(PROMPT), '--exclude-dynamic-system-prompt-sections',
           '--disallowedTools', TOOLS_OFF]
    p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=900)
    try:
        obj = json.loads(p.stdout)
    except json.JSONDecodeError:
        return None, '', 0.0, {}
    usage = obj.get('usage') or {}
    cost = float(obj.get('total_cost_usd') or 0.0)
    return parse_verdict(obj.get('result')), obj.get('result') or '', cost, usage


def log(rec):
    with CALLS.open('a') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def run():
    check_manifest()
    items = json.loads(ITEMS.read_text())
    done = {}
    if RESULTS.exists():
        for l in RESULTS.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                done[r['item_id']] = r
    tmp = Path(tempfile.mkdtemp(prefix='restore_judge_'))
    # Stage 1: Sonnet on all items.
    total = spent(SONNET)
    for it in items:
        if it['item_id'] in done and done[it['item_id']].get('sonnet') is not None:
            continue
        if total + 0.01 > CAP['sonnet']:
            print(json.dumps({'stop': 'sonnet cap', 'spent': round(total, 6)}))
            break
        user = f"QUESTION\n{it['question']}\n\nGOLD ANSWER\n{it['gold']}\n\nSYSTEM ANSWER\n{it['answer']}"
        log({'event': 'intent', 'item_id': it['item_id'], 'model': SONNET, 'transport': 'claude-cli'})
        v, text, cost, usage = call(SONNET, user, tmp)
        if v is None:
            v, text, cost2, usage = call(SONNET, user, tmp)  # one retry
            cost += cost2
        total += cost
        log({'event': 'result', 'item_id': it['item_id'], 'model': SONNET, 'verdict': v, 'content': text,
             'cost_usd': round(cost, 8), 'usage': usage})
        rec = done.get(it['item_id'], {'item_id': it['item_id'], 'key': it['key'], 'arm': it['arm'],
                                       'gemini': it['gemini']})
        rec['sonnet'] = v
        done[it['item_id']] = rec
        print(json.dumps({'item': it['item_id'][:14], 'sonnet': v, 'gemini': it['gemini'],
                          'spent_sonnet': round(total, 6)}), flush=True)
    # Stage 2: Opus on Sonnet-vs-Gemini disagreements only.
    total_o = spent(OPUS)
    for it in items:
        rec = done.get(it['item_id'])
        if not rec or rec.get('sonnet') is None or rec['sonnet'] == it['gemini']:
            continue
        if rec.get('opus') is not None:
            continue
        if total_o + 0.12 > CAP['opus']:
            print(json.dumps({'stop': 'opus cap', 'spent': round(total_o, 6)}))
            break
        user = f"QUESTION\n{it['question']}\n\nGOLD ANSWER\n{it['gold']}\n\nSYSTEM ANSWER\n{it['answer']}"
        log({'event': 'intent', 'item_id': it['item_id'], 'model': OPUS, 'transport': 'claude-cli'})
        v, text, cost, usage = call(OPUS, user, tmp)
        total_o += cost
        log({'event': 'result', 'item_id': it['item_id'], 'model': OPUS, 'verdict': v, 'content': text,
             'cost_usd': round(cost, 8), 'usage': usage})
        rec['opus'] = v
        print(json.dumps({'item': it['item_id'][:14], 'opus': v, 'spent_opus': round(total_o, 6)}), flush=True)
    RESULTS.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in done.values()) + '\n')


def wilson(k, n, z=1.959964):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def mcnemar_exact(b, c):
    from math import comb
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def score():
    check_manifest()
    items = json.loads(ITEMS.read_text())
    rows = {r['item_id']: r for r in (json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip())}
    final, sonnet_gem_agree, dis = {}, 0, []
    for it in items:
        r = rows[it['item_id']]
        s = r.get('sonnet')
        if s is None:
            final[it['item_id']] = None
            continue
        if s == it['gemini']:
            sonnet_gem_agree += 1
            final[it['item_id']] = s
        else:
            dis.append(it['item_id'])
            final[it['item_id']] = r.get('opus')
    opus_sides = Counter()
    for iid in dis:
        o = rows[iid].get('opus')
        if o is None:
            opus_sides['no_opus'] += 1
        elif o == rows[iid]['sonnet']:
            opus_sides['with_sonnet'] += 1
        elif o == [i for i in items if i['item_id'] == iid][0]['gemini']:
            opus_sides['with_gemini'] += 1
    out = {'n': len(items), 'sonnet_invalid': sum(1 for r in rows.values() if r.get('sonnet') is None),
           'sonnet_gemini_agree': {'k': sonnet_gem_agree, 'n': len(items),
                                   'rate': round(sonnet_gem_agree / len(items), 3),
                                   'wilson95': wilson(sonnet_gem_agree, len(items))},
           'disagreements': len(dis), 'opus_sides': dict(opus_sides),
           'opus_overturns_sonnet': opus_sides.get('with_gemini', 0)}
    arms = {}
    for arm in ('restore', 'control'):
        ids = [i['item_id'] for i in items if i['arm'] == arm]
        k = sum(1 for i in ids if final.get(i) == 'correct')
        arms[arm] = {'k': k, 'n': len(ids), 'rate': round(k / len(ids), 3), 'wilson95': wilson(k, len(ids))}
        out[f'{arm}_final'] = arms[arm]
        gk = sum(1 for i in items if i['arm'] == arm and i['gemini'] == 'correct')
        out[f'{arm}_gemini_only'] = {'k': gk, 'n': len(ids), 'rate': round(gk / len(ids), 3)}
    # paired McNemar on keys (restore vs control, final labels)
    keys = sorted({i['key'] for i in items})
    b = c = 0
    for key in keys:
        r = final.get(f'{key}|restore') == 'correct'
        cc = final.get(f'{key}|control') == 'correct'
        if r and not cc:
            b += 1
        elif cc and not r:
            c += 1
    out['mcnemar_restore_vs_control'] = {'restore_only_correct': b, 'control_only_correct': c,
                                         'p_exact': mcnemar_exact(b, c), 'p_exact_text': f"{mcnemar_exact(b, c):.2e}"}
    out['cost_usd'] = {'sonnet': round(spent(SONNET), 6), 'opus': round(spent(OPUS), 6)}
    out['human_fallback_triggered'] = out['opus_overturns_sonnet'] > 5
    (OUT / 'score.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def main():
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


if __name__ == '__main__':
    main()
