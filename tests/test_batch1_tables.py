import json,random,re
from pathlib import Path
import pytest
from scripts import make_batch1_tables as T
VALID_AUTH=('Lead confirmation: the anchor labels are in; unseal E1_judge_sealed\nDate: 2026-12-01\n'+'\n'.join(f'{n} {h}' for n,h in T.UNLOCKS.items())+'\n')
def jl(path,rows):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
def synthetic(root):
    """SYNTHETIC fixtures only: made-up rows with the raw contract; no real result is used."""
    rng=random.Random(1);root=Path(root)
    def agree(n,cats,strata=('MQ/zero','SB/zero')):return [{'cluster':f'c{i}','stratum':strata[i%2],'weight':1.5+(i%2),'a':rng.choice(cats),'b':rng.choice(cats)} for i in range(n)]
    jl(root/'E1/anchor_agreement_rows.jsonl',[dict(r,row=row,col='presence') for row in ('author–author','judge–author','matcher–author') for r in agree(30,['yes','no'])]+[dict(r,row='judge–author',col='fidelity') for r in agree(40,['faithful','partial'])])
    jl(root/'E1/matcher_vs_judge_rows.jsonl',[dict(r,row='matcher–judge',col='presence') for r in agree(80,['yes','no'])])
    jl(root/'E1/headline_rate_rows.jsonl',[{'row':'MuSiQue AggFail (label-based)','col':'rate','cluster':f'i{i}','stratum':'MQ/zero','weight':1.3,'y':rng.random()<.5} for i in range(60)])
    jl(root/'E1/exclusion_rows.jsonl',[{'benchmark':'MuSiQue','instance':f'm{i}','task_type':'multi-hop','agents':4,'excluded':False} for i in range(22)]+[{'benchmark':'Silo-Bench','instance':f's{i}','task_type':'BFS' if i==0 else 'sum','agents':5 if i==0 else 10,'excluded':i==0} for i in range(8)])
    jl(root/'E4/main_delta_rows.jsonl',[{'row':g,'col':a,'cluster':f'i{i}','delta':rng.uniform(-.2,.4)} for g in ('extraction omission (SB)','aggregation (MQ)') for a in ('R-ext','R-agg','R-agg+ (Gemini)') for i in range(12 if g.startswith('agg') else 6)])
    jl(root/'E4/volume_control_delta_rows.jsonl',[{'row':'selection omission (SB-10)','col':'R-sel minus V-sel','cluster':f'i{i}','delta':rng.uniform(-.1,.3),'n_pairs':1} for i in range(3)]+[{'row':'aggregation (MQ)','col':'R-agg minus generic retry','cluster':f'j{i}','delta':rng.uniform(-.1,.3),'n_pairs':1} for i in range(14)])
    jl(root/'E4P/placement_delta_rows.jsonl',[{'row':f'task {t}','col':'final minus local (Gemini call)','cluster':f't{t}_{i}','delta':rng.uniform(0,.5)} for t in range(2) for i in range(12)])
    jl(root/'E2C/casebook_rows.jsonl',[{'row':c,'col':'traces','value':1} for c in ('extraction','selection','aggregation') for _ in range(2)])
    jl(root/'E2A/attribution_rows.jsonl',[{'row':m,'col':col,'cluster':f'b{i}','y':rng.random()<.5} for m in ('audit (Qwen backbone)','[R1] (Qwen backbone)','[R1] (Gemini backbone)') for col in ('released code-only (primary)','strict (sensitivity)') for i in range(20)]+[{'row':'audit (Qwen backbone)','col':'stage accuracy','cluster':f'b{i}','y':True} for i in range(20)])
    jl(root/'table_sources/T10_spotcheck_rows.jsonl',[{'row':'wave 1','col':'defect-free','a':rng.choice(['yes','no']),'b':rng.choice(['yes','no'])} for _ in range(12)])
    jl(root/'table_sources/T11_judge_quality_rows.jsonl',[{'row':'wave 1','col':'self-contradiction','y':i<2} for i in range(5)])
    jl(root/'table_sources/T14_paper_evaluators.jsonl',[dict(row=r,col='presence',metric=m,n_rows=40,n_clusters=8,estimate=.9,ci_lo=.8,ci_hi=.95,method='bootstrap',marks=[]) for r in ('lexical, all rows','Qwen-235B judge, untied rows') for m in ('accuracy','kappa','ac1')])
    jl(root/'table_sources/T15_lexical_correction.jsonl',[dict(row=r,col=c,n_rows=30,n_clusters=8,estimate=.5,ci_lo=.4,ci_hi=.6,method='cluster bootstrap',marks=[]) for r in ('coverage / CritRec (fact level)','OmissionRate = 1 - CritRec') for c in ('lexical rule',"authors' presence labels")])
    jl(root/'table_sources/T16_e2a_yields.jsonl',[{'row':t,'col':c,'value':v} for t in ('extraction','selection','distortion','aggregation') for c,v in (('wave-1 pairs',10),('option C pairs',20))])
    jl(root/'table_sources/T17_e4_manifest_counts.jsonl',[{'row':g,'col':c,'value':v} for g in ('extraction','distortion','selection','aggregation') for c,v in (('MQ scored',3),('SB-5 scored',1),('SB-10 scored',1))])
    jl(root/'E2B/partB_rows.jsonl',[{'row':m,'col':'class agreement','cluster':f'p{i}','y':rng.random()<.5} for m in ('audit (Qwen backbone)','[R1] (Gemini backbone)') for i in range(15)])
    jl(root/'table_sources/run_integrity_rows.jsonl',[{'row':'E1 judge','col':'valid outputs','value':240}])
    p=root/'SB_anchor_20/analysis.json';p.parent.mkdir(parents=True,exist_ok=True)
    def ag(n,c):return {'rows':n,'clusters':c,'agreement':{'estimate':.9,'lo':.8,'hi':.95},'kappa':{'estimate':.7,'lo':.5,'hi':.9}}
    p.write_text(json.dumps({'judge_author':ag(120,20),'matcher_author':ag(94,17),'lexical_author':ag(120,20),'anchor_overlap_8':ag(24,8),'matcher_coverage':{'pairs':120,'valid':94,'missing':26}}))
