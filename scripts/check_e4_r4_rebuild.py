"""Apply the R3/R4 case gates to the 17 missing-fact repair cases.

R3 asks for exactly one support fact that is absent from the pool. R4 asks
that the board alone not reach the gold, that the target fact be in the
support set, that the board plus that fact reach the gold, and that the fact
not be a tautology. No model call, no outcome read: every input is frozen.

For the ten traces originally tagged (f) the script tries two rebuilds: a
single missing fact from the frozen support set, and a statement taken from
the case's source contexts. A lexical pass is not enough; each source rebuild
carries a manual semantic note, because token coverage cannot tell "the 1981
export restraints" from "opened in 1981".

    ./run.sh python -m scripts.check_e4_r4_rebuild
"""
import json
from pathlib import Path

from src.audit.e4_fix_gates import covers, reaches_gold, tautology

ROOT = Path(__file__).resolve().parent.parent
ACTIONS = ROOT / 'rebuttal/pilots/20261110_e4_phase1/actions_phase1.json'
PLAN = ROOT / 'rebuttal/pilots/20261110_e4_insert/insertion_plan.json'
OUT = ROOT / 'rebuttal/diagnosis/R4_rebuild.md'
OUT_JSON = ROOT / 'rebuttal/diagnosis/R4_rebuild.json'

# the ten (f) extraction traces, by instance|model, from verdicts.json
FALSE_CASES = {
    '4hop1__814349_624859_355213_203322|google/gemma-4-31b-it',
    '4hop1__814349_624859_355213_203322|openai/gpt-4o-mini',
    '3hop2__132957_433432_40768|google/gemma-4-31b-it',
    '2hop__491195_265959|google/gemma-4-31b-it',
    '3hop2__304722_590317_63959|google/gemma-4-31b-it',
    '2hop__511454_120259|openai/gpt-4o-mini',
    '2hop__28287_89399|openai/gpt-4o-mini',
    '4hop1__802394_153080_33897_81096|qwen/qwen3-235b-a22b-2507',
    'II-18_n10|qwen/qwen3-235b-a22b-2507',
    'II-18_n5|qwen/qwen3-235b-a22b-2507',
}

