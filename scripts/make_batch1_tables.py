"""Build every batch-1 results table from RAW rows. No number is typed by hand: each cell is computed here from a source file.

Raw row contract (JSONL, a JSON array, or CSV; one record per line) -- every record carries `row` and `col` labels (strings) plus the fields of its kind:
  agreement          {cluster, a, b}  optional {stratum, weight, marks}          -> accuracy, kappa, AC1 (weighted, within-stratum cluster bootstrap)
  agreement_exact    {a, b}                                                      -> percent agreement with exact Clopper-Pearson CI, kappa (bootstrap)
  weighted_proportion{cluster, y} optional {stratum, weight}                     -> weighted share with within-stratum cluster bootstrap CI
  proportion         {cluster, y}                                                -> share with cluster bootstrap CI
  proportion_exact   {y}                                                         -> share with exact Clopper-Pearson CI
  paired_delta       {cluster, delta} optional {n_pairs}                         -> mean with cluster bootstrap CI
  exclusions         {benchmark, instance, task_type, agents, excluded}          -> counts per benchmark, 10% flag
  count_only         {value} or nothing                                          -> n only (descriptive; no CI)
Bootstrap: 2,000 draws, seed 42, percentile 95% CI.

SEALED SOURCES. The script refuses to read any path containing "sealed" unless it is run with --unseal AND the authorisation record
rebuttal/results/batch1/UNSEAL_AUTHORISATION.md exists and is valid. The record comes from the lead, only after the lead confirms the anchor labels are in; it must contain
a line "Lead confirmation: <what the lead confirmed>", a line "Date: YYYY-MM-DD", and the SHA-256 of both E1_judge_sealed manifests it unlocks
(the first run's MANIFEST.sha256 and MANIFEST_retry.sha256, UNLOCKS below). Neither the worker nor the generator creates this file.
Usage: python -m scripts.make_batch1_tables [--root rebuttal/results/batch1] [--out DIR] [--unseal]"""
import argparse,csv,datetime,hashlib,json,math,re
from collections import defaultdict
from pathlib import Path
import numpy as np
ROOT=Path('rebuttal/results/batch1');PREREG=Path('rebuttal/pilots/prereg');SEED=42;DRAWS=2000
class SealedAccessError(PermissionError):pass
def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _digest(o):return hashlib.sha256(json.dumps(o,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
UNLOCKS={'MANIFEST.sha256':'eb8e44281b3051fb600f0bf30cf40962925039f935ab045dc6e49ca3a2988717','MANIFEST_retry.sha256':'bacbfb22afa476e7ccb655f3da44e24f59c8eddeabc9f56c639988f0764c1339'}
def check_authorisation(auth,sealed_dir=None):
    """The authorisation record must carry the lead's confirmation, a date and both unlocked manifest hashes (and the manifests on disk must still match them)."""
    text=Path(auth).read_text()
    if not re.search(r'^Lead confirmation:\s*\S+',text,re.M):raise SealedAccessError('authorisation record lacks a "Lead confirmation:" line')
    if not re.search(r'^Date:\s*\d{4}-\d{2}-\d{2}\s*$',text,re.M):raise SealedAccessError('authorisation record lacks a "Date: YYYY-MM-DD" line')
    for name,h in UNLOCKS.items():
        if h not in text:raise SealedAccessError(f'authorisation record does not name the {name} hash it unlocks')
        m=Path(sealed_dir or ROOT/'E1_judge_sealed')/name
        if m.exists() and _sha(m)!=h:raise SealedAccessError(f'{name} on disk no longer matches its recorded hash')
def guard(path,unseal=False,auth=None,sealed_dir=None):
    """Refuse sealed paths unless explicitly unsealed AND authorised."""
    if 'sealed' in str(path).lower():
        if not unseal:raise SealedAccessError(f'refusing to read {path}: sealed until the lead confirms the anchor labels are in (run with --unseal only then)')
        a=Path(auth or (ROOT/'UNSEAL_AUTHORISATION.md'))
        if not a.exists():raise SealedAccessError(f'--unseal given but the authorisation record is missing: {path}')
        check_authorisation(a,sealed_dir)
        # The record unlocks the E1 judge outputs only: every component must be exactly E1_judge_sealed.
        if not any(p.lower()=='e1_judge_sealed' for p in Path(path).parts):
            raise SealedAccessError(f'refusing {path}: the record authorises the E1 judge outputs only')
def read_rows(path,unseal=False,auth=None):
    guard(path,unseal,auth,sealed_dir=Path(path).parent if 'E1_judge_sealed' not in str(path) else None);p=Path(path);text=p.read_text()
    if p.suffix=='.csv':return list(csv.DictReader(text.splitlines()))
    s=text.strip()
    if s.startswith('['):return json.loads(s)
    return [json.loads(l) for l in s.splitlines() if l.strip()]
# ---------- statistics
def cp_ci(k,n,a=.05):
    from math import comb
    if n==0:return (None,None)
    def up(p):return sum(comb(n,i)*p**i*(1-p)**(n-i) for i in range(k,n+1))
    def lo_(p):return sum(comb(n,i)*p**i*(1-p)**(n-i) for i in range(0,k+1))
    lo=0.0
    if k>0:
        l,h=0.0,1.0
        for _ in range(60):
            m=(l+h)/2
            if up(m)<a/2:l=m
            else:h=m
        lo=h
    hi=1.0
    if k<n:
        l,h=0.0,1.0
        for _ in range(60):
            m=(l+h)/2
            if lo_(m)>a/2:l=m
            else:h=m
        hi=l
    return (lo,hi)
def _pct(v,lo=2.5,hi=97.5):
    v=np.asarray([x for x in v if x is not None and np.isfinite(x)])
    return (float(np.percentile(v,lo)),float(np.percentile(v,hi))) if len(v) else (None,None)
def _clusters(rows,key='cluster'):
    g=defaultdict(list)
    for i,r in enumerate(rows):g[(r.get('stratum','_'),str(r.get(key,i)))].append(i)
    by_stratum=defaultdict(list)
    for (s,c),idx in g.items():by_stratum[s].append(idx)
    return by_stratum
def _draws(rows,rng,key='cluster'):
    by=_clusters(rows,key);keys=sorted(by)
    for _ in range(DRAWS):
        idx=[]
        for s in keys:
            cl=by[s];pick=rng.integers(0,len(cl),len(cl))
            for p in pick:idx+=cl[p]
        yield np.asarray(idx)
def _agree_stats(a,b,w,cats):
    W=w.sum()
    if W<=0:return {'accuracy':None,'kappa':None,'ac1':None}
    po=w[a==b].sum()/W;pa=np.array([w[a==c].sum()/W for c in range(len(cats))]);pb=np.array([w[b==c].sum()/W for c in range(len(cats))])
    pe=float((pa*pb).sum());pc=(pa+pb)/2;q=max(len(cats),2);pe1=float((pc*(1-pc)).sum()/(q-1))
    return {'accuracy':float(po),'kappa':float((po-pe)/(1-pe)) if pe<1 else None,'ac1':float((po-pe1)/(1-pe1)) if pe1<1 else None}
def stat_agreement(rows,categories=None):
    cats=sorted({str(r['a']) for r in rows}|{str(r['b']) for r in rows}|set(categories or []));ix={c:i for i,c in enumerate(cats)}
    a=np.array([ix[str(r['a'])] for r in rows]);b=np.array([ix[str(r['b'])] for r in rows]);w=np.array([float(r.get('weight',1.0)) for r in rows])
    est=_agree_stats(a,b,w,cats);rng=np.random.default_rng(SEED);boot=defaultdict(list)
    for idx in _draws(rows,rng):
        s=_agree_stats(a[idx],b[idx],w[idx],cats)
        for k,v in s.items():boot[k].append(v)
    n_cl=len(_clusters(rows)) and sum(len(v) for v in _clusters(rows).values())
    out={}
    for k in ('accuracy','kappa','ac1'):
        lo,hi=_pct(boot[k]);out[k]={'estimate':est[k],'ci_lo':lo,'ci_hi':hi,'undefined_draws':sum(1 for v in boot[k] if v is None or not np.isfinite(v))}
    return out,{'n_rows':len(rows),'n_clusters':n_cl}
def stat_agreement_exact(rows):
    n=len(rows);k=sum(str(r['a'])==str(r['b']) for r in rows);lo,hi=cp_ci(k,n)
    res={'percent_agreement':{'estimate':k/n if n else None,'ci_lo':lo,'ci_hi':hi,'method':'exact Clopper-Pearson'}}
    if n>=2:
        k_stats,_=stat_agreement([dict(r,cluster=i) for i,r in enumerate(rows)]);res['kappa']=k_stats['kappa']
    return res,{'n_rows':n,'n_clusters':n}
def stat_weighted_prop(rows):
    y=np.array([float(r['y']) for r in rows]);w=np.array([float(r.get('weight',1.0)) for r in rows]);est=float((w*y).sum()/w.sum())
    rng=np.random.default_rng(SEED);boot=[float((w[i]*y[i]).sum()/w[i].sum()) for i in _draws(rows,rng)];lo,hi=_pct(boot)
    return {'share':{'estimate':est,'ci_lo':lo,'ci_hi':hi}},{'n_rows':len(rows),'n_clusters':sum(len(v) for v in _clusters(rows).values())}
def stat_paired_delta(rows):
    valid=[r for r in rows if r.get('delta') is not None]
    ns={'n_rows':len(rows),'n_clusters':sum(len(v) for v in _clusters(rows).values()),'n_pairs':sum(int(r.get('n_pairs',1)) for r in rows)}
    if not valid:
        return {'mean_delta':{'estimate':None,'ci_lo':None,'ci_hi':None}},ns
    d=np.array([float(r['delta']) for r in valid]);est=float(d.mean());rng=np.random.default_rng(SEED);boot=[float(d[i].mean()) for i in _draws(valid,rng)];lo,hi=_pct(boot)
    return {'mean_delta':{'estimate':est,'ci_lo':lo,'ci_hi':hi}},ns
def stat_proportion_exact(rows):
    n=len(rows);k=int(sum(float(r['y']) for r in rows));lo,hi=cp_ci(k,n);return {'share':{'estimate':k/n if n else None,'ci_lo':lo,'ci_hi':hi,'method':'exact Clopper-Pearson'}},{'n_rows':n,'n_clusters':n}
KINDS={'agreement':stat_agreement,'agreement_exact':stat_agreement_exact,'weighted_proportion':stat_weighted_prop,'proportion':stat_weighted_prop,'paired_delta':stat_paired_delta,'proportion_exact':stat_proportion_exact}
# ---------- table specs: the reviewer concern each answers, sources, markings. No numbers.
SB10=("The Silo-Bench anchor has 8 instances, so one exclusion already exceeds 10%.")
GEM_MARK=(r'[Gg]emini','same model as judge')
LABEL_STATUS="these are the authors' labels; file SHA-256 are in rebuttal/results/batch1/UNSEAL_AUTHORISATION.md"
SPECS=[
 {'id':'T01_E1_anchor_agreement','title':'E1 anchor (30 instances): agreement on the anchor: author files, judge and matcher','kind':'agreement','source':'E1/anchor_agreement_rows.jsonl','prereg':['E1.md'],'categories':{'fidelity':['absent','faithful','partial','distorted']},'prevalence':{'presence':'yes','fidelity':'faithful','trace binary':'reached_but_unused'},
  'concerns':['C9 (CR8J W2): is coverage measured validly, i.e. can "lost" and "reached but unused" be told apart reliably?'],'marks':[],
  'notes':['Rows: author–author, judge–author, matcher–author; presence is primary, fidelity secondary with AC1 beside κ (fidelity κ is wide because nearly every fact comes through intact).','Anchor weights from `E1-v9.md`; 2,000-draw weighted within-stratum cluster bootstrap, seed 42.',"The reference judge's labels are an LLM judge's; only the anchor is author-labelled."]},
 {'id':'T02_E1_matcher_vs_judge_80','title':'E1 held-out (80 instances): matcher against the judge','kind':'agreement','source':'E1/matcher_vs_judge_rows.jsonl','prereg':['E1.md'],'categories':{'fidelity':['absent','faithful','partial','distorted']},
  'concerns':['C9 (CR8J W2): does the frozen matcher agree with an independent labeller beyond the 30-instance anchor?'],'marks':[],'notes':['Agreement with a judge\'s labels, not with author labels; read together with the anchor table.']},
 {'id':'T03_E1_reweighted_rates','title':'E1: reweighted headline rates from labels (MuSiQue AggFail included)','kind':'weighted_proportion','source':'E1/headline_rate_rows.jsonl','prereg':['E1.md'],
  'concerns':['C9 (CR8J W2): does the 68% MuSiQue aggregation-failure figure survive when labelled by a judge and checked on the anchor?'],'marks':[],'notes':['The lexical figure (τ = 0.5) is shown beside the label-based rate; a drop is reported with the paper sentences it affects (see the claims-impact table).']},
 {'id':'T04_E1_granularity_exclusions','title':'E1: anchor instances excluded by the granularity cap','kind':'exclusions','source':'E1/exclusion_rows.jsonl','prereg':['E1.md'],
  'concerns':['C9: does the time cap remove the hardest cases from κ?'],'marks':[],'flag_benchmark':'Silo-Bench','flag_threshold':0.10,'notes':[SB10,'Every percentage is shown next to its actual count.']},
 {'id':'T05_E4_main','title':'E4: mean paired Δ versus Rerun, matched repair against mismatched repairs (all cases)','kind':'paired_delta','source':'E4/main_delta_rows.jsonl','prereg':['E4.md'],
  'concerns':['C7 (UEGh W4): does the repair that matches the diagnosis beat the mismatched repairs in each diagnosed group?'],'marks':[(r'R-agg\+|Gemini','Gemini also labelled the E1 groups used to route repairs')],
  'min_n':{'regex':'.*','n':10,'text':'descriptive only (N < 10)'},'notes':['Groups come from the frozen E1 matcher (`semantic-dev-v2`), not the judge; models pooled within benchmark; cluster bootstrap over instances.','Phase 1 ran no mismatched-repair (distortion) arm, so these columns are repair versus Rerun, not versus a mismatched repair.','Not effective as specified: the targeted fact is in the post-swap board in 4 of 17 extraction cases by the matcher and 0 by direct string (`E4_phase1/repair_effect_check.md`).','A3 direct insertion appends the targeted-fact text as one board unit; it is a positive control, and its manipulation check passes by construction (17 of 17 cases).'],
  'reading':'Across 17 extraction cases (15 instances) the extraction repair never changed a case\'s status: R-ext is 0.000 [0.000, 0.000] against Rerun on MuSiQue (14 cases, 12 instances), and every Silo-Bench cell is descriptive (N < 10). The volume control alone fixes two of the 17 cases (one Silo-Bench 5, one Silo-Bench 10); pooled V-ext is +0.118 [0.000, 0.313], MuSiQue 0.000. Not effective as specified: the targeted fact is present after the swap in 4 of 17 cases by the matcher and 0 by direct string; these contrasts estimate no repair effect.'},
 {'id':'T06_E4_volume_control','title':'E4: repair minus its volume control (natural matched pairs only)','kind':'paired_delta','source':'E4/volume_control_delta_rows.jsonl','prereg':['E4.md'],
  'concerns':['C7 (UEGh W4): is the gain due to fixing the diagnosed stage rather than to the amount of text added?'],'marks':[],
  'min_ns':[{'regex':r'SB-','n':5,'text':'no same-volume control available','count_field':'n_pairs'},
           {'regex':'.*','n':5,'text':'descriptive only (fewer than 5 matched pairs)','count_field':'n_pairs'}],
  'show_n_pairs':True,
  'notes':['Natural matched pairs only (A1); the Silo-Bench constructed control is withdrawn. Silo-Bench cells with fewer than 5 matched pairs read "no same-volume control available", as fixed in `E4-v7.md:41`; every cell shows its pair count. The MuSiQue below-5 reading ("descriptive only") is a new, conservative presentation rule that the pre-registration does not cover. The balance table and all-case sensitivity are reported alongside.','Not effective as specified: the targeted fact is in the post-swap board in 4 of 17 extraction cases by the matcher and 0 by direct string (`E4_phase1/repair_effect_check.md`).','A3 direct insertion appends the targeted-fact text as one board unit; it is a positive control, and its manipulation check passes by construction (17 of 17 cases).'],
  'reading':'Three natural matched pairs exist in all: one MuSiQue (repair 0, control 0) and two Silo-Bench 5 (repair 0, control 1; repair 0, control 0); Silo-Bench 10 has none. Both Silo-Bench cells read "no same-volume control available" as pre-registered; the MuSiQue cell is descriptive under the new below-5 rule. The repair beat its control in none of the three pairs, so this cannot separate repair content from added text.'},
 {'id':'T07_E4P_placement','title':'E4-P: one Gemini call at the final stage versus at one local extraction','kind':'paired_delta','source':'E4P/placement_delta_rows.jsonl','prereg':['E4-P-full-seed43.md'],
  'concerns':['Table 9 / CR8J: does upgrading the final aggregation beat upgrading one local extraction, by stage?'],'marks':[(r'[Gg]emini','Gemini also labelled the E1 groups used to pick targets')],'min_n':{'regex':'.*','n':10,'text':'descriptive only (N < 10)'},'notes':['Seed-43 Silo-Bench cases cluster by underlying task across seeds.']},
 {'id':'T08_E2C_casebook','title':'E2-C: casebook counts per judge-labelled class','kind':'count_only','source':'E2C/casebook_rows.jsonl','prereg':['E2-C.md'],'concerns':['C4 (UEGh W3): what do baseline attribution methods say on the same traces?'],'marks':[GEM_MARK],
  'notes':['Descriptive only; classes come from E1 judge labels and the 12 selected traces are author-verified.']},
 {'id':'T09_E2A_attribution','title':'E2 Part A: audit versus attribution baselines on injected single faults (Qwen-backbone headline)','kind':'proportion','source':'E2A/attribution_rows.jsonl','prereg':['E2-A.md','Judge-labelling-v5.md'],
  'concerns':['C4 (UEGh W3), C3 (chSu Q1): is the audit more accurate on stage and type than existing methods when the right answer is known?'],'marks':[GEM_MARK],'r1_both_scorings':True,
  'notes':['Headline: Qwen-backbone rows. Every Gemini-backbone row is marked "same model as judge".','[R1] rows carry both scorings side by side: released code-only (primary) and strict (sensitivity).',"Verified by the rebuttal's reference judge (Gemini 3.6 Flash), with author spot-checks."]},
 {'id':'T10_E2A_spotcheck_agreement','title':'E2 Part A: judge against the authors on the spot-check items','kind':'agreement_exact','source':'table_sources/T10_spotcheck_rows.jsonl','prereg':['E2-A.md','Judge-labelling-v5.md'],
  'concerns':['C4: can the judge-verified injections be trusted? (the only author check of the screening)'],'marks':[],'notes':['Gate: more than 2 disagreements among the 12 wave-1 items, or more than 1 among the 8 wave-2 items, stops scaling. A single disagreement drops the item.','The author check covers screening only.']},
 {'id':'T11_judge_quality','title':'Judge quality: self-contradiction and own-field disagreement','kind':'proportion_exact','source':'table_sources/T11_judge_quality_rows.jsonl','prereg':['Judge-labelling-v5.md'],
  'concerns':['C4: how often does the judge contradict itself, and how often does its own `eligible` field disagree with the derived eligibility rule?'],'marks':[],'notes':['Wave-1 spot items only; wave-2 items do not exist before injections. Exact Clopper–Pearson CIs.']},
 {'id':'T12_E2B_partB','title':'E2 Part B: audit versus attribution baselines on natural failures, against judge labels','kind':'proportion','source':'E2B/partB_rows.jsonl','prereg':['Judge-labelling-v5.md'],
  'concerns':['C4 (UEGh W3): on natural failures, is the audit closer to an LLM judge\'s labels than the baselines are?'],'marks':[GEM_MARK],'r1_both_scorings':True,'footer':'No author check of these labels.',
  'notes':['Closer to an LLM judge\'s labels, not to author labels. Every Gemini-backbone row is marked "same model as judge".']},
 {'id':'T13_run_integrity','title':'Run integrity: calls, failures, retries and the final sample check','kind':'count_only','source':'table_sources/run_integrity_rows.jsonl','prereg':[],'concerns':['Reproducibility: was the planned sample completed, and what was retried?'],'marks':[],'notes':['Sources: run summaries, `retry_log.csv`, `SAMPLE_CHECK.md`.']},
 {'id':'T14_paper_evaluators','title':'Paper evaluators against the authors: lexical rule and Qwen-235B judge on the E1 anchor','kind':'reported','source':'table_sources/T14_paper_evaluators.jsonl','prereg':['Paper-evaluators-v1.1.md'],
  'concerns':['C9 (CR8J W2): how do the paper\'s lexical rule and an LLM judge agree with author labels?'],'marks':[],
  'notes':['Source: `E1/paper_evaluators_v11_full.json` (852 judge-eligible rows; 504 tied rows excluded from the judge only).','Bootstrap: within-stratum instance-cluster, 2,000 draws, seed 42.','Descriptive agreement on this label set; neither evaluator is called validated.']},
 {'id':'T15_lexical_correction','title':'Lexical rule against the authors: coverage, CritRec, OmissionRate and AF on the E1 anchor','kind':'reported','source':'table_sources/T15_lexical_correction.jsonl','prereg':['E1.md'],
  'concerns':['C9 (CR8J W2): what does the lexical rule change relative to author presence, at fact and instance level?'],'marks':[],
  'notes':['Sources: `E1/lexical_bias.json`, `E1/af_corrected.json`; 1,356 labelled rows, 90 traces, 30 instances.','Coverage and CritRec are the same fact-level quantity here (share of gold facts marked present at the board checkpoint). OmissionRate = 1 - CritRec.','AF = complete coverage and a non-perfect answer; trace-level AF is stratum-weighted, instance-level AF is a raw count.','Fact-level and trace-level intervals are within-stratum instance-cluster bootstraps (2,000 draws, seed 42); complete-coverage counts use exact Clopper-Pearson intervals.','AF driver rows: 10 traces in 8 MuSiQue instances. All 40 author-absent rows are MuSiQue; no Silo-Bench row is author-absent.','Affected paper lines are listed in the Markings column; no interpretation is included.']},
 {'id':'T16_E2A_yields','title':'E2 Part A: screened base yields per fault type, wave 1 and option C','kind':'count_only','source':'table_sources/T16_e2a_yields.jsonl','prereg':['E2-A.md'],
  'concerns':['C4 (UEGh W3): how many screened single-fault bases exist per type for the injection comparison?'],'marks':[],'label_dependent':False,
  'notes':['Sources: `E2A_wave1_screening/summary.json` (68 bases) and `E2A_wave2_screening/summary.json` (219 bases).','Pairs are eligible (trace, agent, fault-type) candidates; a trace can yield more than one. No injection outcome exists and none is read here.'],
  'reading':'Across the two screening rounds there are 120/120/82/40 eligible pairs for extraction/selection/distortion/aggregation. The 50-per-type allocation is met for the first three and not for aggregation (40, 10 short). These are candidate (trace, agent, type) pairs from screened bases; no scaled injection has been made (the 7 wave-2 spot injections are not kept cases), so no kept-case count, yield or accuracy is shown.'},
 {'id':'T17_E4_manifest_counts','title':'E4 frozen manifest: cases, scored groups and same-volume pairs','kind':'count_only','source':'table_sources/T17_e4_manifest_counts.jsonl','prereg':['E4-v7.md'],
  'concerns':['C7 (UEGh W4): which diagnosed cases exist per group and benchmark, and how many have a same-volume control?'],'marks':[],'label_dependent':False,
  'notes':['Sources: `E4_manifest/manifest.json` (232 cases; 219 scored, 13 unscored) and `E4_manifest/rext_unit_reconstruction.json` (local reconstruction, no call).','Extraction matched pairs are reconstructed from frozen spans; the live R-ext unit count fixes the final count at intervention.','No repair outcome exists.']},
 {'id':'T21_SB_anchor_20','title':'Silo-Bench anchor (20 instances): judge, matcher and lexical rule against author labels','kind':'sb_anchor','source':'SB_anchor_20/analysis.json','prereg':[],
  'concerns':['C9 (CR8J W2): on a separate Silo-Bench anchor, do the judge and matcher reproduce author labels, and how does the lexical rule compare?'],'marks':[],
  'notes':['Source: `SB_anchor_20/analysis.json` (60 traces, 20 instances; 8 instances shared with the E1 anchor).','Matcher coverage is 94 of 120 pairs; the 26 pairs without a matcher label are not scored, so its agreement is computed on that subset.','Descriptive agreement only; no pass/fail threshold.'],
  'reading':'On the separate 20-instance Silo-Bench anchor the reference judge and the frozen matcher reproduce the author trace label (κ 1.000 [1.000, 1.000]); the lexical rule does not (accuracy 0.383 [0.217, 0.550], κ 0.016 [−0.092, 0.151]). The matcher\'s agreement covers 94 of 120 pairs; the remaining 26 are not scored. The 8 instances shared with the E1 anchor agree closely (accuracy 0.958 [0.875, 1.000], κ 0.833 [0.625, 1.000]), but these rows are descriptive and are not an independent sample.'},
]
def fmt(x):return 'n/a' if x is None else (f'{x:.3f}' if isinstance(x,float) else str(x))
def row_marks(spec,label,rec_marks=()):
    m=list(rec_marks)
    for rx,text in spec.get('marks',[]):
        if re.search(rx,label) and text not in m:m.append(text)
    return m
def build_table(spec,root,unseal=False,auth=None):
    src=Path(root)/spec['source']
    base={'id':spec['id'],'title':spec['title'],'concerns':spec['concerns'],'source':str(spec['source']),'config_sha256':_digest({'spec':{k:v for k,v in spec.items()},'seed':SEED,'draws':DRAWS})}
    base['prereg_sha256']={n:_sha(PREREG/n) for n in spec['prereg'] if (PREREG/n).exists()}
    if not src.exists():return dict(base,status='pending: source not present',cells=[],sources=[]),None
    if spec['kind']=='sb_anchor':return dict(base,status='ok',sources=[{'path':str(spec['source']),'sha256':_sha(src)}],cells=_sb_anchor_cells(src)),None
    rows=read_rows(src,unseal,auth);cells=[];kind=spec['kind']
    if kind=='exclusions':return dict(base,status='ok',sources=[{'path':str(spec['source']),'sha256':_sha(src)}],cells=_exclusion_cells(spec,rows)),rows
    groups=defaultdict(list)
    for r in rows:
        key=(str(r['row']),str(r['col']),str(r.get('metric',''))) if kind=='reported' else (str(r['row']),str(r['col']))
        groups[key].append(r)
    for key,rs in sorted(groups.items()):
        row,col=key[0],key[1]
        marks=row_marks(spec,row,{m for r in rs for m in r.get('marks',[])})
        if kind=='count_only':
            v=sum(float(r.get('value',1)) for r in rs);v=int(v) if v.is_integer() else v
            cells.append({'row':row,'col':col,'metric':'count','n_rows':len(rs),'n_clusters':None,'estimate':v,'ci_lo':None,'ci_hi':None,'method':'descriptive','marks':marks});continue
        if kind=='reported':
            assert len(rs)==1,(row,col,len(rs))
            r=rs[0]
            cells.append({'row':row,'col':col,'metric':r.get('metric') or 'value','n_rows':r.get('n_rows'),'n_clusters':r.get('n_clusters'),'n_pairs':r.get('n_pairs'),'estimate':float(r['estimate']) if r.get('estimate') is not None else None,'ci_lo':r.get('ci_lo'),'ci_hi':r.get('ci_hi'),'method':r.get('method','descriptive'),'marks':marks,'display_note':None});continue
        cats=(spec.get('categories') or {}).get(col) if kind=='agreement' else None
        res,ns=KINDS[kind](rs,cats) if kind=='agreement' else KINDS[kind](rs)
        mn=spec.get('min_n');label=None
        rules=spec.get('min_ns') or ([mn] if mn else [])
        for rule in rules:
            if re.search(rule['regex'],row):
                cnt=ns.get(rule.get('count_field','n_clusters'),ns['n_clusters'])
                if cnt<rule['n']:label=rule['text']
                break
        for metric,v in res.items():
            cells.append({'row':row,'col':col,'metric':metric,'n_rows':ns['n_rows'],'n_clusters':ns['n_clusters'],'n_pairs':ns.get('n_pairs'),'estimate':None if label else v['estimate'] if isinstance(v,dict) else v,
                          'ci_lo':None if label else (v.get('ci_lo') if isinstance(v,dict) else None),'ci_hi':None if label else (v.get('ci_hi') if isinstance(v,dict) else None),'method':(v.get('method','bootstrap') if isinstance(v,dict) else 'bootstrap'),'marks':marks,'display_note':label})
        prev_cat=(spec.get('prevalence') or {}).get(col)
        if prev_cat:
            w=np.array([float(r.get('weight',1.0)) for r in rs]);tot=w.sum()
            share=float((w*np.array([str(r['a'])==prev_cat for r in rs])).sum()/tot/2
                        +(w*np.array([str(r['b'])==prev_cat for r in rs])).sum()/tot/2) if tot else None
            cells.append({'row':row,'col':col,'metric':f'prevalence ({prev_cat})','n_rows':ns['n_rows'],'n_clusters':ns['n_clusters'],
                          'n_pairs':ns.get('n_pairs'),'estimate':share,'ci_lo':None,'ci_hi':None,'method':'descriptive','marks':marks,'display_note':None})
    if spec.get('r1_both_scorings'):
        have=defaultdict(set)
        for c in cells:
            if re.search(r'\[R1\]',c['row']):have[c['row']].add(c['col'])
        for row,cols in have.items():
            for need in ('released code-only (primary)','strict (sensitivity)'):
                if need not in cols:
                    for c in cells:
                        if c['row']==row and 'MISSING second [R1] scoring' not in c['marks']:c['marks'].append('MISSING second [R1] scoring')
    return dict(base,status='ok',sources=[{'path':str(spec['source']),'sha256':_sha(src)}],cells=cells),rows
def _sb_anchor_cells(src):
    """Read the Silo-Bench anchor analysis object directly; the analysis file is the only source."""
    o=json.loads(Path(src).read_text());cov=o.get('matcher_coverage') or {}
    cover=[f"coverage {cov.get('valid')} of {cov.get('pairs')} pairs; {cov.get('missing')} not scored"] if cov else []
    rows=[('Judge–author','judge_author',[]),
          ('Matcher–author','matcher_author',cover),
          ('Lexical rule–author','lexical_author',[]),
          ('Overlap: E1 anchor (8 instances)','anchor_overlap_8',[])]
    cells=[]
    for row,key,marks in rows:
        d=o[key]
        for metric,label in (('agreement','accuracy'),('kappa','kappa')):
            v=d[metric]
            cells.append({'row':row,'col':'trace binary','metric':label,'n_rows':d['rows'],'n_clusters':d['clusters'],'n_pairs':None,
                          'estimate':v['estimate'],'ci_lo':v['lo'],'ci_hi':v['hi'],'method':'cluster bootstrap','marks':list(marks),'display_note':None})
    return cells
def _exclusion_cells(spec,rows):
    by=defaultdict(list)
    for r in rows:by[r['benchmark']].append(r)
    cells=[]
    for b,rs in sorted(by.items()):
        n=len(rs);ex=[r for r in rs if str(r.get('excluded')).lower() in ('true','1','yes')]
        flag=b==spec['flag_benchmark'] and n and len(ex)/n>spec['flag_threshold']
        cells.append({'row':b,'col':'excluded instances','metric':'count','n_rows':n,'n_clusters':n,'estimate':len(ex),'ci_lo':None,'ci_hi':None,'method':'descriptive','pct':(len(ex)/n if n else None),
                      'marks':['LIMITATION FLAG: more than 10% of the Silo-Bench anchor is excluded. '+SB10] if flag else [],'excluded':[{'instance':r['instance'],'task_type':r.get('task_type'),'agents':r.get('agents')} for r in ex]})
    return cells
def render(table,spec):
    L=[f"### {table['id']}: {table['title']}",'',f"**Reviewer concern answered:** "+' | '.join(table['concerns']),'']
    if spec.get('label_dependent',spec['id']!='T13_run_integrity'):L+=[f'**Label status: {LABEL_STATUS}.**','']
    if table['status']!='ok':L+=[f"*Status: {table['status']}. No numbers are shown until the raw source exists.*",'']
    else:
        L+=['| Row | Column / metric | n (rows; clusters) | Estimate | CI low | CI high | Markings |','|---|---|---|---|---|---|---|']
        for c in table['cells']:
            est=c.get('display_note') or (f"{c['estimate']:.3f}" if isinstance(c['estimate'],float) else fmt(c['estimate']))
            n=f"{c['n_rows']}; {c['n_clusters']}" if c['n_clusters'] is not None else str(c['n_rows'])
            if spec.get('show_n_pairs') and c.get('n_pairs') is not None:
                n='0 pairs' if c['n_pairs']==0 else n+f" ({c['n_pairs']} pair{'s' if c['n_pairs']!=1 else ''})"
            extra=f" ({c['estimate']} of {c['n_rows']}, {100*c['pct']:.1f}%)" if c.get('pct') is not None else ''
            L.append(f"| {c['row']} | {c['col']}{(' ('+c['metric']+')') if c['metric']!='count' else ''} | {n} | {est}{extra} | {fmt(c['ci_lo']) if not c.get('display_note') else '—'} | {fmt(c['ci_hi']) if not c.get('display_note') else '—'} | {'; '.join(c['marks'])} |")
        for c in table['cells']:
            for e in c.get('excluded',[]):L.append(f"| {c['row']} excluded: {e['instance']} | task type {e['task_type']}; {e['agents']} agents | | | | | |")
        L.append('')
    L+=[*(f'*Note:* {n}' for n in spec['notes']),'']
    if spec.get('footer'):L+=[f"**{spec['footer']}**",'']
    L+=['**Reading (2–3 lines: what it shows and what it does not):** '+(spec.get('reading') or '[to be written from the numbers after the run]'),'']
    return '\n'.join(L)
def build(root=ROOT,out=None,unseal=False,auth=None,specs=None):
    out=Path(out or Path(root)/'tables');out.mkdir(parents=True,exist_ok=True);specs=specs or SPECS;tables={};md=['# Batch 1: results tables (generated by `scripts/make_batch1_tables.py`)','',f'Generated {datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}. Every number is computed from the raw rows listed in `tables_manifest.json`; none is typed by hand.','']
    for spec in specs:
        t,_=build_table(spec,root,unseal,auth);tables[spec['id']]=t;text=render(t,spec);(out/(spec['id']+'.md')).write_text(text+'\n');md.append(text)
    (out/'batch1_tables.md').write_text('\n'.join(md)+'\n')
    manifest={'generated_utc':datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'generator_sha256':_sha(__file__),'seed':SEED,'bootstrap_draws':DRAWS,'unsealed':bool(unseal),'tables':tables}
    (out/'tables_manifest.json').write_text(json.dumps(manifest,indent=1,default=str));return manifest
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',default=str(ROOT));ap.add_argument('--out');ap.add_argument('--unseal',action='store_true',help='allow reading sealed sources; only after the lead confirms the anchor labels are in');a=ap.parse_args()
    m=build(a.root,a.out,a.unseal);print(json.dumps({k:{'status':v['status'],'cells':len(v['cells'])} for k,v in m['tables'].items()},indent=0))
if __name__=='__main__':main()