@pytest.fixture
def synth(tmp_path):
    root=tmp_path/'batch1';synthetic(root);return root
def test_every_table_has_concern_kind_source_and_no_typed_numbers():
    ids=[s['id'] for s in T.SPECS];assert len(ids)==len(set(ids))==18
    for s in T.SPECS:
        assert s['concerns'] and s['title'] and s['source'] and s['kind'] in set(T.KINDS)|{'count_only','exclusions','reported','sb_anchor'} and s['notes'] is not None
        assert not any(k in s for k in ('estimate','values','cells','numbers'))   # specs hold labels and rules only
def test_pending_tables_show_no_numbers_when_sources_are_missing(tmp_path):
    m=T.build(root=tmp_path/'none',out=tmp_path/'o')
    assert all(t['status'].startswith('pending') and t['cells']==[] for t in m['tables'].values())
    text=(tmp_path/'o'/'batch1_tables.md').read_text();assert 'No numbers are shown' in text and 'to be written from the numbers' in text
def test_tables_on_synthetic_data_have_concern_n_cis_and_markings(synth,tmp_path):
    m=T.build(root=synth,out=tmp_path/'o');text=(tmp_path/'o'/'batch1_tables.md').read_text()
    assert all(t['status']=='ok' for t in m['tables'].values())
    for t in m['tables'].values():
        assert t['concerns'] and t['sources'] and all(len(s['sha256'])==64 for s in t['sources']) and t['config_sha256']
    assert 'Reviewer concern answered' in text and '| Row | Column / metric | n (rows; clusters) | Estimate | CI low | CI high | Markings |' in text
    dep={s['id']:s.get('label_dependent',s['id']!='T13_run_integrity') for s in T.SPECS}
    for tid in m['tables']:
        md=(tmp_path/'o'/(tid+'.md')).read_text()
        if not dep[tid]:assert "authors' labels" not in md
        else:assert "these are the authors' labels" in md and 'UNSEAL_AUTHORISATION.md' in md
    for t in m['tables'].values():
        for c in t['cells']:
            if c['method']!='descriptive' and not c.get('display_note') and c['estimate'] is not None and c['metric'] not in ('kappa','ac1'):assert c['ci_lo'] is not None and c['ci_hi'] is not None and c['ci_lo']<=c['ci_hi']
            assert c['n_rows']>0
    gem=[c for c in m['tables']['T09_E2A_attribution']['cells'] if 'Gemini' in c['row']];assert gem and all('same model as judge' in c['marks'] for c in gem)
    gem12=[c for c in m['tables']['T12_E2B_partB']['cells'] if 'Gemini' in c['row']];assert gem12 and all('same model as judge' in c['marks'] for c in gem12)
    qwen=[c for c in m['tables']['T09_E2A_attribution']['cells'] if 'Gemini' not in c['row']];assert qwen and not any('same model as judge' in c['marks'] for c in qwen)
    cols={c['col'] for c in m['tables']['T09_E2A_attribution']['cells'] if c['row']=='[R1] (Qwen backbone)'};assert {'released code-only (primary)','strict (sensitivity)'}<=cols
    assert not any('MISSING second [R1] scoring' in c['marks'] for c in m['tables']['T09_E2A_attribution']['cells'])
    assert 'No author check of these labels.' in (tmp_path/'o'/'T12_E2B_partB.md').read_text() and 'No author check' not in (tmp_path/'o'/'T09_E2A_attribution.md').read_text()
    assert any(c['display_note']=='no same-volume control available' for c in m['tables']['T06_E4_volume_control']['cells'] if 'SB-' in c['row'])
    t06=(tmp_path/'o'/'T06_E4_volume_control.md').read_text();assert '(3 pairs)' in t06
    mq=[c for c in m['tables']['T06_E4_volume_control']['cells'] if 'MQ' in c['row']];assert mq and all(not c.get('display_note') and c['estimate'] is not None for c in mq)
