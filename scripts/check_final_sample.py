"""Compare the FINAL sets of IDs with the pre-registered lists: exact match, missing, extra and duplicate IDs.
  E1: 80 held-out IDs (E1-v9; lock manifest) x 3 models = 240 traces. Final IDs come ONLY from the file names listed in the two sealed-folder manifests
      (MANIFEST.sha256, MANIFEST_retry.sha256); no sealed file content is read.
  E4-P seed-43: 26 tasks x 3 models = 78 traces; final IDs from the unsealed traces/ file names.
Writes rebuttal/results/batch1/sample_check.json and the one-line SAMPLE_CHECK.md."""
import json,re
from collections import Counter
from pathlib import Path
from src.audit.pilot_common import digest
B=Path('rebuttal/results/batch1');MODELS=('qwen235b','gpt4omini','gemma31b');E4P_MODELS={'qwen':'qwen/qwen3-235b-a22b-2507','gpt':'openai/gpt-4o-mini','gemma':'google/gemma-4-31b-it'}
def compare(expected,final_list):
    c=Counter(final_list);final=set(c);return {'expected':len(expected),'final_ids':len(final_list),'exact_match':final==set(expected) and not [k for k,v in c.items() if v>1],'missing':sorted(set(expected)-final),'extra':sorted(final-set(expected)),'duplicate':sorted(k for k,v in c.items() if v>1)}
def manifest_keys(path):
    p=Path(path);assert p.name.startswith('MANIFEST') and p.name.endswith('.sha256'),'only manifest files may be read from a sealed folder'
    return [m.group(1) for l in p.read_text().splitlines() for m in [re.search(r'  outputs/([0-9a-f]{64})\.json$',l)] if m]
def e1(root=B,ids=None,lock_path=Path('rebuttal/pilots/20261108_review6/e1_n80_locked_manifest.json'),v9=Path('rebuttal/pilots/prereg/E1-v9.md')):
    lock=json.loads(lock_path.read_text());ids=ids or [i for v in lock['strata'].values() for i in v['ids']]
    expected=[digest(['E1-judge',42,i,m]) for i in ids for m in MODELS]
    final=manifest_keys(Path(root)/'E1_judge_sealed'/'MANIFEST.sha256')+manifest_keys(Path(root)/'E1_judge_sealed'/'MANIFEST_retry.sha256')
    r=compare(expected,final);r['ids_80']=len(set(ids))==80;r['id_list_hash_in_E1_v9']=lock['id_list_sha256'] in v9.read_text();r['instances']=len(ids);return r
def e4p(root=B):
    E=Path(root)/'E4P_seed43';tasks=sorted(f.name.replace('.json','') for f in (E/'data').glob('*.json'))   # instance ids keep their _n10 suffix
    expected=[digest([t+'::seed43',mid]) for t in tasks for mid in E4P_MODELS.values()]
    final=[f.stem for m in E4P_MODELS for f in sorted((E/m/'traces').glob('*.json'))]
    r=compare(expected,final);r['tasks']=len(tasks);return r
def line(a,b):
    f=lambda n,r:f"{n}: {'exact match' if r['exact_match'] else 'MISMATCH'} ({r['final_ids']}/{r['expected']}, {len(r['missing'])} missing, {len(r['extra'])} extra, {len(r['duplicate'])} duplicate)"
    return f('E1 judge outputs',a)+'; '+f('E4-P seed-43 traces',b)
def main(root=B):
    a,b=e1(root),e4p(root);Path(root,'sample_check.json').write_text(json.dumps({'e1':a,'e4p':b},indent=1));l=line(a,b);Path(root,'SAMPLE_CHECK.md').write_text(l+'\n');print(l)
if __name__=='__main__':main()
