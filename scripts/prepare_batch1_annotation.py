"""Build author sheets with an allowlist; never copies attribution or audit outputs."""
import json
from pathlib import Path
from src.audit.pilot_common import blind_view,digest,ranked

ROOT=Path('rebuttal/annotation')
SCHEMAS={
'E1':{'critical_facts':[{'fact_id':'','text':'','source_ids':[]}],'sufficient_support_sets':[],
      'carriers':[{'fact_id':'','checkpoint':'pool|board','unit_ids':[],'role':'sole|alternative|joint','fidelity':'faithful|partial|distorted|absent|uncertain'}],
      'binary_call':'lost|reached_but_unused|exclude_partial|exclude_uncertain|correct','rationale':''},
'E2_A_screen':{'clean_reruns_correct':[None,None],'complete_pool':None,'complete_board':None,'any_partial_or_distorted':None,
              'any_uncertain':None,'eligible':None,'critical_facts':[],'sufficient_support_sets':[],'rationale':''},
'E2_A_post':{'injection_type':'','injected_fact_id':'','target_agent':'','only_one_critical_defect':None,
            'wrong_reruns':[None,None],'exactly_one_reasoning_step_changed':None,'keep':None,'rationale':''},
'E4':{'critical_facts':[],'sufficient_support_sets':[],'carrier_fidelity':[],
      'swap_source_quote':'','swap_is_verbatim':None,'swap_preserves_fact':None,'rationale':''},
'E2_B':{'defects':[{'agent':'','stage':'extraction|transmission|aggregation','type':'omission|distortion|reasoning-use|other','step':None}],
        'class':'single|multiple|indeterminate','reference_defects':[],'rationale':''}}