def test_missing_second_r1_scoring_is_marked(synth,tmp_path):
    p=synth/'E2A/attribution_rows.jsonl';rows=[json.loads(l) for l in p.read_text().splitlines()];rows=[r for r in rows if not (r['row']=='[R1] (Qwen backbone)' and r['col']=='strict (sensitivity)')]
    p.write_text(''.join(json.dumps(r)+'\n' for r in rows));m=T.build(root=synth,out=tmp_path/'o')
    assert any('MISSING second [R1] scoring' in c['marks'] for c in m['tables']['T09_E2A_attribution']['cells'] if c['row']=='[R1] (Qwen backbone)')
def test_exclusion_table_flags_the_silo_bench_anchor_with_the_eight_instance_note(synth,tmp_path):
    m=T.build(root=synth,out=tmp_path/'o');cells={c['row']:c for c in m['tables']['T04_E1_granularity_exclusions']['cells']}
    assert cells['Silo-Bench']['estimate']==1 and cells['Silo-Bench']['n_rows']==8 and abs(cells['Silo-Bench']['pct']-0.125)<1e-9 and cells['Silo-Bench']['marks']
    assert cells['MuSiQue']['marks']==[] and cells['Silo-Bench']['excluded'][0]['task_type']=='BFS' and cells['Silo-Bench']['excluded'][0]['agents']==5
    md=(tmp_path/'o'/'T04_E1_granularity_exclusions.md').read_text();assert 'The Silo-Bench anchor has 8 instances, so one exclusion already exceeds 10%.' in md and '1 of 8, 12.5%' in md
def test_manifest_links_cells_to_sources_config_and_preregistration_hashes_and_is_reproducible(synth,tmp_path):
    a=T.build(root=synth,out=tmp_path/'o1');b=T.build(root=synth,out=tmp_path/'o2')
    for tid in a['tables']:assert a['tables'][tid]['cells']==b['tables'][tid]['cells'] and a['tables'][tid]['config_sha256']==b['tables'][tid]['config_sha256']
    t=a['tables']['T01_E1_anchor_agreement'];assert t['prereg_sha256'].get('E1.md') and a['seed']==42 and a['bootstrap_draws']==2000 and a['unsealed'] is False
    on_disk=json.loads((tmp_path/'o1'/'tables_manifest.json').read_text());assert set(on_disk['tables'])==set(a['tables']) and on_disk['generator_sha256']
def test_agreement_statistics_are_right_on_a_known_case():
    rows=[{'cluster':i,'a':x,'b':y} for i,(x,y) in enumerate([('y','y')]*8+[('n','n')]*8+[('y','n')]*2+[('n','y')]*2)]
    res,ns=T.stat_agreement(rows);assert res['accuracy']['estimate']==pytest.approx(16/20) and res['kappa']['estimate']==pytest.approx(0.6) and ns['n_rows']==20
    assert res['accuracy']['ci_lo']<0.8<res['accuracy']['ci_hi']
    lo,hi=T.cp_ci(8,13);assert (round(lo,3),round(hi,3))==(0.316,0.861)
