# Independent MiniLM Model Comparison

## Purpose and independence

This benchmark tests semantic product relevance separately from the organizer's public evaluator. It contains 18 manually written shopping intents covering wallets, outerwear, work shoes, socks, jewelry, bags, hats, maternity wear, belts, and leggings.

- The queries were written from frozen-catalog attributes, not copied or paraphrased from public session prompts.
- All 18 target ASINs and all 163 candidate ASINs have zero overlap with the 200 public ground-truth ASINs.
- Every case uses the same fixed ten-product hard-negative pool for every model.
- When the deterministic retriever did not place the target in its first ten results, the target replaced the tenth result. Consequently, this is a controlled reranking benchmark, not an end-to-end catalog-recall benchmark.
- The target is the catalog product that uniquely combines the multiple attributes stated in the query. Labels were selected before running any semantic model.

The fixture is `tests/fixtures/semantic_ranking_cases.json`. The benchmark rejects public-target overlap, duplicate candidates, missing targets, invalid rankings, missing catalog IDs, and non-finite scores.

## Compared configurations

All models ran locally on CPU with identical production-order product text, a 256-token maximum, and batch size 16.

| Key | Model | Role |
|---|---|---|
| L6 CrossEncoder | `cross-encoder/ms-marco-MiniLM-L6-v2` | Current optional pairwise reranker |
| L12 CrossEncoder | `cross-encoder/ms-marco-MiniLM-L12-v2` | Larger drop-in pairwise reranker |
| L12 dense | `sentence-transformers/msmarco-MiniLM-L12-cos-v5` | Bi-encoder with precomputed candidate embeddings |

## Results

Accuracy is deterministic. Latency is the median of three cached runs on the same arm64 machine using Python 3.14.5, PyTorch 2.10.0, and Transformers 4.53.3.

| Configuration | Hit@1 | Hit@3 | Hit@10 | MRR | Median CPU time per 10-item case |
|---|---:|---:|---:|---:|---:|
| Fixed deterministic candidate order | 0.0556 | 0.1667 | 1.0000 | 0.188889 | n/a |
| L6 CrossEncoder | 0.7778 | 0.9444 | 1.0000 | 0.875000 | 91.65 ms |
| L12 CrossEncoder | **0.8333** | **0.9444** | 1.0000 | **0.893519** | 188.40 ms |
| L12 dense | 0.5556 | 0.8889 | 1.0000 | 0.720370 | **5.87 ms** after indexing |

The dense model indexed the 163 unique benchmark candidates in a median 3.21 seconds. Its 768-dimensional float32 embeddings would occupy about 153.6 MB for all 50,000 catalog products, excluding model and index overhead.

L12 versus L6 was not a broad improvement: 16 of 18 target ranks were identical. L12 improved `large_rfid_card_organizer` from rank 2 to 1 and worsened `convertible_vegan_backpack` from rank 2 to 3. Its MRR gain was therefore driven by one favorable asymmetric MRR change while CPU inference was about twice as slow.

The dense model was strong enough for candidate discovery but weaker as the final ordering model. It placed `convertible_vegan_backpack` tenth, while the CrossEncoders placed it second and third. Conversely, it placed the packable raincoat first and the yoga leggings second, showing useful route diversity.

## Decision

- Keep L6 as the preferred local CrossEncoder when a richly specified query justifies semantic reranking.
- In the production Agent, require at least two concrete non-category constraints, apply deterministic filtering first, and preserve a rank-1 candidate that satisfies every required constraint. This guarded L6 path improved the independent Agent check from Hit@10 `0.5000`/MRR `0.173920` to `0.5556`/`0.218364`.
- Do not replace L6 with L12 by default: the small-set gain is narrow and costs roughly double the CPU inference time.
- Evaluate the dense L12 model as an additional in-memory Browsing candidate route, not as the final ranker.
- Continue disabling semantic reranking for broad category-only queries; this independent benchmark deliberately provides enough attributes to identify one product, unlike the ambiguous public cases that reduced public-set MRR.
- Do not treat these 18 handcrafted cases as private-set evidence. Expand with blinded team-written queries and category-held-out evaluation before changing the scoring default.

## Reproduction

After caching the three model checkpoints:

```powershell
$env:PYTHONPATH="."
$catalogPath = Resolve-Path "..\catalog.jsonl"  # Replace with this machine's catalog location.
python scripts/benchmark_semantic_models.py `
  --cases tests/fixtures/semantic_ranking_cases.json `
  --public-set data/public_set.jsonl `
  --catalog "$catalogPath" `
  --models cross-encoder-l6 cross-encoder-l12 dense-minilm-l12 `
  --output .tmp/semantic-benchmark/results.json
```

Use `--allow-download` only for the initial model download. Model weights and raw benchmark output remain outside Git.

## TDD evidence

| Guarantee | RED evidence | GREEN evidence |
|---|---|---|
| Public labels cannot become benchmark targets | Benchmark module import failed before implementation | Overlap fixture raises `ValueError`; the real fixture reports zero overlap |
| Public-label products cannot enter hard-negative pools | Public candidate overlap test initially failed because only targets were checked | Candidate overlap now raises `ValueError`; the real fixture has zero candidate overlap |
| Every ranking is a permutation of the fixed candidates | Missing benchmark functions caused import failure | Unknown and duplicate IDs are rejected |
| Metrics use exact rank and reciprocal rank | Missing evaluator caused import failure | Synthetic ranks 1 and 3 produce Hit@1 0.5 and MRR 0.6667 |
| Product text matches the production field order | Missing catalog loader caused import failure | Loader test checks the exact title/category/feature/detail/store/description string |
| All models receive the same candidates | Missing `rank_cases` caused import failure | Injected scorer test proves fixed candidate use and exact ranking |

No RED or GREEN checkpoint commits were created because this project requires explicit user approval before every commit.

Verification completed with `75` unit/integration tests passing, Python compilation, `git diff --check`, and language-server diagnostics. A built-in `trace` integration run exercised all three real model paths; third-party branch coverage remains unavailable in the system interpreter.
