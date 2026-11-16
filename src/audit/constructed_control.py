"""Constructed same-volume control, E4 amendment A2 (Silo-Bench). Deterministic; no model writes any control text.

The control text is whole segments of the donor agent's own shard, chosen in ascending SHA-256 order of
["E4-construct-v1", 42, case_id, arm, segment_index] until the unit count equals the repair's added unit count and the
exact base-tokenizer count is within +-10% of the repair's added tokens. One segment = one unit, as written in A2.
"""
import ast,re
from src.audit.pilot_common import digest
SALT='E4-construct-v1';TOL=0.10;MAX_REDRAWS=2

def split_segments(shard_text):
    """Whole segments, never cut: data-list records, dict items, lines, or sentences (in that order of preference)."""
    if isinstance(shard_text,(list,tuple,dict)):obj=shard_text;s=str(shard_text)
    else:
        s=str(shard_text).strip()
        try:obj=ast.literal_eval(s)
        except Exception:obj=None
    if isinstance(obj,(list,tuple)) and obj:return [str(x) for x in obj]
    if isinstance(obj,dict) and obj:return [f'{k}: {v}' for k,v in obj.items()]
    lines=[l.strip() for l in s.splitlines() if l.strip()]
    if len(lines)>1:return lines
    return [x.strip() for x in re.split(r'(?<=[.!?])\s+',s) if x.strip()]

def sha_order(n,case_id,arm):
    return sorted(range(n),key=lambda i:(digest([SALT,42,case_id,arm,i]),i))

def select_segments(segments,case_id,arm,units,tokens,count_tokens,excluded=(),tol=TOL,forbidden=()):
    """Return the chosen segments (list of str, in selection order) or None if no selection satisfies A2."""
    if units==0:return []
    toks=[count_tokens(s) for s in segments];lo,hi=(1-tol)*tokens,(1+tol)*tokens
    bad=set(excluded)|set(forbidden)  # forbidden = segments that carry a needed fact (support-set carriers)
    idx=[i for i in sha_order(len(segments),case_id,arm) if segments[i] not in bad]
    chosen=[];total=0
    for pos,i in enumerate(idx):
        r=units-len(chosen)
        if r==0:break
        t=toks[i];later=sorted(toks[j] for j in idx[pos+1:])
        if r==1:
            if lo<=total+t<=hi:chosen.append(i);total+=t
            continue
        if len(later)<r-1:continue
        if total+t+sum(later[:r-1])<=hi and total+t+sum(later[-(r-1):])>=lo:chosen.append(i);total+=t
    return [segments[i] for i in chosen] if len(chosen)==units and lo<=total<=hi else None

def qwen_check_messages(added_text,needed_fact,source_shard):
    system='You check text for a controlled experiment. Answer with exactly one line: PASS or FAIL, then a short reason.'
    user=(f'SOURCE SHARD (the added text must be copied from it):\n{source_shard}\n\nADDED TEXT:\n{added_text}\n\n'
          f'NEEDED FACT (belongs to a different agent):\n{needed_fact}\n\n'
          'FAIL if the added text states, implies, restores or lets one derive the needed fact, or if any of it is not in the source shard. Otherwise PASS.')
    return [{'role':'system','content':system},{'role':'user','content':user}]

def parse_check(text):
    first=(text or '').strip().splitlines()[0].upper() if (text or '').strip() else ''
    return True if first.startswith('PASS') else False if first.startswith('FAIL') else None

def build_control(shard_text,needed_fact,case_id,arm,units,tokens,count_tokens,check,max_redraws=MAX_REDRAWS,forbidden=()):
    """Selection + Qwen check with redraws. `check(added_text)->True|False|None` (None = unparseable = fail). Returns a record."""
    segs=split_segments(shard_text);excluded=[];attempts=[]
    for attempt in range(max_redraws+1):
        sel=select_segments(segs,case_id,arm,units,tokens,count_tokens,excluded,forbidden=forbidden)
        if sel is None:
            attempts.append({'attempt':attempt,'selection':None,'reason':'no selection satisfies unit count and ±10% tokens'});break
        text='\n'.join(sel);ok=check(text)
        attempts.append({'attempt':attempt,'selection':sel,'tokens':sum(count_tokens(s) for s in sel),'qwen_pass':ok})
        if ok:return {'built':True,'segments':sel,'attempts':attempts,'redraws':attempt}
        excluded+=sel
    return {'built':False,'segments':None,'attempts':attempts,'redraws':len(attempts)-1,'label':'no same-volume control available'}

def report_rows(rows):
    """Built and natural controls are always summarised in separate groups; there is no pooled entry by design."""
    out={}
    for kind in ('natural','constructed'):
        d=[r['delta'] for r in rows if r['control_kind']==kind]
        out[kind]={'n':len(d),'mean_delta':(sum(d)/len(d)) if d else None}
    unknown={r['control_kind'] for r in rows}-set(out)
    if unknown:raise ValueError(f'unknown control kind(s): {sorted(unknown)}')
    return out
