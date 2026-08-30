# Hybrid Semantic Routing TDD Evidence

## Source and user journeys

The journeys were derived from the official Challenge 4 dual-track, in-memory retrieval, semantic-ranking, and offline-feasibility requirements.

- As a high-intent buyer, I want required constraints to narrow results without eliminating the requested Top-K.
- As a shopper with multiple concrete requirements, I want an optional semantic ranker to refine only valid filtered candidates without displacing an exact required match.
- As an evaluator operator, I want missing models, inference failures, and invalid route names to fail safely without corrupting deterministic recommendations.

## RED and GREEN evidence

| Behaviour | RED evidence | GREEN evidence | Guarantee |
|---|---|---|---|
| Route policy is consumed | `python3 -m unittest tests.test_retrieval -v` failed because `_candidate_scores` rejected `route` and diagnostics lacked a strategy | Retrieval suite passed after route-policy implementation | Buying and Browsing execute explicit policies and invalid route names raise `ValueError` |
| Guarded Buying filtering | Route diagnostics and required-filter tests failed before implementation | `test_buying_route_reports_guarded_required_constraint_filtering` passed | Filtering is applied only when at least `top_k` required matches remain |
| Field-specific attributes | A canvas shoe from `Leather Goods Outlet` incorrectly matched required leather material | `test_attribute_coverage_does_not_treat_store_name_as_material` passed | Store text can satisfy brand, but cannot leak into material/color/size/style/feature/use-case matching |
| Semantic specificity gate | Broad category-only Browsing invoked the model, while filtered Buying queries skipped it | Specificity and Agent integration tests passed | The model runs only after two non-category constraints, independently of the route label |
| Semantic candidate safety | A fake model could displace an exact deterministic rank-1 result | Candidate validation and protected-first tests passed | Unknown/duplicate IDs are ignored and a rank-1 product satisfying every required constraint is preserved |
| Local model adapter | `tests.test_local_reranker` failed to import the missing module | Four adapter tests passed | Scores must be finite, one per candidate, and configuration is opt-in |
| Agent integration | Explicit-reranker agent test failed because `Agent` rejected the constructor argument | Targeted agent, adapter, and retrieval tests passed | The official entry point can use a supplied local reranker while preserving default deterministic behaviour |

No RED or GREEN checkpoint commits were created because this project requires explicit user approval before every commit.

## Evaluation evidence

All runs used `DEEPSEEK_ENABLED=0`, the frozen outer catalog, and the official 200-session evaluator.

| Configuration | HR@10 | MRR | MTTC | Technical Score | Decision |
|---|---:|---:|---:|---:|---|
| Deterministic baseline | 1.000 | 0.623800 | 1.735 | 0.872440 | Reference |
| Wider Browsing pool | 1.000 | 0.608687 | 1.715 | 0.868306 | Rejected; all score loss came from the wider pool |
| Guarded Buying filter with baseline pool sizes | 1.000 | 0.623800 | 1.735 | 0.872440 | Retained; score-neutral and safer |
| Local CrossEncoder, weight 0.35, top 50 | 1.000 | 0.585181 | 1.725 | 0.861054 | Rejected as default |
| Local CrossEncoder, weight 0.05, top 20 | 1.000 | 0.623800 | 1.735 | 0.872440 | Score-neutral but materially slower; opt-in only |
| Field-specific attribute text, no model | 1.000 | 0.623800 | 1.735 | 0.872440 | Retained; fixes false matches without score loss |
| Specificity gate + protected rank 1, L6 weight 0.35/top 20 | 1.000 | 0.624593 | 1.735 | 0.872678 | Best model variant; remains opt-in due model packaging and latency |
| Current `origin/main` merged, no model | 1.000 | 0.624008 | 1.735 | 0.872502 | Current branch default |
| Current `origin/main` merged, guarded L6 weight 0.35/top 20 | 1.000 | 0.623704 | 1.735 | 0.872411 | Current combined public run regressed; keep disabled |

The original stronger semantic configuration changed 83 sessions: 34 improved and 49 regressed. The final guarded configuration changed only eight sessions, improving five and regressing three, with no recall or MTTC loss. It made 68 local calls over 200 sessions and spent about 13.2 seconds in model inference. The model is therefore a validated optional path, not the default scoring dependency.

The first seven rows above were measured from local `main` at `c306448`. Remote `main` later advanced to `f657a16`; the final two rows are fresh reruns after merging those collaborator changes into this branch. This makes the current decision stricter: the semantic adapter and its independent benchmark remain reproducible, but current submission scoring should use the deterministic default.

Two tempting public-only variants were rejected. Profile-tag product bonuses reduced Technical Score to `0.858444`, because tags such as `fit` and `material` describe preference dimensions rather than values. Raising only the discovery popularity weight from `0.020` to `0.030` increased the public Technical Score to `0.874757`, but reduced the independent Agent benchmark from Hit@10 `0.5000`/MRR `0.173920` to `0.3333`/`0.120370`; the apparent public gain was not a relevance improvement.

## Verification and known gaps

- Unit and integration runner: `python3 -m unittest discover -s tests -v` (`75` tests passed)
- Line tracing: `python3 -m trace --count --summary --coverdir /tmp/techjam_hybrid_trace --module unittest discover -s tests` reported `100%` executed-line coverage for the `starter` modules. The system interpreter did not have the third-party `coverage` package, so branch coverage was not available.
- Compilation: `python3 -m compileall -q starter tests`
- Language diagnostics: checked on changed Python files
- Full evaluator: commands and outputs above
- An independent 18-case shopping relevance benchmark now compares the L6 CrossEncoder, L12 CrossEncoder, and L12 dense MiniLM without public target or candidate overlap; see `docs/testing/semantic-model-comparison.md`. It remains a handcrafted reranking test, not proof of private-set generalisation.
