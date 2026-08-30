"""Compare local semantic rankers on independent, fixed shopping cases."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


ScoreFunction = Callable[[str, list[str]], list[float]]

MODEL_REFERENCES = {
    "cross-encoder-l6": "cross-encoder/ms-marco-MiniLM-L6-v2",
    "cross-encoder-l12": "cross-encoder/ms-marco-MiniLM-L12-v2",
    "dense-minilm-l12": "sentence-transformers/msmarco-MiniLM-L12-cos-v5",
}


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    query: str
    target_parent_asin: str
    candidate_ids: tuple[str, ...]


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(f"{key} {_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    return str(value)


def rank_by_scores(
    candidate_ids: tuple[str, ...],
    scores: list[float],
) -> list[str]:
    if len(scores) != len(candidate_ids) or any(
        not math.isfinite(float(score)) for score in scores
    ):
        raise ValueError("ranker must return one finite score per candidate")
    indexed = zip(range(len(candidate_ids)), candidate_ids, scores, strict=True)
    return [
        candidate_id
        for _, candidate_id, _ in sorted(
            indexed,
            key=lambda item: (-float(item[2]), item[0]),
        )
    ]


def load_candidate_documents(
    catalog_path: str | Path,
    cases: list[BenchmarkCase],
) -> dict[str, str]:
    required_ids = {
        candidate_id for case in cases for candidate_id in case.candidate_ids
    }
    documents: dict[str, str] = {}
    with Path(catalog_path).open(encoding="utf-8") as handle:
        for line in handle:
            product = json.loads(line)
            parent_asin = str(product["parent_asin"])
            if parent_asin not in required_ids:
                continue
            full_text = " ".join(
                _text(product.get(field))
                for field in (
                    "title",
                    "categories",
                    "features",
                    "details",
                    "store",
                    "description",
                )
            ).strip()
            documents[parent_asin] = full_text[:4000]
    missing = sorted(required_ids - set(documents))
    if missing:
        raise ValueError(f"catalog is missing candidate IDs: {', '.join(missing)}")
    return documents


def _public_targets(public_set_path: Path) -> set[str]:
    targets: set[str] = set()
    if not public_set_path.exists():
        raise ValueError(f"public set not found: {public_set_path}")
    with public_set_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            sample = json.loads(line)
            targets.add(str(sample["ground_truth"]["parent_asin"]))
    return targets


def load_benchmark_cases(
    cases_path: str | Path,
    public_set_path: str | Path,
) -> list[BenchmarkCase]:
    raw_cases = json.loads(Path(cases_path).read_text(encoding="utf-8"))
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("benchmark cases must be a non-empty JSON list")
    public_targets = _public_targets(Path(public_set_path))
    cases: list[BenchmarkCase] = []
    seen_case_ids: set[str] = set()
    for raw in raw_cases:
        case_id = str(raw["case_id"]).strip()
        query = str(raw["query"]).strip()
        target = str(raw["target_parent_asin"]).strip()
        candidate_ids = tuple(str(value).strip() for value in raw["candidate_ids"])
        if not case_id or case_id in seen_case_ids:
            raise ValueError(f"duplicate or empty case ID: {case_id!r}")
        if not query:
            raise ValueError(f"empty query for case {case_id}")
        if target in public_targets:
            raise ValueError(f"case {case_id} uses a public target: {target}")
        public_candidates = sorted(set(candidate_ids) & public_targets)
        if public_candidates:
            raise ValueError(
                f"case {case_id} uses a public candidate: {', '.join(public_candidates)}"
            )
        if len(candidate_ids) < 2:
            raise ValueError(f"case {case_id} needs at least two candidates")
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError(f"case {case_id} has a duplicate candidate")
        if target not in candidate_ids:
            raise ValueError(f"case {case_id} target is not a candidate")
        cases.append(BenchmarkCase(case_id, query, target, candidate_ids))
        seen_case_ids.add(case_id)
    return cases


def evaluate_rankings(
    cases: list[BenchmarkCase],
    rankings: dict[str, list[str]],
) -> dict[str, Any]:
    ranks: dict[str, int] = {}
    for case in cases:
        ranking = rankings.get(case.case_id)
        if ranking is None or len(ranking) != len(case.candidate_ids):
            raise ValueError(f"ranking for {case.case_id} is not a candidate permutation")
        if set(ranking) != set(case.candidate_ids) or len(ranking) != len(set(ranking)):
            raise ValueError(f"ranking for {case.case_id} is not a candidate permutation")
        ranks[case.case_id] = ranking.index(case.target_parent_asin) + 1
    reciprocal_ranks = [1.0 / rank for rank in ranks.values()]
    count = len(cases)
    return {
        "case_count": count,
        "hit_rate_at_1": sum(rank <= 1 for rank in ranks.values()) / count,
        "hit_rate_at_3": sum(rank <= 3 for rank in ranks.values()) / count,
        "hit_rate_at_10": sum(rank <= 10 for rank in ranks.values()) / count,
        "mrr": statistics.fmean(reciprocal_ranks),
        "ranks": ranks,
    }


def rank_cases(
    cases: list[BenchmarkCase],
    documents: dict[str, str],
    scorer: ScoreFunction,
) -> dict[str, Any]:
    rankings: dict[str, list[str]] = {}
    case_seconds: dict[str, float] = {}
    for case in cases:
        texts = [documents[candidate_id] for candidate_id in case.candidate_ids]
        started = time.perf_counter()
        scores = scorer(case.query, texts)
        case_seconds[case.case_id] = time.perf_counter() - started
        rankings[case.case_id] = rank_by_scores(case.candidate_ids, scores)
    total_seconds = sum(case_seconds.values())
    return {
        "metrics": evaluate_rankings(cases, rankings),
        "rankings": rankings,
        "ranking_seconds": total_seconds,
        "mean_case_milliseconds": 1000.0 * total_seconds / len(cases),
        "case_seconds": case_seconds,
    }


def _load_cross_encoder_scorer(
    model_reference: str,
    *,
    local_files_only: bool,
    batch_size: int,
    max_length: int,
) -> tuple[ScoreFunction, float]:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        model_reference,
        local_files_only=local_files_only,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        model_reference,
        local_files_only=local_files_only,
    )
    model.to("cpu")
    model.eval()
    load_seconds = time.perf_counter() - started

    def score(query: str, texts: list[str]) -> list[float]:
        scores: list[float] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            encoded = tokenizer(
                [query] * len(batch),
                batch,
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            with torch.inference_mode():
                logits = model(**encoded).logits.reshape(-1)
            scores.extend(float(value) for value in logits.detach().cpu().tolist())
        return scores

    return score, load_seconds


def _dense_embeddings(
    tokenizer: Any,
    model: Any,
    texts: list[str],
    *,
    batch_size: int,
    max_length: int,
) -> Any:
    import torch
    import torch.nn.functional as functional

    embeddings = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        encoded = tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt",
        )
        with torch.inference_mode():
            token_embeddings = model(**encoded).last_hidden_state
        mask = encoded["attention_mask"].unsqueeze(-1).expand(token_embeddings.size()).float()
        pooled = (token_embeddings * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        embeddings.append(functional.normalize(pooled, p=2, dim=1).cpu())
    return torch.cat(embeddings, dim=0)


def _load_dense_scorer(
    model_reference: str,
    documents: dict[str, str],
    *,
    local_files_only: bool,
    batch_size: int,
    max_length: int,
) -> tuple[ScoreFunction, float, float]:
    import torch
    from transformers import AutoModel, AutoTokenizer

    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        model_reference,
        local_files_only=local_files_only,
    )
    model = AutoModel.from_pretrained(
        model_reference,
        local_files_only=local_files_only,
    )
    model.to("cpu")
    model.eval()
    load_seconds = time.perf_counter() - started

    unique_texts = list(dict.fromkeys(documents.values()))
    index_started = time.perf_counter()
    indexed_embeddings = _dense_embeddings(
        tokenizer,
        model,
        unique_texts,
        batch_size=batch_size,
        max_length=max_length,
    )
    index_seconds = time.perf_counter() - index_started
    embedding_by_text = {
        text: indexed_embeddings[index] for index, text in enumerate(unique_texts)
    }

    def score(query: str, texts: list[str]) -> list[float]:
        query_embedding = _dense_embeddings(
            tokenizer,
            model,
            [query],
            batch_size=1,
            max_length=max_length,
        )[0]
        document_embeddings = torch.stack([embedding_by_text[text] for text in texts])
        return [
            float(value)
            for value in torch.mv(document_embeddings, query_embedding).tolist()
        ]

    return score, load_seconds, index_seconds


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--public-set", type=Path, default=Path("data/public_set.jsonl"))
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.jsonl"))
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--models",
        nargs="+",
        choices=tuple(MODEL_REFERENCES),
        default=list(MODEL_REFERENCES),
    )
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=256)
    args = parser.parse_args()
    cases = load_benchmark_cases(args.cases, args.public_set)
    documents = load_candidate_documents(args.catalog, cases)
    baseline_rankings = {
        case.case_id: list(case.candidate_ids) for case in cases
    }
    results: dict[str, Any] = {
        "benchmark": {
            "case_count": len(cases),
            "candidates_per_case": sorted({len(case.candidate_ids) for case in cases}),
            "cases_sha256": _sha256(args.cases),
            "public_target_overlap": False,
            "catalog": str(args.catalog),
            "max_length": args.max_length,
            "batch_size": args.batch_size,
        },
        "models": {
            "deterministic-candidate-order": {
                "metrics": evaluate_rankings(cases, baseline_rankings),
                "rankings": baseline_rankings,
                "load_seconds": 0.0,
                "ranking_seconds": 0.0,
                "mean_case_milliseconds": 0.0,
            }
        },
    }

    for model_key in args.models:
        model_reference = MODEL_REFERENCES[model_key]
        if model_key == "dense-minilm-l12":
            scorer, load_seconds, index_seconds = _load_dense_scorer(
                model_reference,
                documents,
                local_files_only=not args.allow_download,
                batch_size=max(1, args.batch_size),
                max_length=max(16, args.max_length),
            )
        else:
            scorer, load_seconds = _load_cross_encoder_scorer(
                model_reference,
                local_files_only=not args.allow_download,
                batch_size=max(1, args.batch_size),
                max_length=max(16, args.max_length),
            )
            index_seconds = 0.0
        model_result = rank_cases(cases, documents, scorer)
        model_result.update(
            {
                "model_reference": model_reference,
                "load_seconds": load_seconds,
                "document_index_seconds": index_seconds,
            }
        )
        results["models"][model_key] = model_result
        del scorer
        gc.collect()

    rendered = json.dumps(results, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
