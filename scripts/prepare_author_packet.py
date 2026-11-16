"""No-API author packet from provenance-checked cached k1 answers; no inferred labels."""
import json,hashlib,csv
from pathlib import Path
from collections import defaultdict
from src.audit.critical_fact_validation import build_trace_packages,reconstruct_states_and_scores,get_transmitted_units,load_jsonl
from src.audit.pilot_common import blind_view,digest,ranked
from src.eval.data_loader import load_musique
from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer
P=Path('rebuttal/pilots');O=Path('rebuttal/annotation/author_packet_20261108');META=P/'20261108_review4'
RUNS=[('qwen','run_qwen235b_musique','qwen/qwen3-235b-a22b-07-25'),('gemma','run_musique_gemma31b','google/gemma-4-31b-it-20260402')]
def cached_mq():
 logs=load_jsonl('results/exp4_k_sweep_musique/api_responses.jsonl');instances={r['id']:r for r in load_musique()};out=[]
 for name,run,model in RUNS:
  api=[r for r in logs if r['model']==model];assert len(api)==600
  sources=load_jsonl(Path('results')/run/'api_responses.jsonl');states,scores=reconstruct_states_and_scores(sources)
  expected=[iid for iid in states if iid in instances]
  assert len(expected)*6==len(api)
  packages={r['instance_id']:r for r in build_trace_packages(dataset='musique',run_dir='results/'+run,protocol='score_ranked_relay',source_id=run)}
  for pos,iid in enumerate(expected):
   block=api[6*pos:6*pos+6];assert all(r['instance_id']==iid for r in block)
   # Source request order: random k1,k2,k3 then score-ranked k1,k2,k3; logger preserves request index.
   a=block[3]
   if not a['success']:continue
   t=packages[iid];units=get_transmitted_units(iid,'score_ranked_relay',states,scores,len(t['source_contexts']),k=1)
   board=[{'unit_id':f'k1:a{agent}:u{j}','agent_id':agent,'text':text} for agent,texts in sorted(units.items()) for j,text in enumerate(texts)]
   t['checkpoints']['transmission']=board;t['checkpoints']['board']=board;t['answer_text']=a['content'];v=blind_view(t)
   out.append({'trace_id':digest([run,iid,1]),'instance_id':iid,'model_family':name,'source_run':run,'logged_model':model,'k':1,'correct':answer_f1(extract_answer(a['content']),instances[iid])>=1,'trace':v,'provenance':{'log':'results/exp4_k_sweep_musique/api_responses.jsonl','request_id':a['request_id'],'position_in_model_batch':6*pos+3,'content_sha256':digest(a['content'])}})
 return out

def cached_sb():
 out=[]
 for name,folder,runs in [('qwen','exp4_k_sweep',['run_qwen235b_n5','run_qwen235b_n10']),('gemma','exp4_k_sweep_gemma31b',['run_gemma31b_n5','run_gemma31b_n10'])]:
  logs=load_jsonl(Path('results')/folder/'api_responses.jsonl');groups=defaultdict(list)
  for r in logs:groups[(r['ts'],r['instance_id'])].append(r)
  for run in runs:
   na=5 if run.endswith('n5') else 10;sources=load_jsonl(Path('results')/run/'api_responses.jsonl');states,scores=reconstruct_states_and_scores(sources)
   packages=build_trace_packages(dataset='silobench',run_dir='results/'+run,protocol='score_ranked_relay',source_id=run,n_agents=na)
   for t in packages:
    iid=t['instance_id'];matches=[rs for (_,key),rs in groups.items() if key==iid]
    if len(matches)!=1:continue
    block=matches[0]
    if name=='qwen':
     k1=[r for r in block if r['phase']=='k_sweep_agg_k1']
     if len(k1)!=2:continue
     a=k1[1]
    else:
     if len(block)!=6:continue
     a=block[3]
    if not a['success']:continue
    units=get_transmitted_units(iid,'score_ranked_relay',states,scores,na,k=1);board=[{'unit_id':f'k1:a{agent}:u{j}','agent_id':agent,'text':text} for agent,texts in sorted(units.items()) for j,text in enumerate(texts)]
    t['checkpoints']['transmission']=board;t['checkpoints']['board']=board;t['answer_text']=a['content']
    from src.eval.silo_bench_loader import silobench_exact_match
    correct=silobench_exact_match(extract_answer(a['content']),{'answer':t['gold_answer']})
    out.append({'trace_id':digest([run,iid,1]),'instance_id':iid,'model_family':name,'source_run':run,'logged_model':a['model'],'k':1,'correct':correct,'trace':blind_view(t),'provenance':{'log':str(Path('results')/folder/'api_responses.jsonl'),'request_id':a['request_id'],'content_sha256':digest(a['content'])}})
 return out