# Source-context rebuilds. `fact` is a faithful restatement of the quoted
# source; `decision` is the manual reading of that source.
SOURCE_CASES = {
    '2hop__28287_89399|openai/gpt-4o-mini': {
        'quote': 'Mr. Lawrence as the voice of Plankton / Plank - Ton',
        'fact': 'Mr. Lawrence is the voice of Plankton.',
        'decision': 'keep: rebuild with the corrected fact',
        'note': 'Source credits name Mr. Lawrence as the voice of Plankton; the plan fact wrongly '
                'named SpongeBob. The board already carries the plankton sentence, so one faithful '
                'fact closes the chain.'
    },
    '4hop1__802394_153080_33897_81096|qwen/qwen3-235b-a22b-2507': {
        'quote': 'Phoenix has a rich history of open wheel races, including ... the final career '
                 'victory for Indy legend Mario Andretti (1993).',
        'fact': 'Mario Andretti won the Indy car race in Phoenix in 1993, his final career victory.',
        'decision': 'keep: rebuild with the corrected fact',
        'note': 'The source states the Phoenix race included Andretti\'s final career victory; the '
                'plan facts named the race and its 2016 revival, never the winner.'
    },
    '3hop2__132957_433432_40768|google/gemma-4-31b-it': {
        'quote': 'A decade after the 1973 oil crisis, Honda, Toyota and Nissan, affected by the '
                 '1981 voluntary export restraints, opened US assembly plants ...',
        'fact': '',
        'decision': 'drop: gold 1981 is not entailed',
        'note': 'The sentence dates the opening to "a decade after 1973" (~1983) and uses 1981 only '
                'for the export restraints. Token coverage of "1981" is not entailment.'
    },
    '3hop2__304722_590317_63959|google/gemma-4-31b-it': {
        'quote': '1 December 2010 St Andrew\'s Birmingham City 2 -- 1 League Cup Quarter Final',
        'fact': '',
        'decision': 'drop (R3): two facts absent',
        'note': 'The source row gives the 1 December 2010 Birmingham 2-1 Aston Villa match, but the '
                'question also needs "the 1894-95 FA Cup winner was Aston Villa" (f2), which no board '
                'unit states. The frozen facts instead offer 1963 and 2015 matches.'
    },
    '2hop__491195_265959|google/gemma-4-31b-it': {
        'quote': 'He was the father of actress Lena Olin and singer Mats Olin.',
        'fact': '',
        'decision': 'drop: gold answers the wrong relation',
        'note': 'The source sentence links Stig Olin to Lena Olin as her father, but the question asks '
                'for the mother of the composer. The gold names the daughter, not the mother.'
    },
    '2hop__511454_120259|openai/gpt-4o-mini': {
        'quote': 'When Æthelflæd died in 918, Ælfwynn, her daughter by Æthelred, succeeded ...',
        'fact': '',
        'decision': 'reclassify (b), exclude from the repair cohort',
        'note': 'The 918 sentence is already on the board (board:a0:u1) and the model still refused '
                '("Insufficient information"). Nothing is missing, so this cannot test repair; it is '
                'present-but-unused. The gold\'s relation to Lady Godiva is also unclear.'
    },
    '4hop1__814349_624859_355213_203322|google/gemma-4-31b-it': {
        'quote': 'Gold Hill is a small unincorporated community in southeastern Rowan County, North '
                 'Carolina near the Cabarrus County line.',
        'fact': '',
        'decision': 'drop: malformed gold',
        'note': 'Gold is Cabarrus County, North Carolina; the question asks for a county bordering '
                'Cuyahoga County, Ohio. A correct answer (Lake County, Ohio) needs f3 and f4, two facts.'
    },
    '4hop1__814349_624859_355213_203322|openai/gpt-4o-mini': {
        'quote': 'Gold Hill is a small unincorporated community in southeastern Rowan County, North '
                 'Carolina near the Cabarrus County line.',
        'fact': '',
        'decision': 'drop: malformed gold',
        'note': 'Same case as the gemma trace: Cabarrus County cannot answer a Cuyahoga County border '
                'question, and the correction needs two facts.'
    },
    'II-18_n10|qwen/qwen3-235b-a22b-2507': {
        'quote': '',
        'fact': '',
        'decision': 'drop (R3): 56 pointers absent',
        'note': 'Gold is a whole 80-node ranking; one pointer cannot close the chain.'
    },
    'II-18_n5|qwen/qwen3-235b-a22b-2507': {
        'quote': '',
        'fact': '',
        'decision': 'drop (R3): 25 pointers absent',
        'note': 'Gold is a whole 40-node ranking; one pointer cannot close the chain.'
    },
}


def missing_ids(row):
    return [c['fact_id'] for c in row['carriers']['facts'] if not c['extraction']]


