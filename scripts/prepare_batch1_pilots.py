"""Deterministic offline manifest preparation. Never dispatches an API call."""
import json
from pathlib import Path
from src.audit.pilot_common import MODELS,STRONG,digest,ranked,freeze
from src.eval.data_loader import load_musique

ROOT=Path('rebuttal/pilots')
def main():
    mq=json.loads(Path('results/run_qwen235b_musique/results.json').read_text())['instance_results']['score_ranked_relay']
    sb=[]
    for n in (5,10):
        sb+=json.loads(Path(f'results/run_qwen235b_n{n}/results.json').read_text())['instance_results']['score_ranked_relay']
    audits={}
    for name in ('run_qwen235b_musique','run_qwen235b_n5','run_qwen235b_n10'):
        for r in json.loads(Path(f'results/{name}/audit_metrics.json').read_text())['audit_records']['score_ranked_relay']:
            audits[r['inst_id']]=r['crit_recall']
    def stratify(rows,n):
        groups={}
        for r in rows:groups.setdefault((r['f1']>=1,audits[r['id']]>=1),[]).append(r['id'])
        groups={str(k):ranked(v) for k,v in sorted(groups.items())};out=[]
        while len(out)<n:
            for k in groups:
                if groups[k] and len(out)<n:out.append(groups[k].pop(0))
        return out
    sbids=stratify(sb,20);mqids=stratify(mq,60)
    dev=ranked(sbids)[:5]+ranked(mqids)[:15];held=sorted(set(sbids+mqids)-set(dev))
    allfinal=sorted({r['id'] for r in mq+sb})
    outside=ranked([x['id'] for x in load_musique() if x['id'] not in allfinal])
    pools={'selection':'SHA256 canonical JSON [42, instance_id]; historical Qwen correctness × lexical CR strata, round-robin sorted strata for E1; no new outcomes',
        'e1_dev':dev,'e1_held_out':held,'full_evaluation_ids':allfinal,'pilot_ids':outside[:5],'calibration_ids':outside[5:10]}
    freeze(ROOT/'20261108_preflight/id_manifest.json',pools)
    common={'seed':42,'base_models':list(MODELS),'judge_model':MODELS[0],'strong_model':STRONG,
        'pricing':str(ROOT/'20261108_preflight/pricing.json'),'id_manifest':str(ROOT/'20261108_preflight/id_manifest.json'),
        'pilot_ids':pools['pilot_ids'],'calibration_ids':pools['calibration_ids'],'sample_size':5,'k':1,'max_units':3,
        'temperature':0,'max_tokens':4096,'allow_full_run':False}
    for exp in ('E1','E4','E4-P','E2-C','E2-A'):
        c=dict(common,experiment=exp,output=str(ROOT/('20261108_'+exp.lower().replace('-','_'))),prereg=str(ROOT/'prereg'/f'{exp}.md'))
        if exp=='E1':c.update(lexical_thresholds=[0,.1,.2,.3,.5],bootstrap_draws=2000,acceptance={'human_kappa_lower_ci':.6,'adjudicated_accuracy_lower_ci':.8},source_trace_models=list(MODELS))
        if exp in ('E4','E4-P'):
            c.update(labels='rebuttal/annotation/frozen_matcher_labels.jsonl',action_manifest=str(ROOT/('20261108_'+exp.lower().replace('-','_'))/'actions.json'),
                manifest_sha256=None,matcher_frozen=False)
        if exp=='E4-P':c.update(conditions=['G-ext@t','G-ext@hash','G-sel@t','R-agg+'],sample={'mode':'reserved_pilot','ids':pools['pilot_ids'],'limit':5},enlargement={'enabled':False,'benchmark':'silobench','n_agents':10,'k':1,'additional_seeds':[43],'tasks':'all 26','selection':'all cases, cluster by task across seeds'})
        if exp=='E2-C':c.update(author_labels='rebuttal/annotation/e1_adjudicated.jsonl',casebook_counts={'extraction':4,'selection':4,'aggregation_musique':2,'aggregation_silobench':2},trace_ids=None)
        if exp=='E2-A':c.update(author_screening='rebuttal/annotation/e2a_screening_completed.jsonl',post_checks='rebuttal/annotation/e2a_post_completed.jsonl',max_kept_per_type_model=10,injection_types=['extraction_omission','selection_omission','distortion','aggregation'],taxonomy_revision='0bd196c',taxonomy_modes=17)
        freeze(ROOT/'configs'/f'{exp}.json',c)
    print(json.dumps({'dev':len(dev),'held_out':len(held),'pilot':pools['pilot_ids'],'calibration':pools['calibration_ids']},indent=2))
if __name__=='__main__':main()
