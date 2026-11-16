"""Claims-impact template: which paper claims (file:line) each pre-registered batch-1 result could affect, so a result that goes against us can be mapped straight away.
READ-ONLY on the paper: it quotes the current text of each line and fails if a quoted fragment is not at the stated line (so the map cannot go stale silently).
Writes iclr2027_rebuttal/drafts/claims_impact_template.md. Proposed revisions are labelled proposed and are NOT applied."""
from pathlib import Path
PAPER=Path('iclr2027_paper');OUT=Path('iclr2027_rebuttal/drafts/claims_impact_template.md')
A='sections/0-abstract.tex';I='sections/1-introduction.tex';R='sections/2-related-work.tex';M='sections/3-methodology.tex';X='sections/4-experiments.tex';D='sections/5-discussion.tex';AP='appendix/app_main.tex'
TAC='items/tables/tab_audit_combined.tex';TAP='items/tables/tab_aggregation_placement.tex';TCE='items/tables/appendix/tab_claim_evidence.tex'
ENTRIES=[
 {'id':'R1','result':'E1: matcher validity (presence and fidelity agreement with authors on the 30-instance anchor; matcher against the judge on 80)','tables':['T01','T02'],
  'against':'Matcher–human agreement is low, or the judge disagrees with the authors, so lexical coverage and the semantic matcher cannot be called validated.',
  'claims':[(A,4,'lexical alignment enable systematic tracking'),(I,37,'Our implementation uses benchmark support annotations and lexical matching'),(M,93,'We cannot verify that condition from lexical matching'),(M,97,'Lexical coverage cannot certify semantic sufficiency'),(X,31,'is sensitive to lexical thresholds'),(TCE,20,'semantic sufficiency remains unverified')],
  'proposed':'Say that coverage was checked against author labels on a 30-instance anchor and report the agreement; restrict diagnoses to the instances where the matcher is validated.'},
 {'id':'R2','result':'E1: label-based MuSiQue candidate-aggregation-failure rate against the lexical 68% (reweighted headline rates)','tables':['T03','T01'],
  'against':'The label-based rate falls well below the lexical figure (the lexical sweep already moved it from 68% to 3% as τ rose), so "errors despite complete coverage" is much rarer than reported.',
  'claims':[(A,5,'MuSiQue often yields incorrect answers despite complete measured coverage'),(I,45,'MuSiQue frequently shows incorrect answers despite complete lexical coverage'),(X,31,'relay often gives wrong answers despite complete measured coverage'),(X,33,'On MuSiQue, errors despite complete lexical coverage'),(X,76,'Each selected answer is non-perfect despite complete measured critical-fact coverage'),(TAC,8,'candidate aggregation-failure rate'),(TCE,20,'MuSiQue errors persist despite complete lexical coverage for relay in 8 of 9 models')],
  'proposed':'Revise abstract sentence 4, contribution 2, Key Finding 2, Table 3\'s AF column, §4.2, and the Table 9 cohort definition (cases selected at τ = 0); report Table 9 on validated cases only.'},
 {'id':'R3','result':'E1: Silo-Bench extraction loss against selection loss (from labels)','tables':['T01','T03'],
  'against':'Silo-Bench extraction loss is not larger than selection loss under validated labels.',
  'claims':[(A,5,'Silo-Bench exhibits measurable losses before aggregation'),(I,45,'Silo-Bench shows extraction and selection losses'),(X,28,'localizes the larger loss to extraction'),(X,33,'On Silo-Bench, measured critical-fact loss is larger at extraction than selection'),(TCE,16,'stage-wise extraction and selection losses')],
  'proposed':'Change Key Finding 2\'s first sentence to say that extraction and selection losses are of similar size.'},
 {'id':'R4','result':'E1: strict distortion under human/judge fidelity labels against the LLM-judge-plus-numeric-checks audit','tables':['T01'],
  'against':'Fidelity labels find more strict distortion than the 0.3–0.7% reported for relay.',
  'claims':[(AP,955,'strict distortion is near-zero for relay'),(M,78,'labels each gold/transmitted alignment'),(M,97,'Distortion is audited separately')],
  'proposed':'Report the label-based distortion rate beside the audit figure and revise the appendix sentence.'},
 {'id':'R5','result':'E4: does the repair matched to the diagnosis beat the mismatched repairs in each diagnosed group (all cases)','tables':['T05'],
  'against':'The matched repair does not beat the best mismatched repair in some or all groups.',
  'claims':[(A,7,'The framework maps these diagnoses to targeted interventions'),(I,49,'We map diagnostic patterns to repair targets'),(M,148,'Extraction omission suggests re-extraction'),(D,4,'helps identify where a targeted intervention may be useful'),(X,76,'We test a more targeted choice')],
  'proposed':'Replace "maps these diagnoses to targeted interventions" with "localises defects; a stronger aggregator is a robust default" if the final step wins everywhere; drop "evidence integration" if R-agg is not above generic retry.'},
 {'id':'R6','result':'E4: R-agg and R-agg+ (final step) against the other arms in every group','tables':['T05'],
  'against':'Upgrading the final step wins in every group, so diagnosis-specific repair adds nothing.',
  'claims':[(A,8,'larger gains from upgrading final aggregation'),(I,49,'final-stage placement outperforms one local extraction upgrade'),(X,83,'final aggregation beats local extraction')],
  'proposed':'Contribution 4 and the abstract sentence become "localises defects; a stronger aggregator is a robust default".'},
 {'id':'R7','result':'E4: repair minus its volume control (natural matched pairs only; "no same-volume control available" cells reported as such)','tables':['T06'],
  'against':'The repair does not beat its same-volume control, so the gain may come from added text.',
  'claims':[(I,36,'The identity and meaning of the missing fact determine the repair target, not the total amount communicated')],
  'proposed':'Qualify the introduction sentence; state that Silo-Bench has no answer-neutral same-volume control.'},
 {'id':'R8','result':'E4-P: one Gemini call at the final stage against one local extraction, by stage and task (seed-43 enlargement included)','tables':['T07'],
  'against':'The final-stage advantage shrinks or reverses on the enlarged Silo-Bench sample or when targets come from validated labels.',
  'claims':[(A,8,'larger gains from upgrading final aggregation than from upgrading one local extraction step across three tasks'),(I,49,'across three tasks'),(X,83,'beats local extraction by 6.1, 26.6, and 4.4 points'),(TAP,12,'MQ & 213'),(TAP,13,'SB-5 & 56'),(TAP,14,'SB-10 & 57')],
  'proposed':'Update the three gaps and the "across three tasks" wording to the validated numbers, or restrict the claim to the settings where it holds.'},
 {'id':'R9','result':'E2 Part A and Part B: audit against [R1], Who&When and MAST on injected single faults and on natural failures','tables':['T09','T12'],
  'against':'Baselines match or beat the audit on stage and type accuracy.',
  'claims':[(A,3,'failure attribution framework that tracks answer-critical evidence'),(I,43,'separating observable pipeline defects from candidate downstream failures'),(R,15,'Our evidence-flow audit is complementary'),(R,24,'Tracking evidence alongside final accuracy supports this attribution and identifies repair targets')],
  'proposed':'Withdraw any claim that existing methods cannot separate extraction, transmission and aggregation; state that the audit adds the identity of the missing fact, not stage accuracy.'},
 {'id':'R10','result':'E2 judge quality and the author spot-check gate','tables':['T10','T11'],
  'against':'The judge disagrees with authors on the spot-check items, contradicts itself often, or the gate stops scaling.',
  'claims':[(I,43,'separating observable pipeline defects from candidate downstream failures')],
  'proposed':'No paper sentence changes by itself; E2 claims are then restricted to the author-confirmed subset or to fallback F1/F2, and described as such.'},
]
def line_text(rel,n):
    return (PAPER/rel).read_text().splitlines()[n-1]