GUIDELINES={
'E1':'''Read question, source shards and supports first. Specify atomic facts and alternative sufficient sets before checking units. Do not treat shared words as evidence. Mark every pool/board carrier, its role, and source fidelity. Joint carriers require all units; list alternative carriers separately. Faithful preserves entity, relation, value and qualifier; partial drops a required detail; distorted contradicts it. Distinguish pool absence from selection loss. For a wrong answer, all facts in one sufficient set faithfully on board gives reached-but-unused; otherwise lost, excluding partial/uncertain from binary primary. This label does not prove the model's internal cause. Independently annotate before discussion; adjudicator records reasons. κ on the binary call; accuracy vs adjudication with instance-cluster CI.''',
'E2_A_screen':'''This is AUTHOR SCREENING, not blind Part B. Read the original base trace and sources. Correctness alone is insufficient. Check two clean reruns are correct; every fact in at least one sufficient set reaches pool and board; no critical carrier anywhere is partial/distorted; no uncertainty. Two authors independently screen. Enumerate sufficient support sets and carriers. Injection candidate fact must occur in every sufficient set and have no carrier outside the target agent. Reject unavailable stability results rather than assume them. Cohen κ on eligible/not eligible; item-level disagreement adjudication.''',
'E2_A_post':'''This is an author post-injection check. Compare before/after raw traces and declared edit. Confirm the intended defect is the only critical-evidence defect, including defects caused by re-selection. For evidence edits, both reruns must be wrong. For aggregation, board is unchanged, exactly one visible reasoning step changed, and wrong answer follows; report synthetic cases separately. Reject uncertain or additional defects. Cohen κ on keep/drop and nominal agreement on defect type. No matcher verdict or baseline attribution is displayed.''',
'E4':'''For the 40 matcher spot checks, independently identify carriers and fidelity from sources, without seeing matcher output. Author then compares labels in a separate analysis step. For every R-dist swap, compare old unit, proposed source line and full shard; require exact verbatim span and faithful restoration of the intended fact. Check donor/control swaps too. Partial is not strict distortion. Main study is single annotation; calibration double annotations support Cohen κ on fidelity and swap-valid yes/no. No intervention score or repair outcome is used to decide swap validity.''',
'E2_B':'''BLIND NATURAL-FAILURE LABELING. See only numbered original trace, private shards, gold supports and gold answer. Never open audit, matcher, lexical-score or baseline-attribution files. List all visible defects as agent/stage/type and cite steps. Single: one defect could plausibly be decisive alone; choose earliest decisive defect. Multiple: no single correction suffices, but correcting the set plausibly does. Indeterminate: evidence insufficient. Do not infer cause solely from answer wrongness or a repair result. No internal hidden reasoning is inferred. Cohen κ on single/multiple/indeterminate and on canonical reference tuples, separately. Indeterminate cases counted, unscored. E1 labelers cannot label the same trace for Part B.'''}
EXAMPLES=[
{'source':'Ada was born in 1900.','pool':['Ada was born in 1900.'],'board':['Ada was born in 1900.'],'answer':'1901','lesson':'Faithful carrier reaches board; wrong answer is candidate aggregation. Clean-screen fails correctness; Part B may call single aggregation if visible answer step misuses the date.'},
{'source':'Ada was born in 1900.','pool':['Ada is a person.'],'board':['Ada is a person.'],'answer':'unknown','lesson':'Critical birth date absent from pool: extraction omission. Not a defect-free base. Restoring exact date line is a valid source swap, subject to target manifest.'},
{'source':'Ada was born in 1900.','pool':['Ada was born in 1900.','Ada is a person.'],'board':['Ada is a person.'],'answer':'unknown','lesson':'Carrier exists in pool, absent from board: selection omission. An extraction injection that leaves this extra selection defect must be dropped.'},
{'source':'Ada was born in 1900 in Paris.','pool':['Ada was born in 1900 in Paris.'],'board':['Ada was born in 1901 in Paris.'],'answer':'1901','lesson':'Board contradicts source: distortion of transmission origin; source replacement must be exact. Post-check also inspects every other critical fact before keep.'},
{'source':'Ada was born before 1900 in Paris; Bea was born in Rome.','pool':['Ada was born in Paris.'],'board':['Ada was born in Paris.'],'answer':'1900','lesson':'Missing before qualifier is partial, not strict distortion. Multiple missing facts can make Part B multiple; if necessity cannot be established use indeterminate. Do not label an unsupported exact year as faithful.'}]

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(Path('rebuttal/pilots/20261108_preflight/id_manifest.json').read_text())
    assignments=[]
    for index,iid in enumerate(manifest['calibration_ids']):
        e1pair=('A','B') if index%2==0 else ('C','D');bp=('C','D') if index%2==0 else ('A','B')
        for task in SCHEMAS:
            pair=bp if task=='E2_B' else e1pair
            assignments.append({'instance_id':iid,'task':task,'annotators':pair,'status':'awaiting trace generation and human labels'})
    (ROOT/'calibration_assignments.json').write_text(json.dumps(assignments,indent=2)+'\n')
    for task,schema in SCHEMAS.items():
        dest=ROOT/task;dest.mkdir(exist_ok=True)
        (dest/'guidelines.md').write_text('# '+task+' annotation\n\n'+GUIDELINES[task]+'\n\n## Worked examples (synthetic training only)\n\n'+'\n\n'.join(f"{i+1}. Source: {e['source']} Pool: {e['pool']} Board: {e['board']} Answer: {e['answer']}\n\n{e['lesson']}" for i,e in enumerate(EXAMPLES))+'\n')
        (dest/'label_schema.json').write_text(json.dumps({'annotator_id':'','instance_id':'','trace_hash':'','labels':schema},indent=2)+'\n')
        rows=[]
        for f in sorted(Path('rebuttal/pilots/20261108_e1_calibration/traces').glob('*.json')):
            t=json.loads(f.read_text())
            if t['k']!=1:continue
            if t['instance_id'] not in manifest['calibration_ids']:raise ValueError('Calibration contamination')
            # Five traces/task, one Qwen source trace per reserved instance.
            if t['model']!='qwen/qwen3-235b-a22b-2507':continue
            rows.append({'task':task,'trace_hash':digest(t),'trace':blind_view(t),'labels':schema.copy(),'annotator_id':''})
        sheet=dest/'calibration_sheet.jsonl'
        if not sheet.exists() or all(not r.get('annotator_id') for r in [json.loads(x) for x in sheet.read_text().splitlines()]):
            sheet.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    (ROOT/'README.md').write_text('''# Batch-1 author annotation package

Five reserved calibration instances/task, outside all final evaluation IDs. `calibration_assignments.json` assigns opposite E1/PartB pairs: A+B → C+D, C+D → A+B. Rotate by instance, not model; all models/ks for an instance retain the same pair. Four humans must complete independent sheets, then adjudicate. No human calibration has been performed by the agent.

Each task directory has guidelines, 5 synthetic worked examples, schema and a JSONL labelling sheet. Copy a sheet to `<task>_<annotator>.jsonl` before entering labels; never edit generated sheets. Fill annotator_id and schema fields. Keep two files separate until adjudication. Sheets contain no model attribution, audit verdict, matcher output or lexical score: export uses an explicit recursive field allowlist tested in pytest. Raw system answers are part of the trace, not baseline-attribution outputs.

Run `.conda-env/bin/python -m scripts.prepare_batch1_annotation` after reserved source traces finish to populate all five rows/task. Empty/pending sheets are not completed calibration. E2-A post sheets additionally need actual proposed before/after injection pairs, and E4 swap sheets need proposed exact source spans; these depend on human screening/frozen matcher and are not fabricated.

Expected hours per annotator (balanced rotation): E1 28h; E2-A screening+post 7.5h; E4 single annotation 2h; batch1 total37.5h. PartB batch2 adds17.5h. Calibration adds about1.5h/person across tasks (10min×5 traces×2 reviewers×5 task sheets /4 ≈2.1h maximum; share screening/post reading). Reserve2.1h/person, separately from150h main-study estimate. Calibration stats: E1 binary κ; E2-A eligibility and keep/drop κ; E4 fidelity and swap-valid κ; PartB class and canonical reference κ. Report undefined κ honestly. Discuss all disagreements before evaluation labels; do not change frozen metrics or sample after seeing outcomes.

The annotation package is ready for human work only when its source traces/pairs are present. No messages have been sent to annotators.
''')
    print('Wrote schemas/guidelines/assignments; calibration sheets populated only from completed source traces.')
if __name__=='__main__':main()
