# Part B first-missing-checkpoint labels from stored presence records

2026-11-15. Rule `Part-B-validated-label.md` (sha `cbe9ea72...`). Labels read from the design-A carrier records at
$0 (board presence κ .857, extraction κ .780); Opus reference through the CLI on 7 stratified facts.

## Derived labels and multi-stage counts

| population | traces | multi-stage | rate |
| --- | ---: | ---: | ---: |
| cohort (natural failures) | 59 | 41 | .695 |
| injected | 30 | 4 | .133 |
| all | 89 | 45 | .506 |

277 facts labelled from stored carriers.

## Opus reference check, widened to 30 facts: fails

| sample | n | agreement | κ |
| --- | ---: | ---: | ---: |
| first stratified sample | 7 | 4/7 = .571 | .364 |
| disjoint extension | 23 | 14/23 = .609 | .425 |
| combined | 30 | 18/30 = .600 [.423, .754] | .427 |

Below both bars (.80 / .60). Opus names a shard stage on 5 of the 30, which the derived labels never emit. The
derived labels are therefore not validated, and no per-fact accuracy or re-derived multi-stage rate is citable
from them.

## Ledger

$1.142940 API-equivalent, $0.330967 CLI for the 23 extension calls under the $5.00 cap; the first 7 calls were
$0.345828 API-equivalent, $0.132874 CLI, and their call records are no longer on disk (the extension run wrote
only its own rows into the same files), so the ledger carries that figure from `run.log` on a separate line.
Part B line total $2.092212 API-equivalent.

## Where the 12 disagreements fall ($0, stored rows)

The 30 paired facts disagree on 12. Read from the stored statuses, three causes, none dominant:

| cause | cases | what it is |
| --- | ---: | --- |
| partial treated as carried | 5 | the composite passes a checkpoint when any carrier exists, so `partial` goes forward; the reference calls a partial fact missing at that checkpoint |
| no shard stage | 5 | the reference answers `sharding`; the composite's label space has extraction, transmission and aggregation only |
| reference places the loss later | 3 | no carrier at extraction, yet the reference answers `aggregation` |

One case carries two causes, hence 5 + 5 + 3 − 1 = 12. Because no single principled rule explains the set,
Part B stays negative: no rule change, no fresh sample, no further calls. The text uses only the 47/59 lexical
multi-stage count.