def evaluate(row, plan):
    facts = {f['fact_id']: f for f in row['facts']['facts']}
    board_units = [u['text'] for u in row['board_units']]
    miss = missing_ids(row)
    fid = plan['fact_id']
    fact = facts[fid]
    board_reaches = reaches_gold(board_units, row['gold_answer'], row['question'])
    signals = {
        'n_support_facts': len(facts),
        'missing_ids': miss,
        'n_missing': len(miss),
        'chosen_fact': fid,
        'chosen_in_support': fid in facts,
        'gold_covered_by_support': covers(' '.join(f['text'] for f in facts.values()), row['gold_answer']),
        'board_reaches_gold': board_reaches,
        'board_plus_fact_reaches_gold': reaches_gold(
            board_units + [fact['text']], row['gold_answer'], row['question'],
            fact['text'], fact_is_last=True),
        'fact_is_tautology': tautology(row['question'], fact['text']),
    }
    signals['r3_single_fact'] = len(miss) == 1
    signals['r4_entails_gold'] = not board_reaches and signals['board_plus_fact_reaches_gold']
    signals['r4_pass'] = (signals['chosen_in_support'] and signals['r4_entails_gold']
                          and not signals['fact_is_tautology'])
    signals['r3_r4_pass'] = signals['r3_single_fact'] and signals['r4_pass']
    rebuilt = []
    if not board_reaches:
        rebuilt = [m for m in miss
                   if reaches_gold(board_units + [facts[m]['text']], row['gold_answer'],
                                   row['question'], facts[m]['text'], fact_is_last=True)]
    signals['rebuild_fact_ids'] = rebuilt
    signals['rebuildable'] = bool(rebuilt)
    if signals['board_reaches_gold']:
        signals['verdict'] = 'not a repair case (board already reaches the gold)'
    elif not signals['r3_single_fact']:
        signals['verdict'] = 'drop (R3: more than one support fact absent)'
    elif not signals['rebuildable']:
        signals['verdict'] = 'drop (R4: no single missing fact reaches the gold)'
    else:
        signals['verdict'] = 'rebuild with ' + ', '.join(rebuilt)
    return signals


def source_signals(row, spec):
    board_units = [u['text'] for u in row['board_units']]
    if not spec['quote']:
        return {'lexical': False, 'corrected_fact': False, 'semantic': False}
    quote = spec['quote']
    lexical = reaches_gold(board_units + [quote], row['gold_answer'], row['question'],
                           quote, fact_is_last=True)
    corrected = bool(spec['fact']) and reaches_gold(
        board_units + [spec['fact']], row['gold_answer'], row['question'],
        spec['fact'], fact_is_last=True)
    semantic = spec['decision'].startswith('keep')
    return {'lexical': lexical, 'corrected_fact': corrected, 'semantic': semantic}


# Approved cohort decisions (2026-11-12). Applied in this diagnosis record;
# the frozen cohort and insertion manifests are not edited.
COHORT_ACTION = {
    '4hop1__814349_624859_355213_203322|google/gemma-4-31b-it': ('dropped', 'malformed gold; Cabarrus cannot border Cuyahoga'),
    '4hop1__814349_624859_355213_203322|openai/gpt-4o-mini': ('dropped', 'malformed gold; Cabarrus cannot border Cuyahoga'),
    '3hop2__132957_433432_40768|google/gemma-4-31b-it': ('dropped', 'gold 1981 not entailed; source says a decade after 1973'),
    '2hop__491195_265959|google/gemma-4-31b-it': ('dropped', 'gold is the daughter; question asks the mother'),
    '3hop2__304722_590317_63959|google/gemma-4-31b-it': ('dropped', 'R3: two facts absent (1894-95 winner and the match)'),
    'II-18_n10|qwen/qwen3-235b-a22b-2507': ('dropped', 'R3: 56 pointers absent from an 80-node ranking'),
    'II-18_n5|qwen/qwen3-235b-a22b-2507': ('dropped', 'R3: 25 pointers absent from a 40-node ranking'),
    '2hop__28287_89399|openai/gpt-4o-mini': ('rebuilt', 'corrected fact from source credits'),
    '4hop1__802394_153080_33897_81096|qwen/qwen3-235b-a22b-2507': ('rebuilt', 'corrected fact from the Phoenix race source'),
    '2hop__511454_120259|openai/gpt-4o-mini': ('excluded', 'board already reaches the gold; reclassified (b)'),
    '3hop1__147225_30587_83479|openai/gpt-4o-mini': ('dropped', 'R4 failure: gold paraphrase not entailed; verdict stays (b)'),
    '3hop1__132795_40769_64047|google/gemma-4-31b-it': ('excluded', 'board already reaches the gold; verdict stays (c)'),
    '3hop1__465684_160545_62931|qwen/qwen3-235b-a22b-2507': ('excluded', 'board already reaches the gold; verdict stays (c)'),
    '3hop1__147225_30587_83479|google/gemma-4-31b-it': ('excluded', 'board already reaches the gold; verdict stays (b)'),
    'III-29_n5|google/gemma-4-31b-it': ('excluded', 'R3: 3 support facts absent; both controls answer exactly (class d)'),
}
CLEAN_KEYS = {
    '2hop__280583_229757|google/gemma-4-31b-it',
    '2hop__142621_225454|google/gemma-4-31b-it',
    '2hop__28287_89399|openai/gpt-4o-mini',
    '4hop1__802394_153080_33897_81096|qwen/qwen3-235b-a22b-2507',
}


