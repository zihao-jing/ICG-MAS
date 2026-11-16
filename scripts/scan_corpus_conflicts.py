"""Zero-call scan: same-subject, different-value sentence pairs in the Stage 2
source documents. Sizes option C for the constructed distortion cases.

    ./run.sh python -m scripts.scan_corpus_conflicts
"""
import hashlib
import itertools
import json
import re
from collections import defaultdict
from pathlib import Path

from src.eval.evaluate import normalize

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261112_constructed_distortion/conflict_scan.json'
CASE_CAP = 400

NUM = re.compile(r'\d[\d,.]*(?:\s*(?:million|billion|thousand|m|km|kg|ft|feet|%))?', re.I)
STOP = set('''the a an this that these those his her its their in on at of for with by from as to and or but not no
was were is are be been being had has have do does did which who whom whose what when where why how'''.split())


def sentences(text):
    out = []
    for part in re.split(r'(?<=[.!?])\s+|\n+', text):
        s = ' '.join(part.split())
        if 40 <= len(s) <= 400:
            out.append(s)
    return out


def raw_tokens(s):
    return re.findall(r"[A-Za-z][A-Za-z'’.-]*|\d[\d,.]*", s)


DEMONYMS = set('''african american white asian hispanic latino native american pacific islander
united states english american european african europe british french german italian spanish
chinese japanese indian russian catholic protestant christian jewish muslim'''.split())
LEAD = {'the', 'a', 'an', 'in', 'on', 'at', 'after', 'before', 'during', 'by', 'from',
        'his', 'her', 'its', 'their', 'this', 'that', 'these', 'those', 'as', 'when'}


def load_words():
    p = Path('/usr/share/dict/words')
    if not p.exists():
        return set()
    return {w.strip().lower() for w in p.read_text(errors='ignore').splitlines() if w.strip()}


WORDS = load_words()
PRONOUN = {'he', 'she', 'it', 'they', 'we', 'you', 'i', 'there', 'this', 'that', 'these',
           'those', 'who', 'what', 'which', 'one', 'two', 'three', 'nine', 'may', 'back',
           'according', 'with', 'population', 'document', 'national', 'men', 'women'}


def subject(s):
    """A proper name at the start of the sentence (optionally after one lead
    word), with at least one token that is not an ordinary English word. This
    rejects template sentences ("There were ...", "According to ...") whose
    subject is anaphoric and differs from sentence to sentence."""
    toks = raw_tokens(s)
    start = 1 if toks and toks[0].lower() in LEAD else 0
    run = []
    for t in toks[start:start + 8]:
        if t[:1].isupper() and t.lower() not in LEAD:
            run.append(t)
        else:
            break
    if not run:
        return ''
    sub = ' '.join(run)
    parts = sub.split()
    if sub.lower() in DEMONYMS or len(parts) > 6:
        return ''
    if parts[0].lower() in PRONOUN:
        return ''
    if WORDS and not any(p.lower() not in WORDS for p in parts):
        return ''
    return sub


def values(s):
    return {' '.join(normalize(m.group(0).strip())) for m in NUM.finditer(s)}


def content_tokens(s):
    return {t for t in ' '.join(normalize(s)).split() if t not in STOP and not t.isdigit()}


def scan():
    from scripts.run_expansion_stage2 import packages
    pk = packages('gemma31b')
    docs, seen = [], set()
    for inst, p in pk.items():
        for c in p['source_contexts']:
            h = hashlib.sha256(c['text'].encode()).hexdigest()
            if h in seen:
                continue
            seen.add(h)
            docs.append((inst, c['agent_id'], c['text']))
    try:
        from scripts.run_expansion_stage1 import packages as packages1
        for inst, p in packages1('gemma31b').items():
            for c in p['source_contexts']:
                h = hashlib.sha256(c['text'].encode()).hexdigest()
                if h in seen:
                    continue
                seen.add(h)
                docs.append((inst, c['agent_id'], c['text']))
    except Exception as exc:  # stage 1 run may be absent on a fresh checkout
        print(json.dumps({'stage1_skipped': str(exc)[:120]}))
    groups = defaultdict(list)
    nsent = 0
    for inst, agent, text in docs:
        for s in sentences(text):
            nsent += 1
            sub = subject(s)
            vals = values(s)
            if not sub or not vals:
                continue
            groups[sub.lower()].append({'s': s, 'v': vals, 'c': content_tokens(s),
                                        'instance': inst, 'agent': agent})
    pairs = []
    for sub, rows in groups.items():
        if len(rows) < 2:
            continue
        for a, b in itertools.combinations(rows, 2):
            if a['v'] == b['v']:
                continue
            ca = a['c'] - set(sub.split())
            cb = b['c'] - set(sub.split())
            if not ca or not cb:
                continue
            j = len(ca & cb) / len(ca | cb)
            if j >= 0.5:
                pairs.append({'subject': sub, 'jaccard': round(j, 3),
                              'a': {k: a[k] for k in ('s', 'instance', 'agent')},
                              'b': {k: b[k] for k in ('s', 'instance', 'agent')},
                              'values_a': sorted(a['v']), 'values_b': sorted(b['v'])})
    pairs.sort(key=lambda p: -p['jaccard'])
    same = [p for p in pairs if p['a']['instance'] == p['b']['instance']]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({'documents': len(docs), 'sentences': nsent,
                               'subjects': len(groups), 'conflict_pairs': len(pairs),
                               'same_instance_pairs': len(same),
                               'same_instance_instances': len({p['a']['instance'] for p in same}),
                               'same_instance_subjects': len({p['subject'] for p in same}),
                               'top': pairs[:CASE_CAP]}, indent=1))
    print(json.dumps({'documents': len(docs), 'sentences': nsent,
                      'subjects_with_values': len(groups),
                      'conflict_pairs': len(pairs),
                      'distinct_subjects': len({p['subject'] for p in pairs}),
                      'same_instance_pairs': len(same),
                      'same_instance_instances': len({p['a']['instance'] for p in same}),
                      'same_instance_subjects': len({p['subject'] for p in same}),
                      'out': str(OUT.relative_to(ROOT))}, indent=1))


if __name__ == '__main__':
    scan()