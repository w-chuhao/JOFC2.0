# Project 4: Workload Split for Three People

## Team operating rule

Work against one shared interface from day one. The integration branch must always run the official evaluator; each person owns tests for their module and reviews one teammate's pull request. Freeze features by Monday morning so Monday afternoon is reserved for proof, documentation, and the demo.

## Ownership

| Person | Primary ownership | Concrete deliverables | Backup / review responsibility |
|---|---|---|---|
| **Person 1 - Retrieval and ranking lead** | Catalog loading, metadata filters, BM25, dense retrieval, candidate fusion/diversification, hybrid reranker | Reproducible index build/cache; ranked candidate API; baseline-versus-final metric table | Review agent integration; keep a BM25-only fallback |
| **Person 2 - Conversation-agent lead** | Official agent interface, intent router, dialogue state machine, override/slot reset logic, clarification policy, final response formatting | Runnable end-to-end agent; router/state/clarification tests; example successful and changed-intent conversations | Review retrieval contract and write the architecture section |
| **Person 3 - Evaluation and submission lead** | Starter-kit setup, data/session inspection, evaluator automation, experiment tracking, regression tests, README, Devpost draft, demo production | One-command evaluation notes; experiment log; clean README; metrics/error analysis; public demo video and submission checklist | Review final repository, credentials scan, and reproducibility run |

## Required hand-offs

| Deadline (SGT) | Handoff | Owner | Recipient / acceptance condition |
|---|---|---|---|
| Thu 27 Aug, 12:00 | Baseline agent, data format, evaluator command and initial metrics | Person 3 | Whole team can run the same baseline |
| Thu 27 Aug, 18:00 | `ConversationState` schema plus retrieval request/response contract | Person 2 | Person 1 can implement retrieval without guessing fields |
| Sat 29 Aug, 12:00 | First hybrid ranker callable from the agreed interface | Person 1 | Person 2 can connect it to the agent |
| Sun 30 Aug, 12:00 | Integrated multi-turn agent with clarification and intent override | Persons 1 + 2 | Person 3 can run public-session evaluation |
| Sun 30 Aug, 20:00 | Metrics table, failures to fix, and 2-3 demo scenarios | Person 3 | Whole team agrees on final tuning priorities |
| Mon 31 Aug, 10:00 | Feature freeze; only defects, tests, docs, and demo changes after this point | Whole team | Evaluator completes and no interface changes remain |
| Mon 31 Aug, 18:00 | README/Devpost draft and recorded demo ready for review | Person 3 | Whole team signs off on technical accuracy |
| Tue 1 Sep, 10:30 | Clean-clone verification, final evaluator metrics, and upload check | Persons 1-3 | Submission ready with 90-minute buffer |

## Daily cadence

- **09:30, 10 minutes:** each person states yesterday's evidence, today's outcome, and one blocker.
- **18:00, 15 minutes:** integrate to the shared branch, run the evaluator, and record metrics. Do not end the day with unmerged incompatible interfaces.
- **Monday after 10:00:** reject new features unless they directly fix a scored requirement or a reproducibility defect.

## Friday-Sunday task detail

### Person 1 - Retrieval and ranking

- Build catalog normalisation and field filters.
- Establish BM25 baseline, then add local embedding retrieval and candidate fusion.
- Implement reranking weights/configuration and diversity handling.
- Provide a small failure-analysis report: bad categories, sparse metadata, or near-duplicate results.

### Person 2 - Conversation agent

- Build intent decision rules and test with a small labelled fixture set.
- Implement additive slots and explicit replacement/erasure, e.g. "not shoes - I need a handbag instead".
- Decide exactly when to ask a clarification; ensure the answer asks one useful question and preserves context.
- Integrate Person 1's ranker and ensure responses honour the organiser's API schema.

### Person 3 - Evaluation and communication

- Automate baseline and final evaluations and save a simple metrics CSV/JSON outside versioned secrets/data.
- Compare every material change with the public evaluator; stop regressions early.
- Draft README and Devpost copy from actual implementation evidence, not future plans.
- Produce demo: problem (20 sec), architecture (30 sec), live multi-turn success (60 sec), intent override/clarification (30 sec), metrics/limitations (30 sec).

## Tuesday submission sequence

1. Person 1 runs the final evaluator and confirms the metrics table.
2. Person 2 runs a fresh end-to-end conversation and checks the official interface/turn limit.
3. Person 3 checks repository visibility, README, Devpost links, YouTube visibility, and secret-free status.
4. Submit by **11:30 AM SGT**; retain the last 30 minutes as genuine contingency.
