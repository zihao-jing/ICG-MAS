"""Update packet instructions and prereg after the approved prerequisite completes."""
import json,hashlib
from pathlib import Path
from scripts.build_author_packet_viewer import main as viewer
P=Path('rebuttal/pilots');R=P/'20261108_review5';O=Path('rebuttal/annotation/author_packet_20261108')
def main():
 x=json.loads((R/'supplement_summary.json').read_text());n=x['total_bases'];g=x['supplement_bases'];e=x['evidence_targets_per_type']
 p=O/'GUIDE.md';s=p.read_text()
 s=s.replace('There are 47 real cached-correct MuSiQue k=1 base traces, double assigned;',f'There are {n} real correct MuSiQue k=1 base traces, double assigned;')
 s=s.replace('GPT k=1 answers and human-confirmed classes are missing.','The GPT prerequisite is complete; human-confirmed classes are still missing.')
 s=s.replace('Open your assigned rows in `E2A_screening.jsonl` using the index CSV.','Open your assigned rows in `E2A_screening.jsonl` and `E2A_screening_supplement_wave1.jsonl` in the offline form. Follow `E2A_combined_candidate_order.csv` across both files; it supersedes old within-file ranks without changing old sheets.')
 s=s.replace('47×2×7 min ≈ 11.0 h total',f'{n}×2×7 min ≈ {n*14/60:.1f} h total')
 s=s.replace('Evidence types have 118 trace-agent targets (50 retained if losses ≤57.6%, an unmeasured planning scenario); aggregation has 47 targets and is three short before losses.',f'Evidence types have {e} trace-agent targets; aggregation has {n} targets before losses (50 need retention ≥{50/n:.1%}, unmeasured). The supplement adds {g} bases; none is a pilot/calibration item. Screening remains necessary, as do two clean stability reruns; the prerequisite answer alone does not establish stability.')
 start=s.index('**Contents.**');end=s.index('**Base screening.**',start)
 s=s[:start]+f"**Contents.** The original `E2A_screening.jsonl` retains 47 bases; `E2A_screening_supplement_wave1.jsonl` adds {g} correct GPT-4o-mini k = 1 bases. Together: {n} MuSiQue bases, {e} trace–agent targets per evidence type and {n} aggregation targets. Fifty aggregation candidates require ≥{50/n:.1%} retention; this is capacity, not measured yield. Follow `E2A_combined_candidate_order.csv` across both files; it supersedes old within-file ranks. Each trace has two independent author rows. No pilot/calibration item is added. `E2C_class_confirmation_pool.jsonl` contains 108 wrong traces (93 MQ, 15 SB), not 12 confirmed cases. Open review.html offline, select author/task and download completed rows.\n\n"+s[end:]
 s=s.replace('A/B 3.03 h each; C/D 2.45 h each','A/B 4.32 h each; C/D 3.62 h each, including the supplement')
 p.write_text(s)
 old=P/'prereg/E2-A.md';archive=P/'prereg/E2-A-v1-archived.md'
 if not archive.exists():archive.write_bytes(old.read_bytes())
 s=archive.read_text().replace('# E2-A preregistration —','# E2-A preregistration v2 —')
 s=s.replace('the real cached-correct k1 roster is review4/author_packet_manifest.json, hashed below','the expanded real correct k1 roster is review5/E2A_combined_manifest.json, hashed below')
 s=s.replace('d7c1c15a857ab4503d9b61283519905ecb80e64bd230fb0c17e62029a049cfcd',hashlib.sha256((R/'E2A_combined_manifest.json').read_bytes()).hexdigest())
 s=s.replace('Evidence types have118 potential trace-agent pairs; aggregation has47 trace/aggregator candidates, three short before unknown losses.',f'Evidence types have {e} potential trace-agent pairs; aggregation has {n} trace/aggregator candidates before unknown screening losses.')
 s+='\nApproved day-0 supplement: all 152 GPT-4o-mini k = 1 aggregation answers are bound to frozen board/prompt hashes. Correct nonreserved MuSiQue bases only are added to wave 1, with the original instance rotation. The combined SHA order applies across original and supplementary files; never prioritize a model based on pilot yield. Original sheets remain intact. This is a screening reserve, not eligible injections; all human and clean-rerun gates above remain in force.\n'
 old.write_text(s);(P/'prereg/E2-A-v2.md').write_text(s);viewer()
 (R/'packet_inventory.json').write_text(json.dumps({f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in O.iterdir() if f.is_file()},indent=2)+'\n')
if __name__=='__main__':main()
