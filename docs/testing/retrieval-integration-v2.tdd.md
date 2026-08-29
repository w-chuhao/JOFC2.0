# Retrieval integration v2 TDD evidence

## Source and user journeys

The integration plan was derived during this task rather than from a separate plan file.

- As a shopper, I want follow-up retrieval to retain the specific product category while ignoring dialogue-only filler.
- As a shopper, I want explicit exclusions and intent overrides to remove stale preferences instead of reintroducing them.
- As a shopper, I want useful clarification questions selected from candidate distributions with deterministic fallbacks.
- As a shopper, I want exact feature phrases and required constraints preserved while popularity acts only as a decaying tie-breaker.
- As a developer, I want traces, search diagnostics, and existing remote-main behavior to remain covered.

## RED and GREEN evidence

| Behavior | Test target | RED evidence | GREEN evidence |
|---|---|---|---|
| Stable category query and dialogue stripping | `tests.test_agent.AgentConversationTest.test_retrieval_query_retains_leaf_category_and_strips_dialogue` | `SessionState` lacked `retrieval_query_for` | Passed after adding stable category context and query construction |
| Override and exclusion safety | `test_blanket_override_clears_initial_preference_evidence`, `test_negative_preference_is_not_reintroduced_as_positive` | Stale feature evidence and negated material remained positive | Both passed after tracking initial clues and applying exclusions before positive updates |
| Adaptive deterministic clarification | `test_candidate_statistics_select_discriminating_attribute`, `test_user_profile_prioritizes_relevant_question_when_stats_are_weak` | `choose_clarification` rejected candidate statistics | Both passed with information-value selection and profile/fixed-order fallbacks |
| Expanded candidate statistics | `tests.test_retrieval.CatalogSearchTest.test_candidate_statistics_include_color_and_brand` | Candidate statistics had no `brand` key | Passed with expanded attribute counters |
| Decaying popularity tie-break | `test_popularity_breaks_an_identical_text_tie`, `test_popularity_prior_decays_with_cross_turn_exploration` | Identical products sorted by ID and no decay function existed | Both passed while main's exact feature-phrase tests remained green |
| Intent-override trace fixture | `tests.test_trace_public_sessions.TracePublicSessionsTest.test_override_trace_does_not_score_a_pre_override_target_match` | Fixture raised `KeyError: old_value` | Passed after supplying the evaluator-required field |

## Validation

- `DEEPSEEK_ENABLED=0 python3 -m unittest -v tests.test_agent tests.test_retrieval`: 35 tests passed.
- `DEEPSEEK_ENABLED=0 python3 -m unittest discover -v`: 52 tests passed.
- `python3 -m compileall -q starter tests scripts`: passed.
- `git diff --check`: passed.
- Python language-server diagnostics: no errors, warnings, or hints in the changed Python source and tests.
- Coverage was not collected because the active Python environment does not include the `coverage` module; no dependency was installed solely for this run.

## Evaluator evidence

The 200-session public evaluator ran with `DEEPSEEK_ENABLED=0`, `--catalog ../catalog.jsonl`, and output under the operating-system temporary directory.

- Hit Rate@10: `1.000`
- MRR: `0.623800`
- MTTC: `1.735`
- Efficiency: `0.9265`
- Recommended Technical Score: `0.872440`
- Reported LLM tokens: `0`

These public-set results are regression evidence, not a guarantee of private-set performance.

## Commit evidence

No TDD checkpoint commits were created because this project's durable workflow requires explicit user approval of the descriptive commit message before any commit. The RED/GREEN evidence is preserved here instead.
