"""Build the diagnosis case sheets from frozen E4 artifacts (no model calls).

Reads the frozen action manifests and raw provider responses, recomputes every
score with the project's own scorer, and writes:

    rebuttal/diagnosis/cases.json       machine-readable per-case record
    rebuttal/diagnosis/case_sheets.md   human-readable sheets, board text quoted

Verdict labels (a-f) come from rebuttal/diagnosis/verdicts.json, keyed by
"<group>:<trace_id>", so the classification stays reviewable and the scores
stay recomputed.

    ./run.sh python -I -m scripts.build_e4_diagnosis
"""
import hashlib
import json
import re
import string
from pathlib import Path

from src.eval.evaluate import answer_f1, token_f1
from src.eval.silo_bench_loader import silobench_exact_match
from src.protocols.base import extract_answer, is_refusal

ROOT = Path(__file__).resolve().parent.parent
P1 = ROOT / 'rebuttal/pilots/20261110_e4_phase1/actions_phase1.json'
P23 = ROOT / 'rebuttal/pilots/20261111_e4_phase23/actions_phase23.json'
INS = ROOT / 'rebuttal/pilots/20261110_e4_insert/insertion_plan.json'
RAW1 = ROOT / 'rebuttal/results/batch1/E4_phase1/raw'
RAWI = ROOT / 'rebuttal/results/batch1/E4_direct_insertion/raw'
RAW23 = ROOT / 'rebuttal/results/batch1/E4_phase1b/raw'
OUT = ROOT / 'rebuttal/diagnosis'
VERDICTS = OUT / 'verdicts.json'

CLASSES = {
    'a': 'fact not missing',
    'b': 'present but unused',
    'c': 'scorer rejected a right answer',
    'd': 'model already knew it',
    'e': 'delivery not as intended',
    'f': 'other',
    'ok': 'correct',
}


def digest(s):
    return hashlib.sha256(s.encode()).hexdigest()


def archived_normalize(text):
    """The scorer that produced the archived numbers (punctuation deleted)."""
    text = text.lower()
    text = re.sub(r'\b(a|an|the)\b', ' ', text)
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text.split()


def archived(fn):
    """Run a scorer closure with the archived normalisation restored."""
    import src.eval.evaluate as ev
    old = ev.normalize
    ev.normalize = archived_normalize
    try:
        return fn()
    finally:
        ev.normalize = old


def load_raw(d):
    out = {}
    for f in sorted(d.glob('*.json')):
        recs = json.loads(f.read_text())
        if not recs or 'trace_id' not in recs[0]:
            continue
        out[recs[0]['trace_id']] = {r['arm']: r for r in recs if r.get('arm')}
    return out


def score(answer, instance):
    pred = extract_answer(answer)
    return {
        'answer': answer,
        'pred': pred,
        'f1': round(archived(lambda: answer_f1(pred, instance)), 3),
        'em': round(silobench_exact_match(pred, instance), 3),
        'gold_contained': set(archived_normalize(instance['answer'])) <= set(archived_normalize(pred)),
        'refusal': is_refusal(pred),
    }


def fact_coverage(units, fact_text):
    """Does the supplied text carry the targeted fact?"""
    toks = set(archived_normalize(fact_text))
    if not units:
        return {'contained': False, 'best_f1': 0.0, 'n_units': 0}
    best = archived(lambda: max(token_f1(u, fact_text) for u in units))
    joined = set(archived_normalize(' '.join(units)))
    return {'contained': toks <= joined, 'best_f1': round(best, 3), 'n_units': len(units)}


def carrier_state(row, fact_id):
    for f in row['carriers']['facts']:
        if f['fact_id'] == fact_id:
            return {'extraction': f['extraction'], 'board': f['board']}
    return {'extraction': [], 'board': []}


def instance_dict(row):
    return {'answer': row['gold_answer'], 'answer_aliases': row.get('answer_aliases') or []}


def esc(s):
    return s.replace('|', '\\|').replace('\n', ' ').strip()


def board_table(units, highlight=()):
    lines = ['| unit | agent | text |', '| --- | --- | --- |']
    for u in units:
        mark = ' **→**' if u['unit_id'] in highlight else ''
        lines.append(f"| `{u['unit_id']}`{mark} | {u['agent_id']} | {esc(u['text'])} |")
    return '\n'.join(lines)


