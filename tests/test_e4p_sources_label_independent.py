import re
from pathlib import Path
SRC=Path('scripts/run_e4p_seed43_sources.py').read_text()
def test_runner_imports_nothing_that_reads_labels_matchers_or_groups():
    imports=' '.join(re.findall(r'^(?:from|import) [^\n]+',SRC,re.M)).lower()
    for bad in ('matcher','pilot_selection','labels','diagnos','e4_balance','repair_study','frozen_matcher'):
        assert bad not in imports,bad
def test_runner_never_filters_on_correctness_and_stores_it_only():
    assert "answer_matches_gold" in SRC and "never used to filter" in SRC
    assert not re.search(r'if\s+[^\n]*answer_matches_gold',SRC) and not re.search(r'if\s+not\s+[^\n]*answer_matches_gold',SRC)
def test_runner_lists_qualifying_and_excluded_steps():
    assert 'NOT run here' in SRC and 'matcher, group assignment, target/donor choice' in SRC
def test_runner_uses_only_the_three_base_models():
    for m in ('qwen/qwen3-235b-a22b-2507','openai/gpt-4o-mini','google/gemma-4-31b-it'):assert m in SRC
    assert 'gemini' not in SRC.lower()