def verify():
    bad=[]
    for e in ENTRIES:
        for rel,n,frag in e['claims']:
            try:t=line_text(rel,n)
            except Exception:bad.append((rel,n,'unreadable'));continue
            if frag not in t:bad.append((rel,n,frag))
    return bad
def render():
    L=['# Claims-impact template: pre-registered results against the paper claims they could affect','','**No result is filled in.** For each pre-registered result, the claims (file:line, with the paper\'s current text) that a result against us would affect. Generated read-only from `iclr2027_paper/` by `scripts/make_claims_impact.py`; the paper is not edited, and every "proposed" line is a proposed revision, not applied. A test fails if the quoted text is no longer at its line.','','Use: when `tables_manifest.json` shows a result in the "against us" direction, open its row here.','']
    for e in ENTRIES:
        L+=[f"## {e['id']}. {e['result']}",'',f"**Tables:** {', '.join(e['tables'])} (`rebuttal/results/batch1/tables/`)",f"**Against-us outcome:** {e['against']}",'','| File:line | Current text (excerpt) |','|---|---|']
        for rel,n,frag in e['claims']:
            t=line_text(rel,n).strip().replace('|','\\|');i=max(t.find(frag)-40,0);L.append(f"| `{PAPER.name}/{rel}:{n}` | …{t[i:i+230]}… |")
        L+=['',f"**Proposed revision (not applied):** {e['proposed']}",'']
    return '\n'.join(L)
def main():
    bad=verify()
    if bad:raise SystemExit(f'claims map is stale: {bad}')
    OUT.write_text(render()+'\n');print(f'{len(ENTRIES)} results, {sum(len(e["claims"]) for e in ENTRIES)} claim lines written to {OUT}')
if __name__=='__main__':main()