def answer_table(arms, structured=False):
    head = '| arm | final answer (ANSWER line) | '
    rule = '| --- | --- |'
    if structured:
        head += 'exact match | F1 (not valid for dicts) | refusal |'
        rule += ' --- | --- | --- |'
    else:
        head += 'F1 | gold contained | refusal |'
        rule += ' --- | --- | --- |'
    lines = [head, rule]
    for name, s in arms:
        a = esc(s['pred'])
        if len(a) > 220:
            a = a[:217] + '...'
        if structured:
            lines.append(f"| {name} | {a} | {s['em']:.3f} | {s['f1']:.3f} | "
                         f"{'yes' if s['refusal'] else 'no'} |")
        else:
            lines.append(f"| {name} | {a} | {s['f1']:.3f} | "
                         f"{'yes' if s['gold_contained'] else 'no'} | "
                         f"{'yes' if s['refusal'] else 'no'} |")
    return '\n'.join(lines)


def verdict(key, ver, label='Verdict'):
    v = ver.get(key)
    if not v:
        return f"**{label} verdict.** _pending_\n"
    code = v['class']
    if code == 'ok':
        return f"**{label} verdict: correct.** {v['cause']}\n{v['evidence']}\n"
    return (f"**{label} verdict: ({code}) {CLASSES[code]}.** {v['cause']}\n"
            f"Evidence: {v['evidence']}\n")


def extraction_cases(ver):
    rows = json.loads(P1.read_text())
    raw = load_raw(RAW1)
    insraw = load_raw(RAWI)
    plan = json.loads(INS.read_text())['cases']
    plan_by_trace = {p['trace_id']: p for p in plan}
    out, md = [], []
    seen = set()
    for row in rows:
        if row['group'] != 'extraction_omission':
            continue
        key = 'extraction:' + row['trace_id']
        seen.add(row['trace_id'])
        p = plan_by_trace[row['trace_id']]
        fid = p['fact_id']
        fact = next(f for f in row['facts']['facts'] if f['fact_id'] == fid)
        car = carrier_state(row, fid)
        r = raw.get(row['trace_id'], {})
        i = insraw.get(row['trace_id'], {})
        inst = instance_dict(row)
        arms = [('original board', score(row['answer_text'], inst))]
        for arm in ('Rerun', 'R-ext', 'V-ext'):
            if arm in r:
                arms.append((arm, score(r[arm]['answer'], inst)))
        for arm in ('R-ins', 'V-ins'):
            if arm in i:
                arms.append((arm, score(i[arm]['answer'], inst)))
        ext_units = [u['text'] for u in r.get('R-ext', {}).get('added_units', [])]
        ctl_units = [u['text'] for u in r.get('V-ext', {}).get('added_units', [])]
        ins_unit = i.get('R-ins', {}).get('inserted_unit') or {}
        out.append({
            'group': 'extraction', 'trace_id': row['trace_id'],
            'instance_id': row['instance_id'], 'model': row['model'],
            'benchmark': row['benchmark'], 'question': row['question'],
            'gold': row['gold_answer'], 'fact_id': fid, 'fact': fact['text'],
            'fact_sources': fact['source_ids'],
            'pool_carrier': car['extraction'], 'board_carrier': car['board'],
            'board': [{'unit_id': u['unit_id'], 'agent_id': u['agent_id'],
                       'text': u['text']} for u in row['board_units']],
            'rext_units': ext_units, 'vext_units': ctl_units,
            'rext_fact': fact_coverage(ext_units, fact['text']),
            'ins_unit': ins_unit.get('text'), 'ins_fact': fact_coverage(
                [ins_unit['text']] if ins_unit else [], fact['text']),
            'control_match': i.get('R-ins', {}).get('control_match'),
            'answers': {n: s for n, s in arms},
        })
        md.append(f"### {row['instance_id']} · {row['model']} · {row['benchmark']}\n\n"
                  f"**Question.** {row['question']}\n\n"
                  f"**Gold.** \"{row['gold_answer']}\"\n\n"
                  f"**Targeted fact ({fid}).** \"{fact['text']}\"  \n"
                  f"Extraction carrier: {esc(json.dumps(car['extraction']))} · "
                  f"board carrier: {esc(json.dumps(car['board']))}  \n"
                  f"Fact source(s): {', '.join(fact['source_ids'])}\n\n"
                  f"**Original board ({len(row['board_units'])} units).**\n\n"
                  f"{board_table(row['board_units'])}\n\n")
        if ext_units:
            md.append('**Repaired board: R-ext** (original + these units)\n\n'
                      + '\n'.join(f'- \"{esc(u)}\"' for u in ext_units) + '\n\n')
        if ctl_units:
            md.append('**Control board: V-ext** (original + these units)\n\n'
                      + '\n'.join(f'- \"{esc(u)}\"' for u in ctl_units) + '\n\n')
        if ins_unit:
            cm = i.get('R-ins', {}).get('control_match') or {}
            md.append(f"**Repaired board: R-ins** (original + exact fact)\n\n"
                      f"- \"{esc(ins_unit['text'])}\"  \n"
                      f"Volume match: repair {cm.get('repair_tokens')} vs control "
                      f"{cm.get('control_tokens')} tokens; matched={cm.get('matched')}\n\n")
        md.append('**Final answers**\n\n' + answer_table(arms, row['benchmark'].startswith('SB')) + '\n\n')
        md.append(verdict(key, ver, 'Missing-fact repair') + '\n'
                  + verdict('insertion:' + row['trace_id'], ver, 'Direct insertion') + '\n')
    return out, md, seen


