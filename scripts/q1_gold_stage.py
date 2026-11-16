"""UEGh Q1: gold-fact audit stage vs proxy-fact audit stage on the same MuSiQue traces (cap $1.50).

Gold supports labelled at the extraction and board checkpoints with the validated point labeller
(`per_fact_points_prompt_v1.json`, Haiku 5.5). Stage derived under the audit's own order.
"""
import json, math, hashlib
from pathlib import Path
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_q1_gold_stage'
PROMPT = ROOT / 'rebuttal/pilots/prereg/per_fact_points_prompt_v1.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
MODEL = 'anthropic/claude-haiku-5.5'
PRICE = (0.10 / 1e6, 0.50 / 1e6)
CAP = 1.5
TOK = 4096


def sha(s): return hashlib.sha256(s.encode()).hexdigest()


def spent():
    if not CALLS.exists(): return 0.0
    return sum(json.loads(l).get('cost_usd', 0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def gold_supports():
    sup = {}
    for p in Path('data/musique').glob('musique_full_v1.0_*.jsonl'):
        for line in p.read_text().splitlines():
            if not line.strip(): continue
            d = json.loads(line)
            g = [x['paragraph_text'] for x in d.get('paragraphs', []) if x.get('is_supporting')]
            if g: sup[d['id']] = g
    return sup


def run():
    prof = json.loads(PROMPT.read_text())
    pop = json.loads(Path('rebuttal/pilots/20261115_proxy_support_mq/population.json').read_text())
    res = json.loads(Path('results/run_qwen235b_musique/results.json').read_text())
    wrong = {r['id'] for r in res['instance_results']['score_ranked_relay'] if not r['correct']}
    pool = [x for x in pop if x['model'] == 'qwen235b' and x['instance_id'] in wrong and x.get('has_extraction')]
    OUT.mkdir(parents=True, exist_ok=True)
    items = {}
    total = spent()
    for t in pool[:30]:
        inst = t['instance_id']
        ext = '\n'.join(u['text'] for u in t['checkpoints'].get('extraction') or [])
        board = '\n'.join(u['text'] for u in t['checkpoints'].get('board') or [])
        gold = (t.get('gold_supports') or [{'text': ''}])[0]['text']
        if not ext or not board or not gold:
            continue
        atoms = [a.strip() for a in gold.replace('\n', ' ').split('. ') if len(a.strip()) > 3]
        rec = {'instance': inst, 'atoms': atoms, 'labels': {}}
        for cp, entries in (('extraction', ext), ('board', board)):
            user = prof['user'].format(question=t['question'], fact=gold,
                                       atoms='\n'.join(atoms), entries=entries)
            est = math.ceil((len(prof['system']) + len(user)) / 4)
            if total + est * PRICE[0] + TOK * PRICE[1] > CAP:
                print(json.dumps({'stop': 'cap', 'spent': round(total, 6)}))
                RESULTS.write_text(json.dumps(items, indent=1))
                return
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'intent', 'key': inst + '/' + cp, 'model': MODEL}) + '\n')
            resp = single_request(APIRequest(system_query=prof['system'], user_query=user, model=MODEL,
                                             max_tokens=TOK, temperature=0))
            u = resp.usage or {}
            cost = u.get('prompt_tokens', est) * PRICE[0] + u.get('completion_tokens', 0) * PRICE[1]
            total += cost
            txt = resp.content or ''
            a, b = txt.find('{'), txt.rfind('}')
            try:
                obj = json.loads(txt[a:b + 1])
                labels = obj.get('atoms') or obj.get('labels') or []
            except Exception:
                labels = []
            rec['labels'][cp] = labels
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'result', 'key': inst + '/' + cp, 'model': MODEL,
                                    'usage': u, 'cost_usd': round(cost, 8)}) + '\n')
        items[inst] = rec
        RESULTS.write_text(json.dumps(items, indent=1))
        print(json.dumps({'instance': inst, 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6), 'n': len(items)}))


def score():
    items = json.loads(RESULTS.read_text())
    from collections import Counter
    STATUS = {'present', 'partial', 'absent'}

    def valid(labels, atoms):
        A = set(atoms)
        return (isinstance(labels, dict) and set(labels) == A
                and all(isinstance(v, dict) and v.get('status') in STATUS
                        and isinstance(v.get('unit_ids'), list) for v in labels.values()))

    stages, lenient, cnt = {}, {}, Counter()
    invalid = 0
    for inst, rec in items.items():
        e, b = rec['labels'].get('extraction'), rec['labels'].get('board')
        ve, vb = valid(e, rec['atoms']), valid(b, rec['atoms'])
        invalid += (not ve) + (not vb)
        if not (ve and vb):
            continue
        for cp, lab in (('extraction', e), ('board', b)):
            for v in lab.values():
                cnt[(cp, v['status'])] += 1
        if any(v['status'] == 'absent' for v in e.values()): stages[inst] = 'extraction'
        elif any(v['status'] == 'absent' for v in b.values()): stages[inst] = 'transmission'
        else: stages[inst] = 'aggregation'
        if any(v['status'] in ('absent', 'partial') for v in e.values()): lenient[inst] = 'extraction'
        elif any(v['status'] in ('absent', 'partial') for v in b.values()): lenient[inst] = 'transmission'
        else: lenient[inst] = 'aggregation'
    out = {'n': len(stages), 'invalid_checkpoints': invalid, 'checkpoints': 2 * len(items),
           'status': {'%s/%s' % k: v for k, v in sorted(cnt.items())},
           'gold_stage': dict(Counter(stages.values())),
           'gold_stage_partial_as_failure': dict(Counter(lenient.values())), 'spend_usd': round(spent(), 6)}
    (OUT / 'score.json').write_text(json.dumps(out, indent=1))
    lines = ['# UEGh Q1: gold-fact audit stage sample', '',
             '2026-11-15. Gold supports labelled at extraction and board with the validated point labeller '
             '(Haiku 5.5), 30 MuSiQue score-ranked traces; spend $%.4f, cap $1.50.' % out['spend_usd'], '',
             '| gold stage | n |', '| --- | ---: |']
    for k, v in out['gold_stage'].items(): lines.append('| %s | %d |' % (k, v))
    lines += ['', 'Read as the audit stage computed from gold facts on the same traces, not accuracy against a true stage.']
    (OUT / 'report.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    import sys
    if '--run' in sys.argv: run()
    if '--score' in sys.argv: score()