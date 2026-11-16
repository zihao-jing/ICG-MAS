"""Export approved E1 cached k=3 traces, without diagnostic hints."""
import json
from pathlib import Path
from src.audit.critical_fact_validation import build_trace_packages
from src.audit.pilot_common import blind_view,digest

RUNS={'qwen235b':('run_qwen235b_n5','run_qwen235b_n10','run_qwen235b_musique'),
'gpt4omini':('run_gpt4omini_n5','run_gpt4omini_n10','run_musique_gpt4omini'),
'gemma31b':('run_gemma31b_n5','run_gemma31b_n10','run_musique_gemma31b')}

def main():
    m=json.loads(Path('rebuttal/pilots/20261108_preflight/id_manifest.json').read_text())
    schema=json.loads(Path('rebuttal/annotation/E1/label_schema.json').read_text())['labels'];rows=[]
    for model,runs in RUNS.items():
        ids=set(m['e1_held_out'])|(set(m['e1_dev']) if model=='qwen235b' else set())
        for index,run in enumerate(runs):
            dataset='musique' if index==2 else 'silobench'
            packages=build_trace_packages(dataset=dataset,run_dir=Path('results')/run,protocol='score_ranked_relay',source_id=run,n_agents=None if index==2 else (5 if index==0 else 10))
            for p in packages:
                if p['instance_id'] not in ids:continue
                p['answer_text']=p['baseline_prediction'];v=blind_view(p)
                row={'task':'E1','split':'dev' if p['instance_id'] in m['e1_dev'] else 'held_out','source_id':run,'k':3,'trace_hash':digest(v),'trace':v,'labels':schema,'annotator_id':''}
                rank=sorted(m['e1_dev']+m['e1_held_out']).index(p['instance_id'])
                row['assigned_pair']=['A','B'] if rank%2==0 else ['C','D']
                row['part_b_pair']=['C','D'] if rank%2==0 else ['A','B']
                rows.append(row)
    dest=Path('rebuttal/annotation/E1/evaluation_sheet.jsonl')
    content=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows)
    if dest.exists() and dest.read_text()!=content:
        old=[json.loads(x) for x in dest.read_text().splitlines()]
        if any(r.get('annotator_id') or r['labels']!=schema for r in old):raise FileExistsError('Refusing to overwrite entered labels')
    dest.write_text(content)
    print(json.dumps({'traces':len(rows),'dev':sum(r['split']=='dev' for r in rows),'held_out':sum(r['split']=='held_out' for r in rows)}))
if __name__=='__main__':main()
