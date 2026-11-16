"""Score the paper's two evaluators against author labels on the E1 anchor (Paper-evaluators-v1).

(a) Lexical coverage: `scripts.compute_audit_metrics.align_gold_to_transmitted`, unchanged, called per
    candidate unit to obtain its score, and over the checkpoint to obtain `covered`.
(b) Alignment judge: Qwen-235B, temperature 0, the prompt printed in `app_main.tex:405-440`, one call per
    eligible row, no retry, JSON only, `max_tokens` 512.

Eligible judge rows: the author fact's single gold unit (via `source_ids`) and the unique argmax lexical
candidate at the checkpoint (pool or board). Ties are excluded.

  python -m scripts.run_paper_evaluators --pilot --execute
  python -m scripts.run_paper_evaluators --execute          (full run; only after the pilot is seen)
"""
import argparse, datetime, hashlib, json, random, re
from collections import Counter, defaultdict
from pathlib import Path

from src.audit.pilot_common import CallLedger, digest, freeze
from scripts.compute_audit_metrics import align_gold_to_transmitted

RET = Path('rebuttal/annotation/returns')
PMAP = Path('rebuttal/pilots/20261108_review8/packet_private_map.json')
N80 = Path('rebuttal/pilots/20261108_review6/e1_n80_locked_manifest.json')
PREREG = Path('rebuttal/pilots/prereg/Paper-evaluators-v1.md')
CFG = Path('rebuttal/pilots/configs/Paper-evaluators-v1.json')
OUT_PILOT = Path('rebuttal/results/batch1/Paper_evaluators_pilot')
OUT_FULL = Path('rebuttal/results/batch1/Paper_evaluators_full')
SEED = 42

# prompt text exactly as in app_main.tex:405-440 (alignment judge, system and user)
SYSTEM = ("You are an evidence alignment judge.\n\n"
          "Given a gold evidence unit and a candidate transmitted unit, classify\n"
          "their relationship.\n\n"
          "Labels:\n"
          "- EXACT: candidate preserves the same meaning and all key entities,\n"
          "  numbers, dates, and constraints.\n"
          "- PARAPHRASE: candidate preserves the same meaning with different wording.\n"
          "- PARTIAL: candidate preserves some information but omits a key constraint.\n"
          "- DISTORTED: candidate is related but changes a key entity, number,\n"
          "  date, relation, negation, or condition.\n"
          "- NO_MATCH: candidate does not express the gold evidence.\n\n"
          "Return JSON only:\n"
          '{"label": "EXACT|PARAPHRASE|PARTIAL|DISTORTED|NO_MATCH",\n'
          ' "confidence": 0.0, "reason": "short explanation"}')
USER = "Gold unit: {gold}\nCandidate unit: {cand}\n\nClassify the relationship.\nReturn JSON only:\n" \
       '{"label": "...", "confidence": ..., "reason": "..."}'  # USER is built below by substitution, not .format
LABELS = {'EXACT', 'PARAPHRASE', 'PARTIAL', 'DISTORTED', 'NO_MATCH'}
COLLAPSE = {'EXACT': ('yes', 'faithful'), 'PARAPHRASE': ('yes', 'faithful'),
            'PARTIAL': ('yes', 'partial'), 'DISTORTED': ('yes', 'distorted'),
            'NO_MATCH': ('no', 'absent')}


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rows():
    labels = {a: {r['display_name']: r for r in json.loads(
        (RET / f'E1anchor_{a}_labelling-v1.0.json').read_text())} for a in 'ABCD'}
    pmap = json.loads(PMAP.read_text())
    n80 = json.loads(N80.read_text())
    strata = {i: h for h, v in n80['strata'].items() for i in v['ids']}
    war = {h: v['weight'] for h, v in json.loads(
        Path('rebuttal/pilots/20261108_review7/e1_anchor_locked_manifest.json').read_text())['strata'].items()}
    out = []
    for a, b in (('A', 'B'), ('C', 'D')):
        for name in sorted(set(labels[a]) & set(labels[b])):
            ra, rb = labels[a][name], labels[b][name]
            inst = pmap[ra['item_id']]['instance_id']
            h = strata[inst]
            t = ra['trace']
            gold_units = {s['support_id']: s['text'] for s in t['source_supports']}
            for who, r in (('A', ra), ('B', rb)):
                facts = json.loads(r['answers']['critical_facts_json'])
                cars = {(c['fact_id'], c['checkpoint']): c for c in json.loads(r['answers']['carriers_json'])}
                for fa in facts:
                    src = fa.get('source_ids') or []
                    if len(src) != 1 or src[0] not in gold_units:
                        continue
                    gold = gold_units[src[0]]
                    for cp, cpk in (('pool', 'extraction'), ('board', 'board')):
                        car = cars.get((fa['fact_id'], cp))
                        fid = (car or {}).get('fidelity') or 'absent'
                        if fid == 'uncertain':
                            continue
                        unit_ids = [u['unit_id'] for u in t['checkpoints'][cpk]]
                        unit_text = [u['text'] for u in t['checkpoints'][cpk]]
                        scores = [align_gold_to_transmitted([(0, fa['text'])], [ut])[0]['score'] for ut in unit_text]
                        top = max(scores) if scores else 0.0
                        win = [i for i, s in enumerate(scores) if s == top]
                        covered = align_gold_to_transmitted([(0, fa['text'])], unit_text)[0]['covered']
                        out.append({'row_id': digest(['paper-evaluators', inst, name, who, fa['fact_id'], cp]),
                                    'instance': inst, 'stratum': h, 'weight': war[h], 'trace': name,
                                    'annotator': who, 'fact_id': fa['fact_id'], 'checkpoint': cp,
                                    'fact_text': fa['text'], 'gold_text': gold, 'author_fidelity': fid,
                                    'author_presence': 'yes' if fid != 'absent' else 'no',
                                    'lexical_covered': covered,
                                    'unique_argmax': len(win) == 1,
                                    'candidate_id': unit_ids[win[0]] if len(win) == 1 else None,
                                    'candidate_text': unit_text[win[0]] if len(win) == 1 else None})
    return out


