"""Local, constraint-aware catalog retrieval for the shopping agent.

The evaluator-facing agent owns conversation state.  This module only turns a
query and already-validated constraints into real catalog IDs and compact
candidate statistics that a question planner can use.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sqlite3


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "i", "in", "is", "it", "me", "my", "of", "on", "or", "please", "some",
    "that", "the", "this", "to", "want", "with", "would", "you", "looking",
}
CONSTRAINT_KEYS = (
    "category", "material", "color", "size", "style", "brand", "budget",
    "feature", "use_case",
)
MATERIALS = (
    "leather", "stainless steel", "sterling silver", "silver", "gold", "cotton",
    "wool", "silk", "denim", "suede", "nylon", "polyester", "rubber", "plastic",
)
CATEGORY_TERMS = (
    "earrings", "necklaces", "bracelets", "rings", "watches", "shoes", "boots",
    "sandals", "sneakers", "dress", "dresses", "shirt", "shirts", "jacket",
    "jackets", "jeans", "pants", "handbag", "backpack", "belt", "scarf",
)
WEIGHTS = {
    "category": 8.0,
    "material": 6.0,
    "brand": 6.0,
    "color": 3.0,
    "size": 3.0,
    "style": 3.0,
    "feature": 3.0,
    "use_case": 3.0,
}


def _text(value: object) -> str:
    """Flatten JSON catalog values into searchable, human-readable text."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(f"{key} {_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    return str(value)


def _terms(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_RE.findall(text)
        if len(token) > 1 and token.lower() not in STOPWORDS
    ]


def _constraint_text(constraints: dict[str, object]) -> str:
    """Use textual constraints to widen BM25 retrieval before reranking."""
    values = [
        _text(constraints.get(name))
        for name in CONSTRAINT_KEYS
        if name != "budget" and constraints.get(name) not in (None, "")
    ]
    return " ".join(values)


def _contains_phrase(text: str, phrase: str) -> bool:
    """Match a normalized attribute without treating one word as another's suffix."""
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text))


def _number(value: object) -> float | None:
    """Read a catalog price or validated budget without raising on dirty data."""
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"\d+(?:\.\d+)?", _text(value))
    return float(match.group()) if match else None


@dataclass(frozen=True)
class SearchResult:
    """Ranked catalog IDs plus aggregate observations about the candidate pool."""

    recommendation_ids: list[str]
    candidate_attribute_stats: dict[str, dict[str, int]]


