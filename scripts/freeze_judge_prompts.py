"""Write and hash the frozen LLM-judge prompts (v2). Rubrics are the existing author guidelines; no model calls."""
import json
from pathlib import Path
from src.audit.pilot_common import digest
OUT=Path('rebuttal/judge');A=Path('rebuttal/annotation')
COMMON=("You are an annotator for a research study on multi-agent evidence flow. You will see ONE recorded run: the question, each agent's private source text, "
"the gold supporting facts, the gold answer, the units each agent extracted, the units passed on, the shared board, and the final answer. "
"Judge only from what is shown. Compare every claim strictly against the source text; do not use outside knowledge to decide whether a fact is faithful. "
"Do not infer hidden reasoning. If you cannot decide, answer \"uncertain\" and give the reason; never guess. "
"You are never shown any automated audit, matcher, lexical-overlap or attribution-method output, and you must not try to guess one. "
"Reply with a single JSON object that matches the schema below and nothing else (no prose before or after).")
ADMIN=('Cohen','κ','Two authors','AUTHOR','adjudicat','Independently annotate','E1 labelers','Never open','No matcher verdict','Reject unavailable stability','author post-injection','two clean reruns')
def guideline(path):
    """Existing author guideline as the rubric, minus sentences that only concern human workflow or statistics."""
    body=Path(path).read_text().split('## Worked examples')[0].split('\n',2)[2].strip()
    kept=[s.strip() for s in body.replace('\n',' ').split('. ') if s.strip() and not any(a in s for a in ADMIN)]
    return '. '.join(kept).rstrip('.')+'.'
TASKS={
 'E1_fact_labelling':{'judge_model':'google/gemini-3.6-flash','rubric':guideline(A/'E1/guidelines.md'),'schema':json.loads((A/'E1/label_schema.json').read_text())['labels'],
   'output_note':'List atomic critical facts, sufficient support sets, and for every fact each pool/board carrier with its role and fidelity. Then give binary_call and a short rationale.'},
 'E2_wave1_base_screening':{'judge_model':'google/gemini-3.6-flash','rubric':guideline(A/'E2_A_screen/guidelines.md'),
   'schema':{'defect_free':'yes|no|uncertain','defect_free_reason':'','critical_facts':[],'sufficient_support_sets':[],'any_partial_or_distorted_carrier':'yes|no|uncertain',
     'target_checks':[{'agent_id':0,'target_fact':'','in_every_sufficient_set':'yes|no|uncertain','carrier_outside_agent':'yes|no|uncertain','feasible_fault_types':['extraction_omission','selection_omission','distortion','aggregation'],'source_citations':[]}],'eligible':'yes|no|uncertain','rationale':''},
   'output_note':'The two clean reruns are checked by the pipeline, not by you. Judge the shown base run only. Check every candidate agent.'},
 'E2_wave2_post_injection':{'judge_model':'google/gemini-3.6-flash','rubric':guideline(A/'E2_A_post/guidelines.md'),
   'schema':json.loads((A/'author_packet_20261108/E2A_post_wave2_schema.json').read_text())['answers'],
   'output_note':'You are shown BEFORE and AFTER traces and the declared edit. Answer each field with yes|no|uncertain (source_citations and uncertain_reason are free text; leave minutes_spent empty).'},
 'E2_partB_natural_failure':{'judge_model':'google/gemini-3.6-flash','rubric':guideline(A/'E2_B/guidelines.md'),'schema':json.loads((A/'E2_B/label_schema.json').read_text())['labels'],
   'output_note':'Step numbers refer to the numbered stage steps of the rendered trace (extraction per agent, transmission per agent, then aggregation).'}}
def main():
 prompts={}
 for k,v in TASKS.items():
  system=COMMON+'\n\nRUBRIC\n'+v['rubric']+'\n\nOUTPUT\n'+v['output_note']+'\nSchema (fill every field; use the allowed values shown):\n'+json.dumps(v['schema'],indent=1)
  prompts[k]={'judge_model':v['judge_model'],'system':system,'user_template':'RUN TO JUDGE\n{trace}','temperature':0,'seed':42,'system_sha256':digest(system)}
 doc={'version':'judge-prompts-v3','date':'2026-11-08','status':'frozen for piloting; prompt text identical to the superseded v1 and v2 (system_sha256 unchanged); only metadata changed','prompts':prompts}
 doc['prompts_sha256']=digest(prompts)
 (OUT/'judge_prompts_v3.json').write_text(json.dumps(doc,indent=1,ensure_ascii=False)+'\n')
 print(doc['prompts_sha256'],{k:len(v['system'].split()) for k,v in prompts.items()})
if __name__=='__main__':main()
