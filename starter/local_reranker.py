from __future__ import annotations

import math
import os
from collections.abc import Callable
from pathlib import Path


ScoreFunction = Callable[[str, list[str]], list[float]]


class LocalCrossEncoderReranker:
    """Optional local text-pair ranker loaded only when explicitly configured."""

    def __init__(
        self,
        model_name_or_path: str | Path,
        *,
        batch_size: int = 16,
        max_length: int = 256,
        local_files_only: bool = True,
        scorer: ScoreFunction | None = None,
    ) -> None:
        self.model_name_or_path = str(model_name_or_path)
        self.batch_size = max(1, int(batch_size))
        self.max_length = max(16, int(max_length))
        self._scorer = scorer or self._load_transformer_scorer(local_files_only)

    @classmethod
    def from_environment(
        cls,
        project_root: str | Path,
    ) -> LocalCrossEncoderReranker | None:
        configured = os.environ.get("LOCAL_RERANKER_MODEL", "").strip()
        if not configured:
            return None

        root = Path(project_root)
        configured_path = Path(configured).expanduser()
        if not configured_path.is_absolute() and (root / configured_path).exists():
            configured_path = (root / configured_path).resolve()
        model_reference = str(configured_path) if configured_path.exists() else configured
        allow_download = os.environ.get(
            "LOCAL_RERANKER_ALLOW_DOWNLOAD",
            "0",
        ).casefold() in {"1", "true", "yes", "on"}
        batch_size = int(os.environ.get("LOCAL_RERANKER_BATCH_SIZE", "16"))
        max_length = int(os.environ.get("LOCAL_RERANKER_MAX_LENGTH", "256"))
        return cls(
            model_reference,
            batch_size=batch_size,
            max_length=max_length,
            local_files_only=not allow_download,
        )

    def _load_transformer_scorer(self, local_files_only: bool) -> ScoreFunction:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            self.model_name_or_path,
            local_files_only=local_files_only,
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name_or_path,
            local_files_only=local_files_only,
        )
        model.to("cpu")
        model.eval()

        def score(query: str, texts: list[str]) -> list[float]:
            scores: list[float] = []
            for start in range(0, len(texts), self.batch_size):
                batch = texts[start : start + self.batch_size]
                encoded = tokenizer(
                    [query] * len(batch),
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )
                with torch.inference_mode():
                    logits = model(**encoded).logits.reshape(-1)
                scores.extend(float(value) for value in logits.detach().cpu().tolist())
            return scores

        return score

    def score(self, query: str, documents: list[tuple[str, str]]) -> list[float]:
        """Return one raw cross-encoder logit per input document."""
        if not documents:
            return []
        texts = [text for _, text in documents]
        scores = [float(score) for score in self._scorer(query, texts)]
        if len(scores) != len(documents):
            raise ValueError("local reranker must return one score per document")
        if any(not math.isfinite(score) for score in scores):
            raise ValueError("local reranker scores must be finite")
        return scores

    def rank(self, query: str, documents: list[tuple[str, str]]) -> list[str]:
        scores = self.score(query, documents)
        ranked = sorted(
            zip(documents, scores, strict=True),
            key=lambda item: -item[1],
        )
        return [parent_asin for ((parent_asin, _), _) in ranked]