class CatalogRetriever:
    """In-memory SQLite FTS5 retriever with transparent constraint reranking."""

    def __init__(self, catalog_path: str | Path = "data/catalog.jsonl") -> None:
        self.catalog_path = Path(catalog_path)
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self._build_index()

    def _build_index(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "CREATE VIRTUAL TABLE products USING fts5("
            "parent_asin UNINDEXED, title, categories, features, details, store, description, price UNINDEXED, "
            "tokenize='unicode61 remove_diacritics 2')"
        )
        batch: list[tuple[str, str, str, str, str, str, str, str]] = []
        with self.catalog_path.open(encoding="utf-8") as handle:
            for line in handle:
                product = json.loads(line)
                batch.append(
                    (
                        str(product["parent_asin"]),
                        _text(product.get("title")),
                        _text(product.get("categories")),
                        _text(product.get("features")),
                        _text(product.get("details")),
                        _text(product.get("store")),
                        _text(product.get("description")),
                        _text(product.get("price")),
                    )
                )
                if len(batch) >= 1000:
                    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)", batch)
                    batch.clear()
        if batch:
            cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)", batch)
        self.connection.commit()

    def search(
        self,
        query: str,
        constraints: dict[str, object] | None,
        top_k: int,
    ) -> SearchResult:
        """Return the best real IDs for a query and optional validated constraints."""
        limit = max(0, top_k)
        if limit == 0:
            return SearchResult([], {"category": {}, "material": {}})

        normalized_constraints = constraints or {}
        combined_text = f"{query} {_constraint_text(normalized_constraints)}"
        unique_terms = list(dict.fromkeys(_terms(combined_text)))[:40]
        pool_size = max(limit * 10, 50)
        rows = self._candidate_rows(unique_terms, pool_size)
        ranked_rows = sorted(
            rows,
            key=lambda row: (-self._score(row, normalized_constraints), row["parent_asin"]),
        )

        recommendation_ids: list[str] = []
        seen_ids: set[str] = set()
        for row in ranked_rows:
            parent_asin = str(row["parent_asin"])
            if parent_asin not in seen_ids:
                recommendation_ids.append(parent_asin)
                seen_ids.add(parent_asin)
            if len(recommendation_ids) == limit:
                break

        return SearchResult(
            recommendation_ids=recommendation_ids,
            candidate_attribute_stats=self._attribute_stats(ranked_rows[:50]),
        )

    def _candidate_rows(self, terms: list[str], pool_size: int) -> list[sqlite3.Row]:
        columns = "parent_asin, title, categories, features, details, store, description, price"
        if not terms:
            return self.connection.execute(
                f"SELECT {columns}, 0.0 AS bm25_rank FROM products LIMIT ?", (pool_size,)
            ).fetchall()

        expression = " OR ".join(f'"{term}"' for term in terms)
        return self.connection.execute(
            f"SELECT {columns}, bm25(products, 0.0, 6.0, 4.0, 2.5, 2.5, 1.5, 1.0) AS bm25_rank "
            "FROM products WHERE products MATCH ? ORDER BY bm25(products, 0.0, 6.0, 4.0, 2.5, 2.5, 1.5, 1.0) "
            "LIMIT ?",
            (expression, pool_size),
        ).fetchall()

    def _score(self, row: sqlite3.Row, constraints: dict[str, object]) -> float:
        """Combine BM25 relevance with transparent boosts and category penalties."""
        score = -float(row["bm25_rank"])
        category_text = str(row["categories"]).casefold()
        corpus = " ".join(str(row[field]) for field in row.keys() if field not in {"parent_asin", "bm25_rank"}).casefold()

        category = _text(constraints.get("category")).casefold().strip()
        if category:
            if _contains_phrase(category_text, category):
                score += WEIGHTS["category"]
            elif self._has_clear_category_conflict(category, category_text):
                score -= WEIGHTS["category"] / 2

        for name, weight in WEIGHTS.items():
            if name == "category":
                continue
            value = _text(constraints.get(name)).casefold().strip()
            if value and _contains_phrase(corpus, value):
                score += weight

        budget = _number(constraints.get("budget"))
        price = _number(row["price"])
        if budget is not None and price is not None:
            score += 3.0 if price <= budget else -3.0
        return score

    @staticmethod
    def _has_clear_category_conflict(category: str, category_text: str) -> bool:
        requested_terms = set(_terms(category))
        observed_terms = {term for term in CATEGORY_TERMS if _contains_phrase(category_text, term)}
        return bool(observed_terms and not requested_terms.intersection(observed_terms))

    @staticmethod
    def _attribute_stats(rows: list[sqlite3.Row]) -> dict[str, dict[str, int]]:
        categories: Counter[str] = Counter()
        materials: Counter[str] = Counter()
        for row in rows:
            category_text = str(row["categories"]).casefold()
            corpus = " ".join(str(row[field]) for field in row.keys() if field not in {"parent_asin", "bm25_rank"}).casefold()
            for category in CATEGORY_TERMS:
                if _contains_phrase(category_text, category):
                    categories[category] += 1
            for material in MATERIALS:
                if _contains_phrase(corpus, material):
                    materials[material] += 1
        return {
            "category": dict(categories.most_common(10)),
            "material": dict(materials.most_common(10)),
        }


def search(query: str, constraints: dict[str, object], top_k: int) -> SearchResult:
    """Convenience implementation of the agreed three-argument team contract.

    Production callers that need a non-default catalog or index reuse should keep
    a ``CatalogRetriever`` instance and call its ``search`` method instead.
    """
    return _default_retriever().search(query, constraints, top_k)


_DEFAULT_RETRIEVER: CatalogRetriever | None = None


def _default_retriever() -> CatalogRetriever:
    global _DEFAULT_RETRIEVER
    if _DEFAULT_RETRIEVER is None:
        _DEFAULT_RETRIEVER = CatalogRetriever()
    return _DEFAULT_RETRIEVER