def selection_cases(ver):
    rows = [r for r in json.loads(P1.read_text()) if r['group'] == 'selection_omission']
    raw = load_raw(RAW1)
    out, md = [], []
    for row in rows:
        key = 'selection:' + row['trace_id']
        r = raw.get(row['trace_id'], {})
        inst = instance_dict(row)
        # the selection case has no plan entry; the code picked this fact
        absent = [f for f in row['carriers']['facts'] if not f['board']]
        fid = absent[0]['fact_id'] if absent else None
        fact = next(f for f in row['facts']['facts'] if f['fact_id'] == fid)
        car = carrier_state(row, fid)
        arms = [('original board', score(row['answer_text'], inst))]
        for arm in ('Rerun', 'R-sel', 'V-sel'):
            if arm in r:
                arms.append((arm, score(r[arm]['answer'], inst)))
        sel_units = [u['text'] for u in r.get('R-sel', {}).get('added_units', [])]
        out.append({
            'group': 'selection', 'trace_id': row['trace_id'],
            'instance_id': row['instance_id'], 'model': row['model'],
            'question': row['question'], 'gold': row['gold_answer'],
            'fact_id': fid, 'fact': fact['text'],
            'pool_carrier': car['extraction'], 'board_carrier': car['board'],
            'board': row['board_units'], 'rsel_units': sel_units,
            'answers': {n: s for n, s in arms},
        })
        md.append(f"### {row['instance_id']} · {row['model']} · {row['benchmark']}\n\n"
                  f"**Question.** {row['question']}\n\n"
                  f"**Gold.** \"{row['gold_answer']}\"\n\n"
                  f"**Fact the matcher named ({fid}).** \"{fact['text']}\"  \n"
                  f"Extraction carrier: {esc(json.dumps(car['extraction']))} · "
                  f"board carrier: {esc(json.dumps(car['board']))}\n\n"
                  f"**Original board ({len(row['board_units'])} units).**\n\n"
                  f"{board_table(row['board_units'])}\n\n"
                  f"**Repaired board: R-sel** (original + pool units)\n\n"
                  + ('\n'.join(f'- \"{esc(u)}\"' for u in sel_units) or '- none added')
                  + '\n\n**Final answers**\n\n' + answer_table(arms, row['benchmark'].startswith('SB')) + '\n\n'
                  + verdict(key, ver) + '\n')
    return out, md


