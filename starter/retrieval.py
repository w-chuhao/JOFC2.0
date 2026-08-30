from __future__ import annotations

from collections import Counter
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "please",
    "some",
    "that",
    "the",
    "this",
    "to",
    "want",
    "with",
    "would",
    "you",
    "looking",
}

ATTRIBUTE_WEIGHTS = {
    "category": 6.0,
    "material": 4.0,
    "color": 3.0,
    "size": 2.5,
    "style": 2.0,
    "brand": 3.0,
    "feature": 2.5,
    "use_case": 2.0,
}
SOFT_CONSTRAINT_MULTIPLIER = 0.4
ALIASES = {
    "parka": ("jacket",),
    "jacket": ("parka",),
    "button down": ("shirt",),
    "bike shorts": ("shorts",),
    "handbag": ("purse",),
    "purse": ("handbag",),
    "footwear": ("shoes",),
}
STAT_CATEGORY_TERMS = (
    "earrings", "necklaces", "bracelets", "rings", "watches", "shoes", "boots",
    "sandals", "sneakers", "dress", "dresses", "shirt", "shirts", "jacket",
    "jackets", "jeans", "pants", "handbag", "backpack", "belt", "scarf",
)
STAT_COLOR_TERMS = (
    "black", "white", "blue", "red", "pink", "green", "brown", "gray",
    "purple", "yellow", "orange", "gold", "silver", "beige", "navy",
)
STAT_STYLE_TERMS = (
    "casual", "formal", "vintage", "classic", "modern", "sporty",
    "minimalist", "slim", "oversized",
)
STAT_USE_CASE_TERMS = (
    "running", "hiking", "walking", "workout", "gym", "winter", "outdoor",
    "travel", "wedding", "swimming",
)
STAT_MATERIAL_TERMS = (
    "leather", "stainless steel", "sterling silver", "silver", "gold", "cotton",
    "wool", "silk", "denim", "suede", "nylon", "polyester", "rubber", "plastic",
)
STAT_FEATURE_TERMS = (
    "comfortable", "lightweight", "waterproof", "durable", "stretch", "soft",
    "breathable", "cushioned", "warm", "hypoallergenic", "adjustable",
)
STAT_SIZE_TERMS = (
    "small", "medium", "large", "wide", "narrow", "slim", "plus size",
)
RATING_WEIGHT = 0.002
MISSING_ATTRIBUTE_PENALTIES = {
    "category": 4.0,
    "material": 1.0,
    "color": 0.8,
    "size": 0.5,
    "style": 0.4,
    "brand": 1.0,
    "feature": 0.2,
    "use_case": 0.3,
}
EXACT_FEATURE_PHRASE_BONUS = 0.75
RRF_K = 60.0
GENERIC_FEATURE_PHRASE_TERMS = frozenset(
    {
        "all",
        "and",
        "cotton",
        "color",
        "colors",
        "fabric",
        "hand",
        "imported",
        "leather",
        "machine",
        "made",
        "nylon",
        "polyester",
        "rayon",
        "solid",
        "spandex",
        "usa",
        "wash",
    }
)


@dataclass(frozen=True, slots=True)
class RetrievalPolicy:
    strategy: str
    combined_limit: int
    constraint_limit_multiplier: float
    popularity_weight: float


RETRIEVAL_POLICIES = {
    "buying": RetrievalPolicy(
        strategy="filter_first",
        combined_limit=800,
        constraint_limit_multiplier=1.0,
        popularity_weight=0.02,
    ),
    "browsing": RetrievalPolicy(
        strategy="discovery",
        combined_limit=800,
        constraint_limit_multiplier=1.0,
        popularity_weight=0.02,
    ),
}


class SemanticReranker(Protocol):
    def rank(self, query: str, documents: list[tuple[str, str]]) -> list[str]: ...


def _text(value: object) -> str:
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


def _token_text(text: str) -> str:
    return " " + " ".join(_terms(text)) + " "


