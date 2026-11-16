"""Current review update, keeping the compact report and appendices."""
import json,hashlib
from pathlib import Path
from collections import defaultdict
from scripts.write_batch1_report_v4 import main as previous,table
P=Path('rebuttal/pilots');O=P/'20261108_review5'
def load(p):return json.loads(p.read_text())
def main():
 previous();path=Path('iclr2027_rebuttal/drafts/batch1_pilot_report.md');s=path.read_text().replace('review 4,','review 5,')
 x=load(O/'supplement_summary.json');n=x['total_bases'];g=x['supplement_bases'];e=x['evidence_targets_per_type'];hours=x['hours']
 s=s.replace('Only 7/15 matched pairs; matched-pairs-only proposal needs approval.','Matched-pairs analysis approved; final labels/targets pending. Constructed controls need approval.')
 s=s.replace('47 correct bases / 118 evidence targets; only 47 aggregation candidates. Human screening, additional aggregation bases and postchecks needed.',f'{n} correct bases / {e} evidence targets; {n} aggregation candidates before screening. Human screening and postchecks needed.')
 s=s.replace('47 real correct MQ k = 1 traces: 24 Qwen, 23 Gemma; 94 independent author rows',f'{n} correct MQ k = 1 traces: 24 Qwen, {g} GPT, 23 Gemma; {2*n} author rows')
 s=s.replace('118 trace–agent candidates per evidence fault type. Fifty survive if retention ≥42.4%; no measured loss rate. Aggregation has 47 targets, three short before losses.',f'{e} trace–agent targets per evidence type; {n} aggregation targets. Fifty aggregation candidates require retention ≥{50/n:.1%}; screening loss is unmeasured.')
 s=s.replace('Existing GPT k = 3 boards differ from k = 1, so their answers were not relabelled as k = 1.',f'The approved GPT rebuild recovered 152/152 answers against frozen board and prompt hashes; {g} correct, nonreserved MQ bases are in `E2A_screening_supplement_wave1.jsonl`. Original sheets are unchanged; the combined SHA-order index controls selection.')
 combined=sum(h['E2A_screening_combined_hours_estimate'] for h in hours.values());by=' / '.join(f"{hours[a]['E2A_screening_combined_hours_estimate']:.2f}" for a in 'ABCD')
 s=s.replace('| Days 1–2: E2-A screening | 10.97 | 3.03 / 3.03 / 2.45 / 2.45 |',f'| Days 1–2: E2-A screening, including supplement | {combined:.2f} | {by} |')
 marker='No completed human calibration timings exist:'
 s=s.replace(marker,table(['Model','Correct nonreserved MQ bases','Aggregation targets before screening'],[['Qwen',24,24],['GPT-4o-mini',g,g],['Gemma',23,23],['Total',n,n]])+f'The supplement adds {2*g*7/60:.2f} author-hours; A/B/C/D add '+ ' / '.join(f"{hours[a]['E2A_supplement_hours_estimate']:.2f}" for a in 'ABCD')+f' h. Remaining pre-screening aggregation shortfall: **{max(0,50-n)}**. No pilot/calibration trace was added.\n\n'+marker)
 start=s.index('## E4:');end=s.index('## E2-A allocation',start)
 donor=load(P/'20261108_review4/e4_availability.json');groups=defaultdict(lambda:[0,0,0])
 for r in donor:
  v=groups[r['group_provisional']];v[0]+=1;v[1]+=r['matched_pairs'];v[2]+=r['pairs']
 section='''## E4: approved matched-pair comparison

`E4-v2.md` fixes the rule before this outcome-blind balance export. Repair minus volume control uses equal-unit-count pairs within ±10% exact base tokens. **Matched repair versus mismatched repairs still uses all cases.** The five reserved MQ cases give 7/15 matched pairs: 3/5 cases have any match, 2/5 have all three. No repair outcome by group was inspected.

'''
 section+=table(['Provisional group','MQ cases','MQ matched / possible','SB-5 / SB-10'],[[k,v[0],f'{v[1]}/{v[2]}','Not piloted / not piloted'] for k,v in groups.items()]+[['strict distortion',0,'0/0','Not piloted / not piloted']])
 section+='Balance uses 7 matched and 8 unmatched pair rows, clustered within five instances. Categorical entries are counts; numerical entries are medians. SMD uses pooled variance (NA if undefined). Zero SB rows mean no pilot coverage, not zero full-run availability.\n\n'
 b=load(O/'e4_balance.json');rows=[]
 for r in b['balance']:
  label=r['variable']+(' = '+str(r['level']) if r['level'] is not None else '')
  if r['level'] is not None:a,bv=r['matched_count'],r['unmatched_count']
  else:a,bv=r['matched_median'],r['unmatched_median']
  rows.append([label,a,bv,'NA' if r['smd'] is None else f"{r['smd']:.2f}"])
 section+=table(['Balance variable','Matched','Unmatched','SMD'],rows)
 section+='''Prospective all-case sensitivity: `D = repair score − volume-control score ~ failure type + protocol + base model + repair arm + log(1+repair tokens) + log(1+control tokens)`. Predict equal-volume contrasts by setting control tokens to repair tokens; bootstrap instances jointly across models/arms (2,000 draws, seed 42), separately by benchmark. Non-identifiable fits are reported, not repaired. This model is not fitted to five pilot items. Report a different sign or CI conclusion plainly. Both the balance table and tested analysis code are ready; final human-validated outcomes remain pending.

'''
 s=s[:start]+section+s[end:]
 old='- **E4: planned, pending author confirmation.** Closest-token donor order and matched-pairs-only contrasts, with explicit group coverage and unchanged ±10%.'
 proposal='''- **E4 matched-pairs analysis is approved.** The all-case main repair comparison is unchanged; balance and volume-adjusted sensitivity are preregistered in v2. No additional donor or tolerance change is made.
- **Constructed same-volume controls — card change, pending approval; costed only.** Likely sparse groups: SB-5 extraction has only ≈4 total cases; strict distortion ≈0–1/model/setting (at most ≈3 each SB setting). In the MQ pilot, selection and aggregation have zero matched pairs, extraction three; these five items cannot predict full-run match rates. SB-10 extraction/selection/aggregation availability is unknown. Proposed content: source-grounded distractor facts from an eligible non-target agent's shard, edited to the repair's unit count and ±10% exact token length, without adding any critical target fact or repairing the diagnosed stage. Two authors verify source fidelity, all sufficient sets, and off-target status; Qwen supplies an additional check. Reject failures, never pad with target evidence. Budget per constructed case: at most two base-model drafts, one Qwen check, one base aggregation = **4 calls, ≈$0.00256, 10 author-minutes** (two independent five-minute checks). Assumption: 2,000 input/500 output tokens per call, equal base mix, saved OpenRouter prices. A ten-case allowance costs **40 calls/$0.026/1.67 h**; actual full N is unknown (4N calls/$0.00256N/N÷6 h). If all ≈240 MQ aggregation cases needed one, that alone would be 960 calls/$0.61/40 h. No constructed-control code or calls have been made.'''
 s=s.replace(old,proposal)
 job=load(P/'20261108_gpt4omini_k1_rebuild/process.json');ledger=[json.loads(l) for l in (P/'20261108_gpt4omini_k1_rebuild/calls.jsonl').read_text().splitlines()];results=[r for r in ledger if r['event']=='result'];cost=sum(r.get('cost_usd') or 0 for r in results)
 test=load(O/'verification.json')
 s=s.replace('**289 tests pass**, including an AC1 hand-calculated example, actual pinned R1 scorer behaviour, and recursive blindness checks over the packet itself. No new paid calls this turn. The N80 AC1 simulation is complete; no experiment worker remains. Send the wave-1 packet now, but do not claim that the aggregation reserve or final 12 casebook is complete. Those are explicit remaining dependencies, not manufactured labels.',f"**{test['passed']} tests pass**, including rebuild hash binding, rotation/reserved-ID checks, balance statistics, synthetic volume adjustment, and blindness checks on the supplemented packet. The approved rebuild completed {len(results)}/152 calls, {sum(not r['success'] for r in results)} failures, **${cost:.5f}**. These 152 prerequisite calls were already in the batch budget, not an addition. Lead: the supplementary wave-1 packet is ready to send; it has not been sent. Screening eligibility, stability, postchecks and the human-classified final 12 remain open.")
 # Append active revisions and job provenance without duplicating old hash sections.
 names=['E1-v4.md','E2-A-v2.md','E4-v2.md','Baseline-scoring-v4.md','GPT-k1-rebuild.md']
 start=s.index('| Current prereg |');end=s.index('Completed simulation PID',start)
 s=s[:start]+table(['Current prereg','SHA-256'],[[name,hashlib.sha256((P/'prereg'/name).read_bytes()).hexdigest()] for name in names])+s[end:]
 s+=f"\nCompleted GPT prerequisite PID **{job['pid']}**: `{' '.join(job['command'])}`; log `{job['log']}`. Command is resumable with the same cumulative 152-call cap; do not start a second worker. Outcome-free balance: `python -m scripts.prepare_e4_balance`; supplement: `python -m scripts.supplement_author_packet`. New evidence/test log: `20261108_review5/`.\n"
 s=s.replace('All prereg hashes: `20261108_review4/prereg_hashes.json`.','Current prereg hashes: `20261108_review5/prereg_hashes.json`. Earlier review evidence: `20261108_review4/`.')
 s=s.replace('Packet export: `python -m scripts.prepare_author_packet`;','Original packet export (historical; do not overwrite reviewed sheets): `python -m scripts.prepare_author_packet`;')
 s=s.replace('All prereg hashes: `20261108_review4/prereg_hashes.json`.','All current prereg hashes: `20261108_review5/prereg_hashes.json`.')
 s=s.replace('Packet export: `python -m scripts.prepare_author_packet`;','Original packet exporter (do not rerun over author work): `python -m scripts.prepare_author_packet`;')
 path.write_text(s)
 (O/'prereg_hashes.json').write_text(json.dumps({f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (P/'prereg').glob('*.md')},indent=2)+'\n')
 print('report words',len(s.split()))
if __name__=='__main__':main()