def distortion_cases(ver):
    rows = [r for r in json.loads(P23.read_text()) if r['group'] == 'distortion']
    raw = load_raw(RAW23)
    out, md = [], []
    for row in rows:
        key = 'distortion:' + row['trace_id']
        distorted = row.get('swap_preserves_fact')
        # the facts the swap unit was carrying on the board
        swap_id = row['target_swap']['unit_id']
        distorted_ids = [c['fact_id'] for c in row['carriers']['facts']
                         if any(swap_id in (u.get('unit_ids') or []) and u.get('fidelity') != 'faithful'
                                for u in c['board'])]
        fact_texts = {f['fact_id']: f['text'] for f in row['facts']['facts']}
        recalls = {fid: round(max(token_f1(row['target_swap']['text'], t), 0.0), 3)
                   for fid, t in fact_texts.items() if fid in distorted_ids}
        swap_text = row['target_swap']['text'].strip()
        r = raw.get(row['trace_id'], {})
        inst = instance_dict(row)
        arms = [('original board', score(row['answer_text'], inst))]
        for arm in ('Rerun', 'R-dist', 'V-dist'):
            if arm in r:
                arms.append((arm, score(r[arm]['answer'], inst)))
        out.append({
            'group': 'distortion', 'trace_id': row['trace_id'],
            'instance_id': row['instance_id'], 'model': row['model'],
            'benchmark': row['benchmark'], 'question': row['question'],
            'gold': row['gold_answer'], 'swap_preserves_fact': distorted,
            'distorted_fact_ids': distorted_ids,
            'distorted_facts': [fact_texts[f] for f in distorted_ids],
            'swap_recall': recalls,
            'swap_is_question': swap_text.lower().startswith('question:'),
            'swap_is_header': swap_text.startswith('[Document:'),
            'target_swap': row['target_swap'], 'donor_swap': row['donor_swap'],
            'board': row['board_units'],
            'answers': {n: s for n, s in arms},
        })
        md.append(f"### {row['instance_id']} · {row['model']} · {row['benchmark']}\n\n"
                  f"**Question.** {row['question']}\n\n"
                  f"**Gold.** \"{row['gold_answer']}\"\n\n"
                  f"**Distorted fact ({', '.join(distorted_ids) or 'none named'}).** "
                  + (' '.join(f'\"{esc(fact_texts[f])}\"' for f in distorted_ids) or '—')
                  + f"  \nSwap recall against it: {recalls or '—'}  \n"
                  f"**Manifest says the swap preserves the fact:** {distorted}  \n"
                  f"**Target swap** replaces `{row['target_swap']['unit_id']}` with "
                  f"\"{esc(row['target_swap']['text'])}\"  \n"
                  f"**Donor swap** replaces `{row['donor_swap']['unit_id']}` with "
                  f"\"{esc(row['donor_swap']['text'])}\"\n\n"
                  f"**Original board ({len(row['board_units'])} units).**\n\n"
                  f"{board_table(row['board_units'], highlight=(row['target_swap']['unit_id'],))}"
                  f"\n\n**Repaired board: R-dist.** Same board with the target unit "
                  f"replaced by the target-swap text above.\n\n"
                  f"**Final answers**\n\n" + answer_table(arms, row['benchmark'].startswith('SB')) + '\n\n'
                  + verdict(key, ver) + '\n')
    return out, md


def main():
    ver = json.loads(VERDICTS.read_text()) if VERDICTS.exists() else {}
    OUT.mkdir(parents=True, exist_ok=True)
    ext, ext_md, _ = extraction_cases(ver)
    sel, sel_md = selection_cases(ver)
    dist, dist_md = distortion_cases(ver)
    cases = {'extraction': ext, 'selection': sel, 'distortion': dist}
    (OUT / 'cases.json').write_text(json.dumps(cases, indent=1) + '\n')
    head = ('# E4 diagnosis case sheets\n\n'
            'Generated by `scripts/build_e4_diagnosis.py` from the frozen manifests '
            'and raw provider responses. Every F1 in this file is recomputed with '
            '`answer_f1`; the verdicts are hand-reviewed and kept in `verdicts.json`. '
            'No model calls are made.\n\n'
            f'Cases: {len(ext)} missing-fact repair, {len(sel)} selection, '
            f'{len(dist)} distortion.\n\n')
    body = ('## 1. Missing-fact repair (extraction omission)\n\n' + '\n'.join(ext_md)
            + '\n## 2. Selection cohort\n\n' + '\n'.join(sel_md)
            + '\n## 3. Distortion repair\n\n' + '\n'.join(dist_md))
    (OUT / 'case_sheets.md').write_text(head + body)
    print(json.dumps({k: len(v) for k, v in cases.items()}))


if __name__ == '__main__':
    main()