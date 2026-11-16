"""Frozen v2 of the R2 delivery gate: content-token recall.

Version v2a, frozen 2026-11-12 in
`rebuttal/pilots/20261112_missing_fact_repair/GATE_V2A_RULE.md` before any call.
It changes only the recall term: the fact's content tokens (all fact tokens
minus STOP) must be carried at recall >= 0.8. Every other v1 reason is kept
unchanged. v1 in `e4_fix_gates.py` is untouched and remains on record.
"""
from collections import Counter

from src.audit.e4_fix_gates import DELIVERY_RECALL, STOP, toks
from src.protocols.base import is_refusal


def recall_content(text, fact):
    """Fraction of the fact's content tokens that the text carries (multiset)."""
    ft = Counter(t for t in toks(fact) if t not in STOP)
    if not ft:
        return 0.0
    tt = Counter(toks(text))
    return sum(min(n, tt[t]) for t, n in ft.items()) / sum(ft.values())


def delivery_reasons_v2(text, fact_text, question=None):
    reasons = []
    s = (text or '').strip()
    if not s:
        reasons.append('empty')
        return reasons
    low = s.lower()
    if low.startswith('question:') or (question and low == question.strip().lower()):
        reasons.append('question text')
    if low.startswith('[document:') or low.startswith('[doc'):
        reasons.append('document header')
    if is_refusal(s):
        reasons.append('refusal')
    if s.startswith('[') and s.count(',') >= 5:
        reasons.append('data-list fragment')
    r = recall_content(s, fact_text)
    if r < DELIVERY_RECALL:
        reasons.append(f'fact content recall {r:.2f} < {DELIVERY_RECALL}')
    return reasons


def delivery_gate_v2(text, fact_text, question=None):
    reasons = delivery_reasons_v2(text, fact_text, question)
    return {'ok': not reasons, 'reasons': reasons,
            'recall': round(recall_content(text, fact_text), 3)}