# ---- the sealed-folder guard
def test_the_generator_refuses_to_read_a_sealed_folder_until_unsealed_and_authorised(tmp_path):
    sealed=tmp_path/'E1_judge_sealed'/'x.jsonl';jl(sealed,[{'row':'r','col':'c','value':1}])
    with pytest.raises(T.SealedAccessError):T.read_rows(sealed)                                  # no flag
    with pytest.raises(T.SealedAccessError):T.read_rows(sealed,unseal=True,auth=tmp_path/'none.md')   # flag but no authorisation record
    auth=tmp_path/'UNSEAL_AUTHORISATION.md';auth.write_text(VALID_AUTH)
    assert T.read_rows(sealed,unseal=True,auth=auth)==[{'row':'r','col':'c','value':1}]            # both present
    with pytest.raises(T.SealedAccessError):T.read_rows(tmp_path/'SEALED'/'y.jsonl')               # case-insensitive
    other=tmp_path/'E2_judge_sealed'/'y.jsonl';jl(other,[{'row':'r','col':'c','value':1}])
    with pytest.raises(T.SealedAccessError):T.read_rows(other,unseal=True,auth=auth)               # E1 outputs only
def test_build_refuses_a_spec_whose_source_is_sealed_without_the_flag(tmp_path):
    root=tmp_path/'batch1';jl(root/'E1_judge_sealed'/'rows.jsonl',[{'row':'r','col':'c','value':1}])
    spec={'id':'TX','title':'t','kind':'count_only','source':'E1_judge_sealed/rows.jsonl','prereg':[],'concerns':['x'],'marks':[],'notes':[]}
    with pytest.raises(T.SealedAccessError):T.build(root=root,out=tmp_path/'o',specs=[spec])
    auth=root/'UNSEAL_AUTHORISATION.md';auth.write_text(VALID_AUTH);m=T.build(root=root,out=tmp_path/'o2',unseal=True,auth=auth,specs=[spec]);assert m['unsealed'] is True and m['tables']['TX']['cells']
def test_the_real_sealed_folder_is_untouched_by_a_default_run(tmp_path):
    before={p:p.stat().st_mtime_ns for p in Path('rebuttal/results/batch1/E1_judge_sealed').rglob('*') if p.is_file()}
    T.build(root=Path('rebuttal/results/batch1'),out=tmp_path/'o')   # real root, no unseal flag: must not raise, must not open sealed files
    assert before=={p:p.stat().st_mtime_ns for p in Path('rebuttal/results/batch1/E1_judge_sealed').rglob('*') if p.is_file()}
    assert 'sealed' not in ' '.join(s['source'] for s in T.SPECS).lower()   # no real spec points into a sealed folder


def test_authorisation_record_must_carry_the_leads_confirmation_a_date_and_both_manifest_hashes(tmp_path):
    sealed=tmp_path/'E1_judge_sealed'/'x.jsonl';jl(sealed,[{'row':'r','col':'c','value':1}]);auth=tmp_path/'A.md'
    good=VALID_AUTH
    for bad,why in [(good.replace('Lead confirmation:','Note:'),'no lead line'),(good.replace('Date: 2026-12-01','Date: soon'),'no date'),
                    (good.replace(T.UNLOCKS['MANIFEST.sha256'],'0'*64),'first manifest hash missing'),(good.replace(T.UNLOCKS['MANIFEST_retry.sha256'],'1'*64),'retry manifest hash missing')]:
        auth.write_text(bad)
        with pytest.raises(T.SealedAccessError):T.read_rows(sealed,unseal=True,auth=auth)
    auth.write_text(good);assert T.read_rows(sealed,unseal=True,auth=auth)
def test_the_generator_never_creates_the_authorisation_record():
    src=Path('scripts/make_batch1_tables.py').read_text()
    assert 'UNSEAL_AUTHORISATION' in src and not re.search(r'UNSEAL_AUTHORISATION[^\n]*write',src)
def test_the_real_unlocked_hashes_are_the_two_recorded_manifest_hashes():
    assert T.UNLOCKS['MANIFEST.sha256'].startswith('eb8e4428') and T.UNLOCKS['MANIFEST_retry.sha256'].startswith('bacbfb22') and all(len(h)==64 for h in T.UNLOCKS.values())
