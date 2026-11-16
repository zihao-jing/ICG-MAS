"""Intake check for the authors' returned files: accepted / expected files and complete rows, per author and task. Prints counts only.
Reads only the files in RETURNS and the blank label sheets (item ids and assignments); never any judge output.
File name: <task>_<authorID>_<versiontag>.json (content: a JSON array of rows, or one JSON row per line). The tag must equal the folder's VERSION; there is no dry-run special case."""
import json,re
from pathlib import Path
RETURNS=Path('rebuttal/annotation/returns');DATA=Path('rebuttal/annotation/labelling_20261108/data');VERSION_FILE=Path('rebuttal/annotation/labelling_20261108/VERSION')
TASKS={'E1calibration':'T0_calibration_E1','E1dev':'T1_E1_dev','E1anchor':'T2_E1_anchor','E2spotcheck1':'T3_E2_spotcheck_wave1'};OPTIONAL={'uncertain_reason'}
NAME=re.compile(r'^(E1calibration|E1dev|E1anchor|E2spotcheck1)_([ABCD])_(.+)\.json$')
def _sheet(p):return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]
def load_rows(p):
    text=Path(p).read_text().strip()
    if text.startswith('['):return json.loads(text)
    return [json.loads(l) for l in text.splitlines() if l.strip()]
def current_version(version_file=VERSION_FILE):return Path(version_file).read_text().strip()
def intake(returns=RETURNS,data=DATA,version=None,override=None):
    """override: an optional folder whose files replace same-named files in `returns` (a corrected re-export)."""
    version=version or current_version();out={};files_exp=files_got=0;ret=Path(returns)
    expected={s:_sheet(Path(data)/(s+'.jsonl')) for s in TASKS.values()}
    files={f.name:f for f in ret.glob('*.json')} if ret.exists() else {}
    if override:
        for f in Path(override).glob('*.json'):files[f.name]=f
    present={}
    for f in sorted(files.values(),key=lambda p:p.name):
        m=NAME.match(f.name)
        if m:present.setdefault((m.group(1),m.group(2)),[]).append((m.group(3),f))
    for a in 'ABCD':
        out[a]={}
        for short,sheet in TASKS.items():
            exp_ids={r['item_id'] for r in expected[sheet] if r['assigned_annotator']==a};files_exp+=1
            rec={'received':False,'rows':0,'expected':len(exp_ids),'complete':0,'unexpected_rows':0,'other_version_files':0}
            for tag,f in present.get((short,a),[]):
                if tag!=version:rec['other_version_files']+=1;continue
                try:rows=load_rows(f)
                except Exception:rec['received']='unreadable';continue
                rec['received']=True;rec['rows']=len(rows);rec['complete']=rec['unexpected_rows']=0
                for r in rows:
                    if r.get('item_id') not in exp_ids or r.get('assigned_annotator')!=a:rec['unexpected_rows']+=1;continue
                    if r.get('annotator_id') and all(str(v).strip() for k,v in r.get('answers',{}).items() if k not in OPTIONAL):rec['complete']+=1
            if rec['received'] is True:files_got+=1
            out[a][short]=rec
    return {'version':version,'authors':out,'files_received':files_got,'files_expected':files_exp}
if __name__=='__main__':print(json.dumps(intake()))
