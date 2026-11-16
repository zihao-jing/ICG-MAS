"""Progress of a sealed run from COUNTS-ONLY sources: the run log lines ("i/N status") or the counts log (running totals). Never opens a ledger or a sealed folder.
Usage: python -m scripts.status_counts_only <run.log | counts.jsonl>"""
import json,re,sys
from pathlib import Path
def status(path):
    p=Path(path);text=p.read_text();n=ok=bad=fail=0;last=None;cost=None
    if p.suffix=='.jsonl':
        rows=[json.loads(l) for l in text.splitlines() if l.strip()]
        if not rows:return {'done':0}
        calls=[r for r in rows if r.get('event','call')=='call']
        if not calls:return {'done':0}
        r=calls[-1];return {'done':r['n'],'of':r['of'],**r['running']}
    for l in text.splitlines():
        m=re.match(r'^(\d+)/(\d+) (valid|format_invalid|failed)(?: \S+)?$',l.strip())
        if m:
            n=int(m.group(1));last=int(m.group(2));ok+=m.group(3)=='valid';bad+=m.group(3)=='format_invalid';fail+=m.group(3)=='failed'
        elif l.startswith('{') and 'sealed_manifest_sha256' in l:
            s=json.loads(l);cost=s.get('cost_usd')
    return {'done':n,'of':last,'valid':ok,'format_invalid':bad,'failed':fail,'cost_usd':cost if cost is not None else 'pending end of run'}
if __name__=='__main__':print(json.dumps(status(sys.argv[1])))
