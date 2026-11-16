"""Write README.md (tables computed from the sheets) and CHECKSUMS.sha256 for the labelling folder."""
import csv,hashlib,json
from pathlib import Path
from collections import defaultdict
F=Path('rebuttal/annotation/labelling_20261108')
def jl(p):return [json.loads(x) for x in Path(p).read_text().splitlines()]
def main():
    anc=jl(F/'data/T2_E1_anchor.jsonl');pairs=defaultdict(set)
    for r in anc:pairs[r['display_name'].split(' run')[0]].add(r['assigned_annotator'])
    qs={'A+B':[],'C+D':[]}
    for q,a in sorted(pairs.items()):qs['+'.join(sorted(a))].append(q.replace('Anchor ',''))
    dev=jl(F/'data/T1_E1_dev.jsonl');devp=defaultdict(set)
    for r in dev:devp[r['display_name']].add(r['assigned_annotator'])
    dn={'A+B':sum(1 for a in devp.values() if a=={'A','B'}),'C+D':sum(1 for a in devp.values() if a=={'C','D'})}
    spot=jl(F/'data/T3_E2_spotcheck_wave1.jsonl')
    sp={a:[r['display_name'] for r in spot if r['assigned_annotator']==a] for a in 'ABCD'}
    hrs={'A':{'dev':5.25},'B':{'dev':5.25},'C':{'dev':3.5},'D':{'dev':3.5}}
    rows=[]
    for a in 'ABCD':
        h=hrs[a];spot_h=len(sp[a])*7/60
        rows.append((a,2.1,11.81,h['dev'],spot_h,2.1+11.81+h['dev']+spot_h))
    t='| Author | Day 0 calibration | Anchor | Dev | Spot-checks wave 1 | **Total now** |\n|---|---:|---:|---:|---:|---:|\n'+'\n'.join(f'| {a} | {c:.2f} | {an:.2f} | {d:.2f} | {s:.2f} | **{tot:.1f} h** |' for a,c,an,d,s,tot in rows)
    VERSION=(F/'VERSION').read_text().strip()
    readme=f'''**Version: {VERSION}** (file `VERSION`; its checksum is in `CHECKSUMS.sha256`; changes are listed in `CHANGELOG.md`)

# Labelling folder: start here

**What this is.** One folder with everything you need to do the labelling for our rebuttal experiments: the data, the instructions, an offline form, and how to send your work back. You do not need any other document. Open `forms/labelling_form.html` in a browser; it works offline.

## Why we are asking you

We are testing two things: whether our automatic fact-tracking is accurate, and whether our audit finds a planted fault better than another method. An AI model (the "judge") does most of the labelling that authors would otherwise do by hand. A judge can be wrong, so your labels are the yardstick that measures how often. **You never see the judge's answers, the tracker's answers or any method's answers, and they never see yours.** Please do not look for them.

## The tasks: calibration (Task 0) plus three labelling tasks (Tasks 1-3)

| # | Task | Guideline | Data file | Items | Who | Due |
|---|---|---|---|---|---|---|
| 0 | **Calibration** on 5 runs, to align our reading (not used as data) | `guidelines/1_E1_labelling.md` (covers Tasks 0-2) | `data/T0_calibration_E1.jsonl` | 5 runs, everyone | A, B, C, D | Sun 8 Nov (day 0) |
| 1 | **E1 dev labels** (used to tune the tracker, so they come first) | same | `data/T1_E1_dev.jsonl` | 20 runs, two authors each | pairs below | end of day 3, Wed 11 Nov |
| 2 | **E1 anchor** (the yardstick for the judge and the tracker) | same | `data/T2_E1_anchor.jsonl` | 30 questions × 3 runs, two authors each | pairs below | end of day 3, Wed 11 Nov |
| 3 | **E2 spot-checks**: is a base run clean? Wave 1 now; wave 2 later | `guidelines/2_E2_spotcheck.md` (Task 3) | `data/T3_E2_spotcheck_wave1.jsonl` | 12 items now, one author each; 8 more later | table below | wave 1: end of day 2, Tue 10 Nov; wave 2: one working day after it arrives |

**Not in this folder yet, on purpose:** the 8 wave-2 spot-check sheets (they can only be made after wave 1 passes and faults are planted). Nobody will send you invented ones; they will arrive as a new file with the same instructions.

## Order to do them

1. Read this page and the guideline for Tasks 0-2, then do the **calibration** (Task 0) **alone**, save, and send your file back. Once all four calibration files are in, the lead sends all four to everyone and we compare them in one short call (the lead arranges the time in the same message thread); this is the only time you see another author's answers before the real tasks. Calibration answers are not used as data.
2. **Task 3 (E2 spot-checks)**: short, due first (Tue 10 Nov).
3. **Task 1 (dev)**, then **Task 2 (anchor)**: due Wed 11 Nov. Dev comes first because the tracker is frozen on it.
4. The wave-2 spot-checks follow when they arrive.

For Tasks 1 and 2, work **alone first** on every item and send your **independent** file (it is the file that counts for agreement). Reconciling with your partner comes later: after both independent files are in, the lead sends each pair a short reconciliation sheet containing only the items where you differ, with its own return date. Nothing is due for reconciliation before then. Task 3 items have one author each; nothing to reconcile.

## Who labels what

**E1 anchor (30 questions, 3 runs each).** Two authors per question, by rotation along a fixed order: odd positions go to A+B, even positions to C+D. All three runs of a question go to the same pair; the other pair never sees that question.

- **A+B** label: {', '.join(qs['A+B'])}
- **C+D** label: {', '.join(qs['C+D'])}

Each author labels 15 questions = 45 runs. The question numbers (`Q01`...) are shown in the form as "Anchor Q07 run 2"; `data/assignments.csv` lists every item and its authors.

**E1 dev (20 runs, two authors each).** A+B label {dn['A+B']} runs, C+D label {dn['C+D']} runs (an earlier fixed assignment, so A and B have more).

**E2 spot-checks, wave 1 (one author per item).** {'; '.join(f'**{a}**: '+', '.join(v) for a,v in sp.items())}.


## Hours and dates (planning estimates; please record your real minutes)

Counted in calendar days from the day this folder is sent, assumed to be Sunday 8 November 2026 (day 0). If it goes out later, every date slides by the same number of days.

{t}

How the hours were worked out (planning estimates, not measured): **anchor** 1.575 person-hours per question for the *pair* together (double labelling 1.025 h plus fact specification and reconciliation 0.55 h), so each of the two authors carries half: 15 questions × 1.575 ÷ 2 = 11.81 h. **Dev**: 0.875 person-hours per run for the pair, so each author carries half: A and B 12 runs × 0.875 ÷ 2 = 5.25 h, C and D 8 runs = 3.5 h. **Spot-checks**: 7 minutes per item. **Calibration**: a flat 2.1 h reserve. Graph and ranking runs from Silo-Bench can take longer than average; please record your real minutes on every item, and stop at the time cap in the guideline (the only cap is for graph and ranking runs in Task 1-2; the 2.1 h calibration figure is a flat reserve for reading the guidelines and doing the five calibration runs). **Still to come, sent separately:** wave-2 spot-checks (about 0.17 h each, 2 items each). The totals above do not include a spot-check margin: please budget about 1 h extra per author for the spot-check tasks.

## How to do the work

1. Open `forms/labelling_form.html`. Pick **your letter** and the **task**. The form shows only your own items. (The file contains everyone's blank rows; please do not browse your partner's.)
2. Read the guideline (the box at the top of the page, or the file in `guidelines/`). Each task has worked examples and edge cases (uncertain, partial vs. distorted, joint facts, data-list records).
3. Fill in every box for an item. Choice boxes show the allowed answers: where "uncertain" is offered you may use it (add a reason). For the E1 call the way to say "uncertain" is `exclude_uncertain`. The `annotator_id` field in the file is filled in by the form automatically.
4. Press **Save my rows**. This downloads one file named `<task>_<authorID>_<versiontag>.json`, for example `E1anchor_A_{VERSION}.json` (the tag is the version at the top of this page). You can save more than once; the last file replaces the earlier one. Your typing is also kept in the browser automatically, but the downloaded file is what counts.
5. **Return your files.** The channel is the one line below; keep the file names exactly as downloaded and do not edit the files by hand. A file counts as **received** when the intake check accepts it and your row in `STATUS.md` shows it.

**RETURN CHANNEL:** authors email their files to the lead annotator, who saves them unchanged in `rebuttal/annotation/returns/`, where the intake check reads them.

6. If something is unclear, write it in the item's `rationale` or `uncertain_reason` box, and tell the lead by replying to the message that sent you this folder (the lead's contact is whoever sent it); do not guess.

## What this folder never contains

No audit output, tracker (matcher) output, judge output, lexical score or baseline-method output; no model names or run names. Items are named by number only. The files were checked for this before sending. The answer text a system produced, and the unit ids, may be formatted differently from run to run; that is not information. If you ever see something that looks like an automatic verdict, stop and tell the lead.

## Folder map

- `README.md`: this page.
- `VERSION` and `CHANGELOG.md`: the version tag and what changed.
- `guidelines/`: one guideline per task type.
- `data/`: the sheets (`T*.jsonl`) and `assignments.csv`.
- `forms/labelling_form.html`: the offline form.
- `CHECKSUMS.sha256`: SHA-256 of every other file (`shasum -a 256 -c CHECKSUMS.sha256` from inside this folder).

If you were sent an earlier packet (named `author_packet_20261108`), it is **superseded**; do not use it.
'''
    (F/'README.md').write_text(readme)
    lines=[]
    for p in sorted(F.rglob('*')):
        if p.is_file() and p.name!='CHECKSUMS.sha256':lines.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(F)}')
    (F/'CHECKSUMS.sha256').write_text('\n'.join(lines)+'\n')
    print(t)
if __name__=='__main__':main()