def pilot_sample(rs, n=48):
    """Fixed pilot: all partial rows, then absent rows, then faithful rows; seed 42 within each class."""
    rng = random.Random(SEED)
    chosen, picked = [], set()
    for cls in ('partial', 'absent'):
        pool = [r for r in rs if r['unique_argmax'] and r['author_fidelity'] == cls and r['row_id'] not in picked]
        rng.shuffle(pool)
        for r in pool:
            if len(chosen) >= (n - 2 if cls == 'faithful' else n):
                break
            chosen.append(r); picked.add(r['row_id'])
    rest = [r for r in rs if r['unique_argmax'] and r['author_fidelity'] == 'faithful' and r['row_id'] not in picked]
    rng.shuffle(rest)
    chosen += rest[:max(0, n - len(chosen))]
    return sorted(chosen, key=lambda r: r['row_id'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--execute', action='store_true')
    a = ap.parse_args()
    cfg = json.loads(CFG.read_text())
    assert cfg['prereg_sha256'] == sha(PREREG), 'pre-registration changed since it was frozen'
    assert cfg['prompt_sha256'] == digest([SYSTEM, USER]) == cfg['paper_prompt_sha256']
    all_rows = rows()
    elig = [r for r in all_rows if r['unique_argmax']]
    plan = pilot_sample(elig) if a.pilot else elig
    out = OUT_PILOT if a.pilot else OUT_FULL
    print(json.dumps({'rows_all': len(all_rows), 'eligible': len(elig), 'selected': len(plan),
                      'checkpoints': dict(Counter(r['checkpoint'] for r in plan)),
                      'author_fidelity': dict(Counter(r['author_fidelity'] for r in plan)),
                      'lexical_covered': dict(Counter(r['lexical_covered'] for r in plan)),
                      'execute': a.execute, 'start_utc': utc()}), flush=True)
    if not a.execute:
        return
    out.mkdir(parents=True, exist_ok=True)
    ledger = CallLedger(out, cfg, PREREG, len(plan))
    done = {'planned': len(plan), 'valid': 0, 'failed': 0, 'failed_reason': Counter(), 'rows': plan,
            'model': cfg['model'], 'temperature': cfg['temperature'], 'max_tokens': cfg['max_tokens'],
            'pilot': a.pilot, 'start_utc': utc()}
    try:
        for i, r in enumerate(plan, 1):
            msgs = [{'role': 'system', 'content': SYSTEM},
                    {'role': 'user', 'content': USER.replace('{gold}', r['gold_text']).replace('{cand}', r['candidate_text'])}]
            try:
                raw = ledger.call(r['row_id'], cfg['model'], msgs, max_tokens=cfg['max_tokens'],
                                  temperature=0, response_format={'type': 'json_object'})
                label = json.loads(raw)['label'].strip().upper()
                if label not in LABELS:
                    raise ValueError('label not in the five')
                r['judge_label'] = label
                r['judge_presence'], r['judge_fidelity'] = COLLAPSE[label]
                r['judge_valid'] = True
                done['valid'] += 1
            except Exception as exc:
                r['judge_label'] = None
                r['judge_valid'] = False
                r['judge_error'] = type(exc).__name__ + ': ' + str(exc)
                done['failed'] += 1
                done['failed_reason'][type(exc).__name__] += 1
            print(f"{i}/{len(plan)} {'ok' if r['judge_valid'] else 'failed'} {r['judge_label']} "
                  f"{r['instance']} {r['checkpoint']} {utc()}", flush=True)
    finally:
        ledger.close()
    res = [json.loads(l) for l in (out / 'calls.jsonl').read_text().splitlines() if l.strip()]
    res = [x for x in res if x['event'] == 'result']
    done.update({'calls': len(res), 'calls_failed': sum(not x['success'] for x in res),
                 'cost_usd': round(sum(x.get('cost_usd') or 0 for x in res), 6), 'end_utc': utc(),
                 'runner_sha256': sha(__file__), 'config_sha256': digest(cfg),
                 'prereg_sha256': sha(PREREG)})
    (out / 'rows.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in plan))
    (out / 'summary.json').write_text(json.dumps(done, indent=2, default=str) + '\n')
    print(json.dumps({k: done[k] for k in ('planned', 'valid', 'failed', 'calls', 'calls_failed', 'cost_usd')}))


if __name__ == '__main__':
    main()