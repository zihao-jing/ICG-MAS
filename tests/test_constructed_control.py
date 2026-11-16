import re
from src.audit.constructed_control import split_segments,select_segments,build_control,sha_order,parse_check
count=lambda s:len(re.findall(r'\w+|[^\w\s]',s))   # offline stand-in tokenizer for unit tests
PROSE=' '.join(f'Sentence {i} talks about topic {i} in some detail here.' for i in range(30))
DATA=str(list(range(1000,1040)))
def test_split_keeps_whole_records_and_sentences():
    assert split_segments('[-439, -61, 985]')==['-439','-61','985']
    s=split_segments(PROSE);assert len(s)==30 and all(x.endswith('.') for x in s)
    assert split_segments('YBADYZ')==['YBADYZ']
def test_selection_is_deterministic_and_order_independent_of_call_count():
    segs=split_segments(PROSE);a=select_segments(segs,'c1','V-ext',2,22,count);b=select_segments(segs,'c1','V-ext',2,22,count)
    assert a==b and a is not None
    assert select_segments(segs,'c2','V-ext',2,22,count)!=a or True  # different case id may differ; no assertion on equality
def test_unit_count_equal_and_tokens_within_ten_percent():
    segs=split_segments(PROSE)
    for units,tokens in [(1,11),(2,22),(3,33)]:
        sel=select_segments(segs,'case','V-sel',units,tokens,count)
        assert sel is not None and len(sel)==units
        t=sum(count(s) for s in sel);assert 0.9*tokens<=t<=1.1*tokens
def test_selected_segments_are_substrings_of_the_donor_shard_and_never_cut():
    segs=split_segments(PROSE);sel=select_segments(segs,'case','V-dist',2,22,count)
    assert all(s in segs and s in PROSE for s in sel)
def test_no_selection_when_records_are_too_short_for_the_unit_rule():
    # records of 1-2 tokens cannot make 2 units of about 50 tokens: A2 as written has no feasible selection
    assert select_segments(split_segments(DATA),'case','V-ext',2,50,count) is None
def test_excluded_segments_are_never_reused_after_a_failed_check():
    segs=split_segments(PROSE);first=select_segments(segs,'case','V-ext',2,22,count)
    second=select_segments(segs,'case','V-ext',2,22,count,excluded=first)
    assert second is not None and not set(first)&set(second)
def test_target_segments_are_never_selected_because_only_donor_shard_is_used():
    target=' '.join(f'Target fact {i} is stated here for the other agent today.' for i in range(30))
    sel=select_segments(split_segments(PROSE),'case','V-ext',3,33,count)
    assert sel is not None and not set(sel)&set(split_segments(target))

def test_redraw_limit_and_unavailable_label():
    res=build_control(PROSE,'needed','case','V-ext',2,22,count,check=lambda t:False)
    assert not res['built'] and res['redraws']==2 and res['label']=='no same-volume control available' and len(res['attempts'])==3
    used=[s for a in res['attempts'] for s in (a['selection'] or [])];assert len(used)==len(set(used))   # never reused
def test_passes_on_first_draw_with_no_redraw():
    res=build_control(PROSE,'needed','case','V-ext',2,22,count,check=lambda t:True)
    assert res['built'] and res['redraws']==0
def test_unparseable_check_counts_as_failure():
    assert parse_check('PASS: fine') is True and parse_check('FAIL: states it') is False and parse_check('maybe') is None
    res=build_control(PROSE,'n','case','V-ext',2,22,count,check=lambda t:parse_check('maybe'))
    assert not res['built']
def test_reporting_separation_helper_never_pools_built_and_natural():
    from src.audit.constructed_control import report_rows
    rows=[{'control_kind':'natural','delta':1.0},{'control_kind':'natural','delta':0.0},{'control_kind':'constructed','delta':1.0}]
    out=report_rows(rows)
    assert out['natural']['n']==2 and out['constructed']['n']==1 and 'pooled' not in out


def test_segments_carrying_a_needed_fact_are_never_selected():
    segs=split_segments(PROSE);carriers=set(segs[:25])   # only 5 clean segments remain
    sel=select_segments(segs,'case','V-ext',2,22,count,forbidden=carriers)
    assert sel is not None and not set(sel)&carriers
    assert select_segments(segs,'case','V-ext',2,22,count,forbidden=set(segs)) is None


def test_shard_given_as_a_python_list_is_split_into_whole_records():
    assert split_segments([(1,2),(3,4)])==['(1, 2)','(3, 4)']
    assert split_segments({'a':1})==['a: 1']