def _price(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


@dataclass(slots=True)
class ProductDocument:
    parent_asin: str
    semantic_text: str
    full_tokens: str
    category_tokens: str
    brand_tokens: str
    attribute_tokens: dict[str, str]
    price: float | None
    brand: str
    average_rating: float
    rating_number: int


@dataclass(frozen=True)
class SearchResult:
    """Ranked catalog IDs plus attribute frequencies in the best candidates."""

    recommendation_ids: list[str]
    candidate_attribute_stats: dict[str, dict[str, int]]
    diagnostics: dict[str, object]


class CatalogSearch:
    """In-memory multi-route BM25 retrieval with transparent constraint reranking."""

    def __init__(
        self,
        catalog_path: str | Path,
        *,
        semantic_reranker: SemanticReranker | None = None,
        semantic_weight: float = 0.35,
        semantic_candidate_limit: int = 20,
        semantic_min_specific_constraints: int = 2,
    ) -> None:
        self.catalog_path = Path(catalog_path)
        self.semantic_reranker = semantic_reranker
        self.semantic_weight = max(0.0, float(semantic_weight))
        self.semantic_candidate_limit = max(1, int(semantic_candidate_limit))
        self.semantic_min_specific_constraints = max(
            1,
            int(semantic_min_specific_constraints),
        )
        self.connection = sqlite3.connect(":memory:")
        self.products: dict[str, ProductDocument] = {}
        self._build_index()

    def _build_index(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "CREATE VIRTUAL TABLE products USING fts5("
            "parent_asin UNINDEXED, title, categories, features, details, store, description, "
            "tokenize='unicode61 remove_diacritics 2')"
        )
        batch: list[tuple[str, str, str, str, str, str, str]] = []
        with self.catalog_path.open(encoding="utf-8") as handle:
            for line in handle:
                product = json.loads(line)
                parent_asin = str(product["parent_asin"])
                title = _text(product.get("title"))
                categories = _text(product.get("categories"))
                features = _text(product.get("features"))
                details = _text(product.get("details"))
                store = _text(product.get("store"))
                description = _text(product.get("description"))
                full_text = " ".join(
                    (title, categories, features, details, store, description)
                ).strip()
                structured_text = " ".join(
                    (title, features, details, description)
                ).strip()
                contextual_text = " ".join(
                    (title, categories, features, details, description)
                ).strip()
                self.products[parent_asin] = ProductDocument(
                    parent_asin=parent_asin,
                    semantic_text=(
                        full_text[:4000] if self.semantic_reranker is not None else ""
                    ),
                    full_tokens=_token_text(full_text),
                    category_tokens=_token_text(f"{title} {categories}"),
                    brand_tokens=_token_text(f"{store} {title}"),
                    attribute_tokens={
                        "material": _token_text(structured_text),
                        "color": _token_text(structured_text),
                        "size": _token_text(structured_text),
                        "style": _token_text(contextual_text),
                        "feature": _token_text(structured_text),
                        "use_case": _token_text(contextual_text),
                    },
                    price=_price(product.get("price")),
                    brand=store.strip(),
                    average_rating=_price(product.get("average_rating")) or 0.0,
                    rating_number=int(_price(product.get("rating_number")) or 0),
                )
                batch.append(
                    (
                        parent_asin,
                        title,
                        categories,
                        features,
                        details,
                        store,
                        description,
                    )
                )
                if len(batch) >= 1000:
                    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
                    batch.clear()
        if batch:
            cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
        self.connection.commit()

    @staticmethod
    def _retrieval_policy(route: str) -> RetrievalPolicy:
        try:
            return RETRIEVAL_POLICIES[route]
        except KeyError as error:
            raise ValueError(f"unsupported retrieval route: {route}") from error

    def _bm25_route(self, query: str, limit: int) -> list[str]:
        unique_terms = list(dict.fromkeys(_terms(query)))[:40]
        expression = " OR ".join(f'"{term}"' for term in unique_terms)
        if not expression:
            return []
        rows = self.connection.execute(
            "SELECT parent_asin FROM products WHERE products MATCH ? "
            "ORDER BY bm25(products, 0.0, 6.0, 4.0, 2.5, 2.5, 1.5, 1.0) LIMIT ?",
            (expression, limit),
        ).fetchall()
        return [str(row[0]) for row in rows]

    @staticmethod
    def _constraint_text(constraints: dict, key: str) -> str:
        value = constraints.get(key)
        return "" if value is None else str(value).strip()

    @staticmethod
    def _expand_aliases(text: str) -> str:
        expanded = [text]
        lowered = text.casefold()
        for alias, replacements in ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", lowered):
                expanded.extend(replacements)
        return " ".join(expanded)

    def _candidate_scores(
        self,
        query: str,
        constraints: dict,
        priorities: dict[str, str],
        *,
        route: str = "browsing",
    ) -> dict[str, float]:
        policy = self._retrieval_policy(route)
        constraint_values = [
            self._constraint_text(constraints, key)
            for key in ATTRIBUTE_WEIGHTS
            if self._constraint_text(constraints, key)
        ]
        combined_query = self._expand_aliases(" ".join((query, *constraint_values)).strip() or query)
        routes: list[tuple[str, float, int]] = [
            (combined_query, 2.0, policy.combined_limit)
        ]
        route_settings = {
            "category": (3.0, 500),
            "material": (1.8, 400),
            "color": (1.4, 300),
            "size": (1.2, 300),
            "style": (1.2, 300),
            "brand": (1.5, 300),
            "feature": (1.5, 500),
            "use_case": (1.2, 300),
        }
        for key, (weight, limit) in route_settings.items():
            value = self._constraint_text(constraints, key)
            if value:
                routes.append(
                    (
                        self._expand_aliases(value),
                        weight,
                        int(limit * policy.constraint_limit_multiplier),
                    )
                )

        scores: dict[str, float] = {}
        seen_queries: set[str] = set()
        for route_query, route_weight, limit in routes:
            normalized_query = " ".join(dict.fromkeys(_terms(route_query)))
            if not normalized_query or normalized_query in seen_queries:
                continue
            seen_queries.add(normalized_query)
            for rank, parent_asin in enumerate(
                self._bm25_route(route_query, limit),
                start=1,
            ):
                scores[parent_asin] = scores.get(parent_asin, 0.0) + (
                    route_weight / (RRF_K + rank)
                )
        return scores

    def _guarded_required_filter(
        self,
        candidate_ids: list[str],
        constraints: dict,
        priorities: dict[str, str],
        top_k: int,
        route: str,
    ) -> tuple[list[str], list[str]]:
        """Filter Buying candidates only when enough exact choices remain."""
        if route != "buying":
            return candidate_ids, []

        required_attributes = [
            attribute
            for attribute in ATTRIBUTE_WEIGHTS
            if attribute != "category"
            and constraints.get(attribute) is not None
            and priorities.get(attribute) == "required"
        ]
        if not required_attributes:
            return candidate_ids, []

        matches = [
            parent_asin
            for parent_asin in candidate_ids
            if all(
                self._attribute_coverage(
                    self.products[parent_asin],
                    attribute,
                    constraints[attribute],
                )
                >= 0.5
                for attribute in required_attributes
            )
        ]
        if len(matches) < top_k:
            return candidate_ids, []
        return matches, required_attributes

    @staticmethod
    def _attribute_haystack(product: ProductDocument, attribute: str) -> str:
        if attribute == "category":
            return product.category_tokens
        if attribute == "brand":
            return product.brand_tokens
        return product.attribute_tokens.get(attribute, product.full_tokens)

    def _attribute_coverage(
        self,
        product: ProductDocument,
        attribute: str,
        value: object,
    ) -> float:
        terms = list(dict.fromkeys(_terms(self._expand_aliases(str(value)))))
        if not terms:
            return 0.0
        haystack = self._attribute_haystack(product, attribute)
        matched = sum(f" {term} " in haystack for term in terms)
        return matched / len(terms)

    @staticmethod
    def _feature_phrases(value: object) -> set[str]:
        """Return distinctive two-to-five-token phrases from a feature clue."""
        phrases: set[str] = set()
        for clause in str(value).split(";"):
            terms = _terms(clause)
            for length in range(2, min(5, len(terms)) + 1):
                for start in range(len(terms) - length + 1):
                    phrase_terms = terms[start : start + length]
                    is_generic = all(
                        term.isdigit() or term in GENERIC_FEATURE_PHRASE_TERMS
                        for term in phrase_terms
                    )
                    if not is_generic:
                        phrases.add(" ".join(phrase_terms))
        return phrases

    def _exact_feature_phrase_bonus(
        self,
        product: ProductDocument,
        constraints: dict,
    ) -> float:
        feature = constraints.get("feature")
        if feature is None:
            return 0.0
        haystack = product.full_tokens
        phrases = self._feature_phrases(feature)
        if any(f" {phrase} " in haystack for phrase in phrases):
            return EXACT_FEATURE_PHRASE_BONUS
        return 0.0

    def _rerank_score(
        self,
        product: ProductDocument,
        retrieval_score: float,
        constraints: dict,
        priorities: dict[str, str],
        exclusions: dict[str, set[str]],
        popularity_weight: float = 0.0,
    ) -> float | None:
        budget = constraints.get("budget")
        if isinstance(budget, (int, float)) and product.price is not None:
            if product.price > float(budget):
                return None
            retrieval_score += 0.5

        score = retrieval_score
        for attribute, weight in ATTRIBUTE_WEIGHTS.items():
            value = constraints.get(attribute)
            if value is None:
                continue
            coverage = self._attribute_coverage(product, attribute, value)
            multiplier = 1.0 if priorities.get(attribute) == "required" else SOFT_CONSTRAINT_MULTIPLIER
            if coverage:
                score += weight * multiplier * coverage
            else:
                score -= MISSING_ATTRIBUTE_PENALTIES[attribute] * multiplier
        for attribute, values in exclusions.items():
            if any(
                self._attribute_coverage(product, attribute, value) >= 0.5
                for value in values
            ):
                return None
        score += self._exact_feature_phrase_bonus(product, constraints)
        score += popularity_weight * math.log1p(max(0, product.rating_number))
        score += RATING_WEIGHT * max(0.0, product.average_rating)
        return score

    @staticmethod
    def _decayed_popularity_weight(
        base_weight: float,
        previously_shown: int,
    ) -> float:
        return base_weight * max(0.0, 1.0 - min(previously_shown, 80) / 80.0)

    @staticmethod
    def _semantic_specific_constraint_count(constraints: dict) -> int:
        return sum(
            constraints.get(attribute) is not None
            for attribute in (*ATTRIBUTE_WEIGHTS, "budget")
            if attribute != "category"
        )

    def _satisfies_all_required_constraints(
        self,
        product: ProductDocument,
        constraints: dict,
        priorities: dict[str, str],
    ) -> bool:
        required = [
            attribute
            for attribute in ATTRIBUTE_WEIGHTS
            if constraints.get(attribute) is not None
            and priorities.get(attribute) == "required"
        ]
        return bool(required) and all(
            self._attribute_coverage(
                product,
                attribute,
                constraints[attribute],
            )
            >= 0.5
            for attribute in required
        )

    def _semantic_rerank(
        self,
        query: str,
        ranked_ids: list[str],
        constraints: dict,
        priorities: dict[str, str],
    ) -> tuple[list[str], bool, int, int, bool]:
        specificity = self._semantic_specific_constraint_count(constraints)
        if (
            self.semantic_reranker is None
            or not ranked_ids
            or specificity < self.semantic_min_specific_constraints
        ):
            return ranked_ids, False, 0, specificity, False

        candidate_ids = ranked_ids[: self.semantic_candidate_limit]
        documents = [
            (parent_asin, self.products[parent_asin].semantic_text)
            for parent_asin in candidate_ids
        ]
        try:
            proposed_order = self.semantic_reranker.rank(query, documents)
        except Exception:
            return ranked_ids, False, 0, specificity, False

        candidate_set = set(candidate_ids)
        semantic_order: list[str] = []
        seen: set[str] = set()
        for parent_asin in proposed_order:
            if parent_asin in candidate_set and parent_asin not in seen:
                seen.add(parent_asin)
                semantic_order.append(parent_asin)
        if not semantic_order:
            return ranked_ids, False, 0, specificity, False
        semantic_order.extend(
            parent_asin for parent_asin in candidate_ids if parent_asin not in seen
        )

        deterministic_rank = {
            parent_asin: rank for rank, parent_asin in enumerate(candidate_ids, start=1)
        }
        semantic_rank = {
            parent_asin: rank for rank, parent_asin in enumerate(semantic_order, start=1)
        }
        protected_first = self._satisfies_all_required_constraints(
            self.products[candidate_ids[0]],
            constraints,
            priorities,
        )
        movable_ids = candidate_ids[1:] if protected_first else candidate_ids
        fused = sorted(
            movable_ids,
            key=lambda parent_asin: (
                -(
                    1.0 / (RRF_K + deterministic_rank[parent_asin])
                    + self.semantic_weight
                    / (RRF_K + semantic_rank[parent_asin])
                ),
                deterministic_rank[parent_asin],
            ),
        )
        fused_ids = (
            ([candidate_ids[0]] if protected_first else [])
            + fused
            + ranked_ids[len(candidate_ids) :]
        )
        return (
            fused_ids,
            True,
            len(candidate_ids),
            specificity,
            protected_first,
        )

    def _candidate_attribute_stats(
        self,
        ranked_ids: list[str],
    ) -> dict[str, dict[str, int]]:
        counters: dict[str, Counter[str]] = {
            "category": Counter[str](),
            "material": Counter[str](),
            "color": Counter[str](),
            "style": Counter[str](),
            "brand": Counter[str](),
            "use_case": Counter[str](),
            "feature": Counter[str](),
            "size": Counter[str](),
            "budget": Counter[str](),
        }
        terms_by_attribute = {
            "category": STAT_CATEGORY_TERMS,
            "material": STAT_MATERIAL_TERMS,
            "color": STAT_COLOR_TERMS,
            "style": STAT_STYLE_TERMS,
            "use_case": STAT_USE_CASE_TERMS,
            "feature": STAT_FEATURE_TERMS,
            "size": STAT_SIZE_TERMS,
        }
        for parent_asin in ranked_ids[:50]:
            product = self.products[parent_asin]
            for attribute, terms in terms_by_attribute.items():
                haystack = self._attribute_haystack(product, attribute)
                for term in terms:
                    if f" {term} " in haystack:
                        counters[attribute][term] += 1
            if product.brand:
                counters["brand"][product.brand.casefold()] += 1
            if product.price is not None:
                bucket = f"under_{int(math.ceil(product.price / 25.0) * 25)}"
                counters["budget"][bucket] += 1
        return {attribute: dict(counter.most_common(10)) for attribute, counter in counters.items()}

    def search(
        self,
        query: str,
        constraints: dict,
        top_k: int,
        *,
        exclude_ids: set[str] | None = None,
        constraint_priorities: dict[str, str] | None = None,
        excluded_constraints: dict[str, set[str]] | None = None,
        route: str = "browsing",
    ) -> SearchResult:
        """Return ranked IDs and statistics using current validated constraints.

        ``exclude_ids`` is used for later conversational turns to expose the
        next-best catalogue items without changing the ranking itself.
        """
        policy = self._retrieval_policy(route)
        limit = max(0, top_k)
        if limit == 0:
            return SearchResult(
                [],
                {},
                {
                    "candidate_count": 0,
                    "route": route,
                    "strategy": policy.strategy,
                    "required_filter_attributes": [],
                },
            )

        priorities = constraint_priorities or {}
        exclusions = excluded_constraints or {}
        excluded = exclude_ids or set()
        popularity_weight = self._decayed_popularity_weight(
            policy.popularity_weight,
            len(excluded),
        )
        candidate_scores = self._candidate_scores(
            query,
            constraints,
            priorities,
            route=route,
        )
        candidate_ids = list(candidate_scores) or list(self.products)
        category = constraints.get("category")
        if category is not None:
            category_matches = [
                parent_asin
                for parent_asin in candidate_ids
                if self._attribute_coverage(
                    self.products[parent_asin],
                    "category",
                    category,
                )
                >= 0.5
            ]
            if len(category_matches) >= limit:
                candidate_ids = category_matches

        candidate_ids, required_filter_attributes = self._guarded_required_filter(
            candidate_ids,
            constraints,
            priorities,
            limit,
            route,
        )

        ranked: list[tuple[float, str]] = []
        for parent_asin in candidate_ids:
            product = self.products[parent_asin]
            score = self._rerank_score(
                product,
                candidate_scores.get(parent_asin, 0.0),
                constraints,
                priorities,
                exclusions,
                popularity_weight,
            )
            if score is not None:
                ranked.append((score, parent_asin))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        ranked_ids = [parent_asin for _, parent_asin in ranked]
        (
            ranked_ids,
            semantic_reranked,
            semantic_candidate_count,
            semantic_specific_constraint_count,
            semantic_protected_first,
        ) = self._semantic_rerank(query, ranked_ids, constraints, priorities)
        return SearchResult(
            recommendation_ids=[
                parent_asin
                for parent_asin in ranked_ids
                if parent_asin not in excluded
            ][:limit],
            candidate_attribute_stats=self._candidate_attribute_stats(ranked_ids),
            diagnostics={
                "candidate_count": len(candidate_ids),
                "ranked_count": len(ranked_ids),
                "route": route,
                "strategy": policy.strategy,
                "popularity_weight": popularity_weight,
                "required_filter_attributes": required_filter_attributes,
                "semantic_reranked": semantic_reranked,
                "semantic_candidate_count": semantic_candidate_count,
                "semantic_specific_constraint_count": (
                    semantic_specific_constraint_count
                ),
                "semantic_protected_first": semantic_protected_first,
                "active_exclusion_count": sum(
                    len(values) for values in exclusions.values()
                ),
            },
        )
