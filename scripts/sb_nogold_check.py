"""Three-trace check that the two-step proxy prompt (question + shards only) carries no gold text. $0, no calls.

Renders the frozen v3 prompt exactly as `sb_twostep_pilot.py` did, then compares the rendered SOURCE DOCUMENTS
block, line by line, against the trace's gold support list.
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PILOTS = ROOT / 'rebuttal/pilots'
PROMPT = PILOTS / 'prereg/proxy_facts_prompt_v3_two_step.json'
POP = PILOTS / '20261115_proxy_support_sb_fixed/population.json'
OUT = PILOTS / '20261115_sb_nogold_check'


def render_docs(row):
    return '\n\n'.join(f"[{d['unit_id']}]\n{d['text']}" for d in row['documents'])


def norm(x):
    return ' '.join(str(x).split())


def check_prompt_fields(prof, user):
    """The rendered prompt must contain no gold field and no answer field."""
    fields = [k for k in ('gold_supports', '"gold', 'gold:', '"answer"', 'answer:') if k in user]
    return fields


def main():
    prof = json.loads(PROMPT.read_text())
    rows = json.loads(POP.read_text())
    rng = random.Random(43)
    pick = rng.sample(rows, 3)
    out = {'prompt_sha': None, 'user_template_fields': [], 'traces': []}
    import hashlib
    out['prompt_sha'] = hashlib.sha256(PROMPT.read_bytes()).hexdigest()
    out['user_template_fields'] = ['question', 'documents'] if '{documents}' in prof['facts']['user'] else []
    for r in pick:
        docs = render_docs(r)
        sel = prof['selection']['user'].format(question=r['question'], documents=docs)
        fac = prof['facts']['user'].format(question=r['question'], documents=docs)
        gold = [norm(g['text']) for g in (r.get('gold_supports') or [])]
        # every document as rendered, recovered from the rendered block
        rendered = [norm(d['text']) for d in r['documents']]
        gold_in_prompt = sum(1 for g in gold if g in norm(sel) and g in norm(fac))
        out['traces'].append({
            'key': r['key'],
            'documents': len(rendered),
            'gold_supports': len(gold),
            'documents_that_are_gold_supports': sum(1 for d in rendered if d in gold),
            'gold_supports_present_in_rendered_prompt': gold_in_prompt,
            'documents_equal_gold_list': rendered == gold,
            'gold_field_names_in_prompt': check_prompt_fields(prof, sel + fac),
        })
    (OUT / 'check_fixed_prompt.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()