def short(s, n=150):
    s = ' '.join(s.split())
    return s if len(s) <= n else s[:n - 3] + '...'


def main():
    rows = [r for r in json.loads(ACTIONS.read_text()) if r['group'] == 'extraction_omission']
    plans = {p['trace_id']: p for p in json.loads(PLAN.read_text())['cases']}
    row_by_key = {r['instance_id'] + '|' + r['model']: r for r in rows}
    out, md = [], []
    for row in rows:
        key = row['instance_id'] + '|' + row['model']
        sig = evaluate(row, plans[row['trace_id']])
        record = {'trace_id': row['trace_id'], 'instance_id': row['instance_id'],
                  'model': row['model'], 'is_f_case': key in FALSE_CASES,
                  'gold': row['gold_answer'], 'signals': sig}
        if key in COHORT_ACTION:
            record['action'], record['action_reason'] = COHORT_ACTION[key]
        if key in FALSE_CASES:
            spec = SOURCE_CASES[key]
            src = source_signals(row, spec)
            record['source'] = {'quote': spec['quote'], 'fact': spec['fact'],
                                'decision': spec['decision'], 'note': spec['note'],
                                **src}
            record['decision'] = spec['decision']
            out.append(record)
            md.append(f"### {row['instance_id']} · {row['model'].split('/')[-1]}\n\n"
                      f"Gold: \"{short(row['gold_answer'])}\"  \n"
                      f"Chosen fact `{sig['chosen_fact']}`: \"{short(plans[row['trace_id']]['repair_unit']['text'])}\"  \n"
                      f"Missing support facts: {sig['n_missing']} "
                      f"({', '.join(sig['missing_ids'][:8])}"
                      f"{' ...' if sig['n_missing'] > 8 else ''})  \n"
                      f"Board alone reaches gold: {'yes' if sig['board_reaches_gold'] else 'no'} · "
                      f"R3 single absent fact: {'pass' if sig['r3_single_fact'] else 'FAIL'} · "
                      f"board+fact reaches gold: "
                      f"{'yes' if sig['board_plus_fact_reaches_gold'] else 'no'} · "
                      f"tautology: {'yes' if sig['fact_is_tautology'] else 'no'}  \n"
                      f"Frozen single-fact rebuild: "
                      f"{', '.join(sig['rebuild_fact_ids']) if sig['rebuildable'] else 'none'}  \n")
            if spec['quote']:
                md.append(f"Source candidate: \"{short(spec['quote'], 220)}\"  \n"
                          f"Lexical reach: {'yes' if src['lexical'] else 'no'}; "
                          f"corrected fact passes: {'yes' if src['corrected_fact'] else 'n/a'}; "
                          f"semantic entailment: {'yes' if src['semantic'] else 'no'}  \n")
            md.append(f"Semantic reading: {spec['note']}  \n"
                      f"**Decision: {spec['decision']}.**\n")
        else:
            out.append(record)
    by_key = {o['instance_id'] + '|' + o['model']: o for o in out}
    clean = []
    for key in sorted(CLEAN_KEYS):
        o = by_key[key]
        row = row_by_key[key]
        if key in SOURCE_CASES:
            fact = SOURCE_CASES[key]['fact']
            basis = 'rebuilt: ' + SOURCE_CASES[key]['quote']
        else:
            fid = o['signals']['rebuild_fact_ids'][0]
            fact = next(f['text'] for f in row['facts']['facts'] if f['fact_id'] == fid)
            basis = f'frozen fact {fid}'
        clean.append({'trace_id': o['trace_id'], 'instance_id': o['instance_id'],
                      'model': o['model'], 'fact': fact, 'basis': basis})
    actions = [{'trace_id': o['trace_id'], 'instance_id': o['instance_id'],
                'model': o['model'], 'action': o['action'], 'reason': o['action_reason']}
               for o in out if 'action' in o]
    (OUT_JSON).write_text(json.dumps({'cases': out, 'applied': {'clean_cohort': clean,
                                                               'actions': actions}},
                                     indent=1) + '\n')
    head = ('# R3/R4 rebuild check\n\n'
            'Generated by `scripts/check_e4_r4_rebuild.py` from the frozen phase-1 action '
            'manifest and insertion plan; no model calls. R3 requires exactly one absent '
            'support fact. R4 requires the board alone not to reach the gold (otherwise the '
            'case is present-but-unused), the fact in the support set, the board plus that fact '
            'to reach the gold, and the fact not to be a tautology. Reach is a lexical proxy; '
            'the source-context rebuilds below carry a manual semantic reading because token '
            'coverage cannot tell an entailment from a mention.\n\n'
            f'Extraction cases checked: {len(out)}. '
            f'(f) traces checked: {sum(o["is_f_case"] for o in out)}.\n\n'
            + '\n'.join(md) + '\n## All extraction cases\n\n'
            '| instance | model | missing | board has gold | R3 | R4 | rebuildable | verdict |\n'
            '| --- | --- | --- | --- | --- | --- | --- | --- |\n')
    for o in out:
        s = o['signals']
        head += (f"| {o['instance_id']} | {o['model'].split('/')[-1]} | {s['n_missing']} | "
                 f"{'yes' if s['board_reaches_gold'] else 'no'} | "
                 f"{'pass' if s['r3_single_fact'] else 'fail'} | "
                 f"{'pass' if s['r4_pass'] else 'fail'} | "
                 f"{'yes' if s['rebuildable'] else 'no'} | "
                 f"{o.get('decision', s['verdict'])} |\n")
    head += ('\nThe "board already reaches the gold" rows include the two (c) '
             'scoring cases (`3hop1__132795`, `3hop1__465684`) and `3hop1__147225` '
             'gemma. Their arm verdicts stand, but they cannot test missing-fact '
             'repair because the gold was already on the board. Four traces are '
             'clean single-fact repair cases: `2hop__280583`, `2hop__142621`, '
             '`2hop__28287`, and `4hop1__802394`.\n'
             '\n## Cohort decisions (approved 2026-11-12, applied here)\n\n'
             'The frozen cohort and insertion manifests are unchanged; these '
             'decisions apply to the diagnosis record and the planned reruns.\n\n'
             '| case | model | action | reason |\n'
             '| --- | --- | --- | --- |\n')
    for a in actions:
        head += (f"| {a['instance_id']} | {a['model'].split('/')[-1]} | "
                 f"{a['action']} | {a['reason']} |\n")
    head += ('\n### Clean single-fact cohort (4 traces)\n\n'
             '| case | model | fact | basis |\n'
             '| --- | --- | --- | --- |\n')
    for c in clean:
        head += (f"| {c['instance_id']} | {c['model'].split('/')[-1]} | "
                 f"{short(c['fact'], 160)} | {short(c['basis'], 120)} |\n")
    OUT.write_text(head)
    print(json.dumps({o['instance_id'] + '/' + o['model'].split('/')[-1]: o['signals']['verdict']
                      for o in out if o['is_f_case']}, indent=1))


if __name__ == '__main__':
    main()