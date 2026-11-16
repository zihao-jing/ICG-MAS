# Amendment 2: diagnosis runs on the validated-renderer pair

2026-11-15, $0. The cause method in `Proxy-gold-disagreement-causes.md` is unchanged. The pair is now the
validated-renderer records (`Q1-validated-rerun.md`): gold atoms and proxy atoms both come from that run, both
sides labelled with `a1: text` ids, all 30 traces per sample scored.

Gold atoms are read from the run's gold records at the failing checkpoint; the atom text is the split of the row's
first gold support. Everything else (recall thresholds .8/.5, the three causes, majority assignment per trace,
the no-gold-absent-atom class) is as frozen.
