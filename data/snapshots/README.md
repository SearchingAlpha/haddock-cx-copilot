# Snapshots

The only SQLite databases in the repo. Everything else (`*.db`) is ignored on purpose.

| File | What | Used by |
|---|---|---|
| `queue.db` | The demo state: the 15 processed `T-` tickets of the queue, no reviews, plus the radar with its history and 6 candidates with the product request drafted. No problem approved yet. Kutxabank is `P-0009`. | `cp data/snapshots/queue.db haddock.db` on a new machine, or before a rehearsal |
| `radar-notices.db` | The `evals/run_notices.py` run: P-0004 resolved with 12 proactive notices. | `scripts/build_golden.py --radar` (default), for the public demo |

Synthetic data only, no keys. Regenerating `queue.db` calls Sonnet and is not deterministic: the demo script relies on this exact state.
