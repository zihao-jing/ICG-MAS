# Coverage labeller — final statement (item 2)

No paid call was made for this statement. The v2 held-out run is
`../20261113_coverage_validation_v2/report.md`; the development calls are in
`calls.jsonl` here. Earlier results stay on record unchanged.

## Result

| prompt | population | prompt complete | author complete | agreement (95% CI) | kappa (95% CI) | verdict |
| --- | --- | ---: | ---: | --- | --- | --- |
| v1 | Anchor, 90 traces (180 comparisons) | 58 | 156 | 70/180 = 0.389 | 0.031 | fail |
| v2 | held-out, 25 traces (60 comparisons) | 8 | 50 | 18/60 = 0.300 (0.188-0.432) | 0.060 (0.019-0.128) | **FAIL** |
| v3 | Anchor dev only | 56 | 156 | 76/180 = 0.422 | 0.095 | dev |
| v4 | Anchor dev only | 74 | 152 | 88/174 = 0.506 | 0.111 | dev |
| v5 | Anchor dev only | 112 | 156 | 126/178 = 0.708 | 0.275 | dev |

The pass rule was frozen before the v2 run: agreement >= 0.80 **and** kappa >=
0.60. v2 failed on both. The coverage labeller is **not validated**; the
lexical rule remains the reported coverage figure. The v3-v5 rows are
development iterations on the Anchor labels used to design the prompt, not
validation, and were written after the held-out result was seen, so they cannot
serve as a clean held-out test. No further paid run was made.

Spend: v2 held-out $0.009452 (60 calls, `../20261113_coverage_validation_v2/calls.jsonl`);
v3-v5 development $0.128394 (270 calls, this directory). Reproduce the
development rows with `./run.sh python -m scripts.coverage_labeller_v3 --dev-report`.

## Cause

There are two causes, and the second one is the binding one.

**1. The unit of judgment differs.** v1 asked whether one board unit restates
each whole support passage. The authors label per `critical_facts_json` fact,
and a carrier may be `joint`: across 240 E1 label sets there are 878 board
carriers, 400 joint; 594 cite three board units. A fact can be faithfully
carried by three units together, which v1 read as partial. v2 fixed this
(union of units, joint carriers, record-to-sentence conversion) and still
failed.

**2. The support passages contain content the question does not need, and the
author label does not require it.** `author_complete` is true when every fact
the authors *listed* is faithfully carried at the board, not when the whole
passage is. The passages in this benchmark are whole documents. v2 called a
passage `partial` whenever the board omitted document detail, even when the
decisive value was present verbatim. This is visible in v2's own reasons:

- Calibration run 2: the board carries "penetrated into the Roman Empire on 31
  December 406" verbatim; v2 says `partial` because the board "omits the
  Suebic settlement of Galicia, the 409 and 411 events, and the 585 Visigothic
  invasion." The question asks only for the year; authors mark both facts
  faithful.
- Calibration run 5: `partial` because the board omits "the 2000 census
  population of 3,702" (not needed for the county link) and "the agency's role
  in managing parks and recreation" (v2 itself calls it framing).
- Dev run 01: `partial` because the board omits "the portrait's subject
  (George Dyer), the pose and setting details."

Of the 60 held-out comparisons, 42 are author-complete / prompt-incomplete (8
are complete in both, 10 incomplete in both, and none is prompt-complete /
author-incomplete).
The labeller must therefore decide relevance itself, because the authors'
critical-fact list is not shown to it; v1 and v2 did not, and called passages
partial for omitting irrelevant document text.

The author labels are not noisy: only 2 of 115 doubly annotated E1 items split
on `author_complete` (Anchor Q09 run 3, Q25 run 1). The problem is that their
unit is the listed critical fact and their relevance judgment lives in that
list, so the label is not reconstructible from the support text alone. That is
an annotation-design property, not a wording defect that another prompt
revision fixes.

**3. What the development revisions show.** v3-v5 added a decisive-claim rule
(the same move as the screening amendment): identify the minimal content the
question needs, ignore background, and treat any substantive restatement as
present. Agreement rises 0.422 -> 0.506 -> 0.708 and kappa 0.095 -> 0.111 ->
0.275 on the Anchor set, which supports cause 2 (relevance selection, not
fidelity, is what the remaining disagreement is about). Even v5 is far below
the frozen kappa floor of 0.60, and its small residual is the same kind of
relevance call. There is no evidence that a further prompt edit would cross
the threshold, and testing one on the held-out items after seeing the first
failure would not be a clean validation.

## Consequence for the rebuttal

Coverage and AF remain the lexical figures. No labeller-based coverage number
is reported as validated. The diagnosis to state is that the author label is a
critical-fact-carrier label whose relevance judgment is not in the support
text, so an evidence-only labeller cannot reproduce it reliably; it is not that
the audit pipeline cannot measure coverage by lexical means.