def export_rows(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():
  previous=[json.loads(x) for x in path.read_text().splitlines()]
  if any(r.get('annotator_id') or any(v not in ['',None,[]] for v in r.get('answers',{}).values()) for r in previous):raise ValueError('Refusing to overwrite annotations')
 path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))

def main():
 O.mkdir(exist_ok=True);META.mkdir(exist_ok=True);traces=cached_mq();d=json.loads((P/'20261108_review3/e1_stratified_design.json').read_text());held={i for h,s in d['designs']['80']['strata'].items() for i in s['ids']}
 correct=sorted([r for r in traces if r['correct']],key=lambda r:(digest([42,r['trace_id']]),r['trace_id']))
 wrong=sorted([r for r in traces+cached_sb() if not r['correct'] and r['instance_id'] in held],key=lambda r:(digest([42,r['trace_id']]),r['trace_id']))
 manifests={'candidate_order_rule':'SHA256 canonical JSON [42, trace_id], then trace_id; all cached-correct MQ k1 traces, not outcome-selected repairs','E2A_candidates':[{k:v for k,v in r.items() if k!='trace'} for r in correct],'E2C_confirmation_pool':[{k:v for k,v in r.items() if k!='trace'} for r in wrong],'missing_sources':['GPT-4o-mini MQ k1 aggregation cache absent','E2-C final 12 requires human class labels and confirmed held-out design'],'E2C_selected_ids':None,'candidate_per_fault_type':50,'screening_loss_rate':None,'note':'No measured human screening loss or timing available. Do not invent reserves or a twelve-case class-confirmed selection.'}
 manifests['evidence_target_candidate_order']=[{'trace_id':r['trace_id'],'agent':a} for r in correct for a in sorted([x['agent_id'] for x in r['trace']['source_contexts']],key=lambda a:digest([42,r['trace_id'],a]))]
 manifests['aggregation_candidate_order']=[{'trace_id':r['trace_id'],'agent':'aggregator'} for r in correct]
 # Metadata with model/provenance stays outside the author packet.
 (META/'author_packet_manifest.json').write_text(json.dumps(manifests,indent=2)+'\n')
 allids=sorted({r['instance_id'] for r in traces+wrong});pair=lambda iid:['A','B'] if allids.index(iid)%2==0 else ['C','D']
 fields={'defect_free':'','all_sufficient_sets_json':'','target_fact_text':'','target_agent_id':'','fact_in_every_sufficient_set':'','no_carrier_outside_target_agent':'','extraction_candidate':'','selection_candidate':'','distortion_candidate':'','aggregation_visible_step_candidate':'','uncertain_reason':'','source_citations':'','minutes_spent':'','target_checks_json':''}
 screen=[]
 for rank,r in enumerate(correct,1):
  for person in pair(r['instance_id']):screen.append({'task':'E2-A base screening','item_id':r['trace_id'],'candidate_rank':rank,'candidate_agent_ids':[x['agent_id'] for x in r['trace']['source_contexts']],'k':1,'assigned_annotator':person,'annotator_id':'','trace':r['trace'],'answers':dict(fields)})
 export_rows(O/'E2A_screening.jsonl',screen)
 classrows=[]
 for r in wrong:
  for person in pair(r['instance_id']):classrows.append({'task':'E2-C class confirmation','item_id':r['trace_id'],'k':1,'assigned_annotator':person,'annotator_id':'','trace':r['trace'],'answers':{'class':'','single_defect':'','support_sets_json':'','source_citations':'','uncertain_reason':'','minutes_spent':''}})
 export_rows(O/'E2C_class_confirmation_pool.jsonl',classrows)
 post={'schema_version':'author-post-v1','task':'E2-A post-injection','before_trace':None,'after_trace':None,'answers':{'exactly_one_critical_defect':'','other_critical_facts_unchanged':'','wrong_in_two_reruns':'','one_visible_step_changed_if_aggregation':'','source_citations':'','uncertain_reason':'','minutes_spent':''}}
 (O/'E2A_post_wave2_schema.json').write_text(json.dumps(post,indent=2)+'\n')
 for name in ['E2A_screening','E2C_class_confirmation_pool']:
  rows=[json.loads(x) for x in (O/(name+'.jsonl')).read_text().splitlines()]
  with (O/(name+'_index.csv')).open('w') as f:
   writer=csv.writer(f);writer.writerow(['item_id','assigned_annotator','jsonl_row']);writer.writerows((r['item_id'],r['assigned_annotator'],i+1) for i,r in enumerate(rows))
 totals={a:sum(r['assigned_annotator']==a for r in screen) for a in 'ABCD'}
 summary={'screening_traces':len(correct),'class_confirmation_traces':len(wrong),'class_confirmation_MQ':sum('__' in r['instance_id'] for r in wrong),'class_confirmation_SB':sum('__' not in r['instance_id'] for r in wrong),'screening_passes':len(screen),'assignments':totals,'model_counts':{name:sum(r['model_family']==name for r in correct) for name,_,_ in RUNS},'evidence_target_candidates_per_type':len(manifests['evidence_target_candidate_order']),'aggregation_candidates':len(correct),'shortfall_before_losses_per_type':{'aggregation':max(0,50-len(correct))},'human_timing_available':False}
 (META/'author_packet_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary)
 guide=f'''# Author screening packet — 8 November 2026

**Ready to send for wave-1 screening, not a final eligible-case list. Do not run injections yet.** There are {len(correct)} real cached-correct MuSiQue k=1 base traces, double assigned; {len(wrong)} held-out wrong MQ/SB traces await independent case classification. GPT k=1 answers and human-confirmed classes are missing. The 12-case E2-C selection cannot be made before those human labels. No final class or model diagnosis is shown.

1. Open your assigned rows in `E2A_screening.jsonl` using the index CSV. Read source shards, extraction pool, selected board and raw system answer. Specify atomic critical facts and EVERY sufficient support set. Confirm the whole trace is defect-free, the target fact is in every sufficient set, and no carrier occurs outside its target agent. Mark each feasible fault type separately. A correct answer alone is insufficient. Two authors independently fill separate rows; the same pair reconciles disagreements before injection; unresolved items are excluded.
2. Single-defect means precisely one necessary critical fact is omitted at extraction/selection, one source-grounded fact is strictly contradicted, or exactly one visible aggregation reasoning step is changed, with all other critical evidence intact. Qualifier loss is partial, not strict distortion. Use `uncertain`, explain why and cite the source; never guess. Uncertain or non-unique-target cases do not pass.
3. In `E2C_class_confirmation_pool.jsonl`, record extraction omission, selection omission, candidate aggregation, other or uncertain without seeing a proposed class. Only confirmed wrong held-out k=1 traces can enter the fixed SHA selector: 4 extraction SB, 4 selection SB, 2 aggregation MQ, 2 aggregation SB. Record class shortfalls rather than filling them with guesses.
4. **Wave 2:** post-injection sheets cannot be filled before an injection exists. They are exported immediately after approved screening AND the corresponding injection/reruns. Compare raw before/after traces; check uniqueness, other facts unchanged, and two wrong reruns (aggregation: one visible step). No matcher/baseline output is shown. Allow 10 h total / 2.5 h per annotator for up to 120 kept-case checks, plus adjudication; the timing is a planning allowance, not calibration measurement.

**Who and when:** A+B and C+D alternate by instance; all model traces for one instance retain the pair. The complementary pair remains unexposed for blind Part B; it does not adjudicate these sheets. Day 0: lead sends this packet and calibration. Days 1–2: wave-1 screening ({len(correct)}×2×7 min ≈ {len(correct)*14/60:.1f} h total) and class confirmation in SHA order, stopping once quotas fill (MQ 7 min/pass; SB 20 min/pass). The full pool is a reserve, not a request to label every item. Day 3 onward: release screened items; produce wave-2 sheets after each injection, return within one working day so the run is not held up. Full 12-case confirmation budget: 10 SB×2×20 min +2 MQ×2×7 min =7.13 h. Record actual `minutes_spent`; no completed human calibration timings currently exist.

Allocation is **50 candidates per fault type**, with independent screening before any injection; the same screened base may support distinct type candidates when eligible. Evidence types have 118 trace-agent targets (50 retained if losses ≤57.6%, an unmeasured planning scenario); aggregation has 47 targets and is three short before losses. Complete target_checks_json for every candidate_agent_id, with fact, every-set necessity, exclusive ownership and per-type eligibility. Up to 30 kept per type remains unverified; **fewer than 10 kept → descriptive reporting only**. No reviewer should fill a nonexistent post-injection sheet.

The export excludes audit verdicts, matcher labels/scores, lexical coverage and attribution-baseline output. Raw base-system answers are essential trace evidence and are deliberately visible. Lead: this wave-1 packet is ready to send; the assistant has not sent it.
'''
 (O/'GUIDE.md').write_text(guide)
 (O/'hours_by_annotator.json').write_text(json.dumps({a:{'E2A_screening_hours_estimate':totals[a]*7/60,'E2C_full_pool_hours_upper_estimate':sum((7 if '__' in r['trace']['instance_id'] else 20)/60 for r in classrows if r['assigned_annotator']==a),'post_wave2_reserved_hours':2.5,'calibration_reserved_hours':2.1,'basis':'planning minutes only; measured human times unavailable'} for a in 'ABCD'},indent=2)+'\n')
if __name__=='__main__':main()
