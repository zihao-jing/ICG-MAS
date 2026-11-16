"""Strict released-taxonomy parsing; official prompt text is never reimplemented here."""
import re

def parse_attribution(text,steps,taxonomy):
    fields={}
    for key in ('Agent Name','Step Number','Error Mode'):
        m=re.search(r'^\s*(?:\*\*)?'+re.escape(key)+r'(?:\*\*)?\s*:\s*(.*?)\s*$',text,re.M)
        fields[key]=m.group(1).strip() if m else None
    step=fields['Step Number'];code=None;name=None
    if fields['Error Mode']:
        m=re.fullmatch(r'([A-Z]+\.\d+)(?:\s*[:\-–]\s*(.+))?',fields['Error Mode'].strip().strip('*'))
        if m:code,name=m.groups()
    valid_mode=code in taxonomy
    if valid_mode and name is not None:
        norm=lambda s:re.sub(r'\s+',' ',s.strip().strip('*')).casefold()
        valid_mode=norm(name)==norm(taxonomy[code]['name'])
    by_step={str(r['step']):r for r in steps}
    valid_step=step in by_step
    agents={r['agent'] for r in steps}
    valid_agent=fields['Agent Name'] in agents
    return {'agent':fields['Agent Name'],'step':step,'code':code,'family':code.split('.')[0] if valid_mode else None,
        'agent_valid':valid_agent,'step_valid':valid_step,'mode_valid':valid_mode,
        'stage':by_step[step]['stage'] if valid_step else None,
        'parse_ok':all(v is not None for v in fields.values()),'invalid_type':not valid_mode}

def score_attribution(pred,reference):
    return {'agent':int(pred['agent_valid'] and pred['agent']==reference['agent']),
        'stage':int(pred['step_valid'] and pred['stage']==reference['stage']),
        'family':int(pred['mode_valid'] and pred['family']==reference['family']),
        'mode':int(pred['mode_valid'] and pred['code']==reference['mode'])}
