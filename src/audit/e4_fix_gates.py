"""Setup gates for the E4 repair experiments (R2, R3, R4, R6).

These are pre-flight checks, not scoring. They read frozen text only and make
no model calls. A run is allowed to spend only on arms that pass its gate.

R2 delivery: a repair text must carry the target fact (token recall >= 0.8)
and must not be question text, a document header, a refusal, or a data-list
fragment. Otherwise the answer call is skipped and the arm is logged as a
delivery failure.

R3 case design: exactly one support fact may be absent from the pool.

R4 data: the board alone must not reach the gold, the target fact is in the
support set, the board plus that fact reaches the gold, and the fact is not a
tautology. "Reaches" means a unit states the gold and shares a content token
with the question or the chain; a unit cannot vouch for itself, and a gold
stated in a disconnected unit does not count.

R6 matcher: selection needs a faithful extraction carrier and no board
carrier; distortion needs the swap to carry the distorted fact (recall >= 0.8)
and the replaced unit to carry it too (recall >= 0.5).
"""
from collections import Counter

from src.eval.evaluate import normalize
from src.protocols.base import is_refusal

STOP = {
    'county', 'city', 'located', 'near', 'line', 'state', 'united', 'states',
    'one', 'two', 'three', 'first', 'second', 'also',
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'am',
    'has', 'had', 'have', 'do', 'does', 'did', 'done',
    'which', 'who', 'whom', 'whose', 'what', 'when', 'where', 'why', 'how',
    'that', 'this', 'these', 'those', 'it', 'its', 'they', 'their', 'them',
    'he', 'she', 'his', 'her', 'him', 'we', 'our', 'you', 'your', 'i',
    'and', 'or', 'but', 'not', 'no', 'than', 'then', 'so', 'such',
    'in', 'on', 'at', 'to', 'of', 'for', 'with', 'by', 'from', 'as',
    'into', 'over', 'under', 'about', 'after', 'before', 'between',
    'during', 'through', 'up', 'down', 'out', 'off', 'again', 'once',
    'here', 'there', 'all', 'any', 'both', 'each', 'few', 'more', 'most',
    'other', 'some', 'only', 'own', 'same', 'too', 'very', 'just', 'now',
    'would', 'could', 'should', 'can', 'may', 'might', 'must', 'will',
    'shall', 'part', 'nearby', 'border', 'shares', 'share', 'borders',
}

DELIVERY_RECALL = 0.8
SWAP_RECALL = 0.8
REPLACED_RECALL = 0.5


def toks(s):
    return normalize(s)


def content(s):
    return set(toks(s)) - STOP


def recall(text, fact):
    """Fraction of the fact's tokens that the text carries (multiset)."""
    ft = Counter(toks(fact))
    if not ft:
        return 0.0
    tt = Counter(toks(text))
    return sum(min(n, tt[t]) for t, n in ft.items()) / sum(ft.values())


def covers(text, gold):
    t = set(toks(gold))
    return bool(t) and t <= set(toks(text))




def reaches_gold(units, gold, question, fact_text=None, fact_is_last=False):
    """A gold-bearing unit counts only if it links to the existing chain.

    With `fact_is_last`, the final unit is the candidate repair fact; it must
    link to the question or to one of the earlier units (a unit cannot vouch
    for itself). With no `fact_text`, only the question is an anchor.
    """
    q = content(question)
    for i, u in enumerate(units):
        if not covers(u, gold):
            continue
        uc = content(u)
        if fact_is_last and i == len(units) - 1:
            if uc & q or any(uc & content(b) for b in units[:-1]):
                return True
        elif uc & q or (fact_text is not None and uc & content(fact_text)):
            return True
    return False


def tautology(question, fact):
    return not (set(toks(fact)) - set(toks(question)))


def delivery_reasons(text, fact_text, question=None):
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
    r = recall(s, fact_text)
    if r < DELIVERY_RECALL:
        reasons.append(f'fact recall {r:.2f} < {DELIVERY_RECALL}')
    return reasons


def delivery_gate(text, fact_text, question=None):
    reasons = delivery_reasons(text, fact_text, question)
    return {'ok': not reasons, 'reasons': reasons, 'recall': round(recall(text, fact_text), 3)}


def r4_signals(question, gold, board_units, facts, fact_id, missing_ids):
    fact_text = facts[fact_id]
    sig = {
        'missing_ids': list(missing_ids),
        'n_missing': len(missing_ids),
        'fact_in_support': fact_id in facts,
        'board_reaches_gold': reaches_gold(board_units, gold, question),
        'board_plus_fact_reaches_gold': reaches_gold(board_units + [fact_text], gold,
                                                     question, fact_text, fact_is_last=True),
        'fact_is_tautology': tautology(question, fact_text),
        'r3_single_fact': len(missing_ids) == 1,
    }
    # A repair case must have nothing missing on the board: if the board alone
    # already reaches the gold, the case is (b) present-but-unused, not a
    # missing-fact case.
    sig['r4_pass'] = (sig['fact_in_support']
                      and not sig['board_reaches_gold']
                      and sig['board_plus_fact_reaches_gold']
                      and not sig['fact_is_tautology'])
    sig['pass'] = sig['r3_single_fact'] and sig['r4_pass']
    return sig


def selection_eligible(carriers):
    """Fact ids with a faithful extraction carrier and no board carrier."""
    out = []
    for c in carriers.get('facts', []):
        ext = c.get('extraction') or []
        board = c.get('board') or []
        if not board and any(e.get('fidelity') == 'faithful' for e in ext):
            out.append(c['fact_id'])
    return out


def distortion_gate(swap_text, distorted_facts, replaced_unit_text):
    swap = {fid: round(recall(swap_text, t), 3) for fid, t in distorted_facts.items()}
    replaced = {fid: round(recall(replaced_unit_text, t), 3) for fid, t in distorted_facts.items()}
    ok = bool(swap) and max(swap.values()) >= SWAP_RECALL and max(replaced.values()) >= REPLACED_RECALL
    return {'ok': ok, 'swap_recall': swap, 'replaced_recall': replaced,
            'reason': None if ok else 'swap or replaced unit misses the distorted fact'}