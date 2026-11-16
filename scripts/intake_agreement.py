"""Human-human agreement from the returned label files only. No judge, matcher or baseline output is read.
Per fact at the board checkpoint: presence is "present" when the board fidelity is not "absent"; fidelity is the
board fidelity. Rows whose binary_call is exclude_partial or exclude_uncertain are dropped from primary agreement
(E1-v9). Anchor rows carry the stratum weight from the locked anchor manifest and cluster by instance; dev and
calibration are unweighted and cluster by item. Prints the numbers used in the intake report.
Usage: python -m scripts.intake_agreement"""
import glob,json
from collections import defaultdict
from scripts.make_batch1_tables import stat_agreement
RET='rebuttal/annotation/returns';TAG='labelling-v1.0'
MANIFEST='rebuttal/pilots/20261108_review7/e1_anchor_locked_manifest.json'
PRIVATE='rebuttal/pilots/20261108_review8/packet_private_map.json'
FID=['absent','faithful','partial','distorted'];PRES=['absent','present']
def task_rows(task):
    out={}
    for f in sorted(glob.glob(f'{RET}/{task}_*_{TAG}.json')):
        a=f.split('/')[-1].split('_')[1];out[a]={r['item_id']:r for r in json.load(open(f))}
    return out
def fact_labels(r):
    facts=[x['fact_id'] for x in json.loads(r['answers']['critical_facts_json'])]
    board={c['fact_id']:c['fidelity'] for c in json.loads(r['answers']['carriers_json']) if c['checkpoint']=='board'}
    return {fid:board.get(fid,'absent') for fid in facts}
def pairs(task,ids):
    rs=task_rows(task);out=[]
    for x,y in ids:
        for item in sorted(set(rs.get(x,{}))&set(rs.get(y,{}))):out.append((x,y,item,rs[x][item],rs[y][item]))
    return out
def agreement(task,idpairs,anchor=False):
    priv=json.load(open(PRIVATE)) if anchor else {}
    man=json.load(open(MANIFEST));w={i:st['weight'] for st in man['strata'].values() for i in st['ids']}
    pres=[];fid=[];dropped=0;pairinfo=defaultdict(lambda:{'n_items':0,'diffs':0})
    for x,y,item,ra,rb in pairs(task,idpairs):
        info=pairinfo[(x,y)];info['n_items']+=1
        la,lb=fact_labels(ra),fact_labels(rb)
        if la!=lb or ra['answers']['binary_call']!=rb['answers']['binary_call']:info['diffs']+=1
        if ra['answers']['binary_call'] in ('exclude_partial','exclude_uncertain') or rb['answers']['binary_call'] in ('exclude_partial','exclude_uncertain'):
            dropped+=1;continue
        inst=priv.get(item,{}).get('instance_id',item);weight=w.get(inst,1.0) if anchor else 1.0
        cluster=inst if anchor else item
        for k in sorted(set(la)&set(lb)):
            fa,fb=la[k],lb[k]
            if 'uncertain' in (fa,fb):continue
            pres.append({'a':'present' if fa!='absent' else 'absent','b':'present' if fb!='absent' else 'absent','weight':weight,'stratum':'','cluster':cluster})
            fid.append({'a':fa,'b':fb,'weight':weight,'stratum':'','cluster':cluster})
    return {'presence':stat_agreement(pres,PRES),'fidelity':stat_agreement(fid,FID),'pairs':{'+'.join(k):v for k,v in pairinfo.items()},'dropped_items':dropped,'n_fact_rows':{'presence':len(pres),'fidelity':len(fid)}}
def main():
    res={'anchor':agreement('E1anchor',[('A','B'),('C','D')],anchor=True),
         'dev':agreement('E1dev',[('A','B'),('C','D')]),
         'calibration':agreement('E1calibration',[('A','B'),('A','C'),('A','D'),('B','C'),('B','D'),('C','D')])}
    print(json.dumps(res,indent=1))
if __name__=='__main__':main()