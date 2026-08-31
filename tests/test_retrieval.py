from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from starter.retrieval import CatalogSearch


CATALOG_ROWS = [
    {
        "parent_asin": "SHOE_IN_BUDGET",
        "title": "Black leather walking shoes",
        "features": ["comfortable cushioned sole"],
        "details": {"material": "leather", "color": "black"},
        "description": ["Everyday walking footwear"],
        "categories": ["Clothing", "Shoes"],
        "store": "Shoe Store",
        "average_rating": 4.5,
        "rating_number": 100,
        "price": 80.0,
    },
    {
        "parent_asin": "SHOE_OVER_BUDGET",
        "title": "Black leather formal shoes",
        "features": ["premium leather"],
        "details": {"material": "leather", "color": "black"},
        "description": ["Formal footwear"],
        "categories": ["Clothing", "Shoes"],
        "store": "Luxury Shoe Store",
        "average_rating": 4.8,
        "rating_number": 500,
        "price": 180.0,
    },
    {
        "parent_asin": "BAG_BLACK",
        "title": "Black leather handbag",
        "features": ["zipper closure"],
        "details": {"material": "leather", "color": "black"},
        "description": ["Shoulder bag"],
        "categories": ["Clothing", "Handbags"],
        "store": "Bag Store",
        "average_rating": 4.3,
        "rating_number": 60,
        "price": 60.0,
    },
    {
        "parent_asin": "SHOE_CANVAS",
        "title": "Black canvas walking shoes",
        "features": ["comfortable cushioned sole"],
        "details": {"material": "canvas", "color": "black"},
        "description": ["Everyday walking footwear"],
        "categories": ["Clothing", "Shoes"],
        "store": "Shoe Store",
        "average_rating": 4.4,
        "rating_number": 90,
        "price": 75.0,
    },
    {
        "parent_asin": "SHOE_CANVAS_LEATHER_STORE",
        "title": "Black canvas walking shoes",
        "features": ["comfortable cushioned sole"],
        "details": {"material": "canvas", "color": "black"},
        "description": ["Everyday walking footwear"],
        "categories": ["Clothing", "Shoes"],
        "store": "Leather Goods Outlet",
        "average_rating": 4.4,
        "rating_number": 90,
        "price": 75.0,
    },
    {
        "parent_asin": "FEATURE_PHRASE_EXACT",
        "title": "Everyday walking shoes",
        "features": ["All Motion Comfort technology", "Machine Wash"],
        "details": {},
        "description": [],
        "categories": ["Clothing", "Shoes"],
        "store": "Comfort Store",
        "average_rating": 4.5,
        "rating_number": 100,
        "price": 80.0,
    },
    {
        "parent_asin": "FEATURE_TOKEN_OVERLAP",
        "title": "Everyday walking shoes",
        "features": ["Comfort lining with motion support all day"],
        "details": {},
        "description": [],
        "categories": ["Clothing", "Shoes"],
        "store": "Comfort Store",
        "average_rating": 4.5,
        "rating_number": 100,
        "price": 80.0,
    },
    {
        "parent_asin": "AAA_TIE_LOW",
        "title": "Green cotton casual shirt",
        "features": ["soft"],
        "details": {"material": "cotton", "color": "green"},
        "description": ["Everyday shirt"],
        "categories": ["Clothing", "Shirts"],
        "store": "Tie Brand",
        "average_rating": 3.0,
        "rating_number": 2,
        "price": 30.0,
    },
    {
        "parent_asin": "ZZZ_TIE_POPULAR",
        "title": "Green cotton casual shirt",
        "features": ["soft"],
        "details": {"material": "cotton", "color": "green"},
        "description": ["Everyday shirt"],
        "categories": ["Clothing", "Shirts"],
        "store": "Tie Brand",
        "average_rating": 4.9,
        "rating_number": 5000,
        "price": 30.0,
    },
    {
        "parent_asin": "MMM_TIE_MIDDLE",
        "title": "Green cotton casual shirt",
        "features": ["soft"],
        "details": {"material": "cotton", "color": "green"},
        "description": ["Everyday shirt"],
        "categories": ["Clothing", "Shirts"],
        "store": "Tie Brand",
        "average_rating": 4.0,
        "rating_number": 100,
        "price": 30.0,
    },
    *[
        {
            "parent_asin": f"STEEL_HOOP_{number:02d}",
            "title": f"Lightweight stainless steel hoop earrings {number}",
            "features": ["hypoallergenic hoops"],
            "details": {"material": "stainless steel", "style": "hoop"},
            "description": ["Lightweight everyday earrings"],
            "categories": ["Jewelry", "Earrings"],
            "store": "Jewelry Store",
            "average_rating": 4.5,
            "rating_number": 100,
            "price": 20.0 + number,
        }
        for number in range(1, 11)
    ],
]


def constraints(**updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "category": None,
        "material": None,
        "color": None,
        "size": None,
        "style": None,
        "brand": None,
        "budget": None,
        "feature": None,
        "use_case": None,
    }
    values.update(updates)
    return values


class FakeSemanticReranker:
    def __init__(self, ranking: list[str] | None = None, *, error: Exception | None = None):
        self.ranking = ranking or []
        self.error = error
        self.calls: list[tuple[str, list[tuple[str, str]]]] = []

    def rank(self, query: str, documents: list[tuple[str, str]]) -> list[str]:
        self.calls.append((query, documents))
        if self.error is not None:
            raise self.error
        return list(self.ranking)


class FakeScoredSemanticReranker:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.calls: list[tuple[str, list[tuple[str, str]]]] = []

    def score(self, query: str, documents: list[tuple[str, str]]) -> list[float]:
        self.calls.append((query, documents))
        return list(self.scores)


class CatalogSearchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        catalog_path = Path(self.temporary_directory.name) / "catalog.jsonl"
        catalog_path.write_text(
            "".join(json.dumps(row) + "\n" for row in CATALOG_ROWS),
            encoding="utf-8",
        )
        self.search = CatalogSearch(catalog_path)

    def tearDown(self) -> None:
        self.search.connection.close()
        self.temporary_directory.cleanup()

    def test_semantic_defaults_match_guarded_evaluation_configuration(self) -> None:
        self.assertEqual(self.search.semantic_weight, 0.35)
        self.assertEqual(self.search.semantic_candidate_limit, 20)
        self.assertEqual(self.search.semantic_min_specific_constraints, 2)
        self.assertEqual(self.search.semantic_min_score_gap, 0.5)

    def test_ranking_diagnostics_are_opt_in(self) -> None:
        result = self.search.search(
            query="black leather shoes",
            constraints=constraints(category="shoes", material="leather"),
            top_k=3,
        )

        self.assertNotIn("ranking_candidates", result.diagnostics)

    def test_ranking_diagnostics_explain_returned_candidate_scores(self) -> None:
        expected = self.search.search(
            query="black leather shoes",
            constraints=constraints(category="shoes", material="leather"),
            top_k=3,
        ).recommendation_ids
        self.search.enable_ranking_diagnostics = True

        result = self.search.search(
            query="black leather shoes",
            constraints=constraints(category="shoes", material="leather"),
            top_k=3,
        )

        self.assertEqual(result.recommendation_ids, expected)
        candidates = result.diagnostics["ranking_candidates"]
        self.assertEqual(
            [item["parent_asin"] for item in candidates],
            result.recommendation_ids,
        )
        first = candidates[0]
        self.assertEqual(first["returned_rank"], 1)
        self.assertTrue(first["route_signals"])
        self.assertIn("bm25_score", first["route_signals"][0])
        self.assertAlmostEqual(
            first["retrieval_score"],
            sum(item["rrf_contribution"] for item in first["route_signals"]),
        )
        attribute_total = sum(
            item["contribution"]
            for items in first["attribute_contributions"].values()
            for item in items
        )
        explained_total = (
            first["retrieval_score"]
            + first["budget_adjustment"]
            + attribute_total
            + first["feature_phrase_bonus"]
            + first["popularity_contribution"]
            + first["rating_contribution"]
        )
        self.assertAlmostEqual(first["total_score"], explained_total)

    def test_category_constraint_ranks_matching_product_above_other_category(self) -> None:
        results = self.search.search(
            query="black leather",
            constraints=constraints(category="shoes", color="black", material="leather"),
            top_k=10,
        )

        ids = results.recommendation_ids
        first_shoe_rank = min(
            ids.index("SHOE_IN_BUDGET"),
            ids.index("SHOE_OVER_BUDGET"),
        )
        self.assertLess(first_shoe_rank, ids.index("BAG_BLACK"))

    def test_budget_constraint_excludes_known_over_budget_product(self) -> None:
        results = self.search.search(
            query="black leather shoes",
            constraints=constraints(category="shoes", budget=100.0),
            top_k=10,
        )

        self.assertIn("SHOE_IN_BUDGET", results.recommendation_ids)
        self.assertNotIn("SHOE_OVER_BUDGET", results.recommendation_ids)

    def test_search_returns_unique_catalog_identifiers(self) -> None:
        results = self.search.search(
            query="black leather",
            constraints=constraints(material="leather", color="black"),
            top_k=2,
        )

        ids = results.recommendation_ids
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(set(ids).issubset({row["parent_asin"] for row in CATALOG_ROWS}))

    def test_specific_earring_query_returns_ten_valid_unique_ids(self) -> None:
        result = self.search.search(
            query="lightweight stainless steel hoop earrings",
            constraints=constraints(),
            top_k=10,
        )

        ids = result.recommendation_ids
        self.assertEqual(len(ids), 10)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(set(ids).issubset({row["parent_asin"] for row in CATALOG_ROWS}))
        self.assertTrue(all(parent_asin.startswith("STEEL_HOOP_") for parent_asin in ids))

    def test_material_constraint_ranks_leather_above_canvas(self) -> None:
        result = self.search.search(
            query="black walking shoes",
            constraints=constraints(category="shoes", material="leather", color="black"),
            top_k=10,
        )

        ids = result.recommendation_ids
        first_leather_rank = min(
            ids.index("SHOE_IN_BUDGET"),
            ids.index("SHOE_OVER_BUDGET"),
        )
        self.assertLess(first_leather_rank, ids.index("SHOE_CANVAS"))

    def test_search_returns_candidate_attribute_statistics(self) -> None:
        result = self.search.search(
            query="black leather shoes",
            constraints=constraints(category="shoes"),
            top_k=10,
        )

        self.assertIn("category", result.candidate_attribute_stats)
        self.assertIn("material", result.candidate_attribute_stats)
        self.assertGreater(result.candidate_attribute_stats["category"].get("shoes", 0), 0)
        self.assertGreater(result.candidate_attribute_stats["material"].get("leather", 0), 0)

    def test_candidate_statistics_include_color_and_brand(self) -> None:
        result = self.search.search(
            query="green cotton shirt",
            constraints=constraints(category="shirts"),
            top_k=10,
        )

        self.assertGreater(result.candidate_attribute_stats["color"].get("green", 0), 0)
        self.assertGreater(result.candidate_attribute_stats["brand"].get("tie brand", 0), 0)

    def test_popularity_breaks_an_identical_text_tie(self) -> None:
        result = self.search.search(
            query="green cotton casual shirt",
            constraints=constraints(category="shirts"),
            top_k=10,
        )

        ids = result.recommendation_ids
        self.assertLess(ids.index("ZZZ_TIE_POPULAR"), ids.index("AAA_TIE_LOW"))

    def test_popularity_prior_decays_with_cross_turn_exploration(self) -> None:
        self.assertGreater(
            self.search._decayed_popularity_weight(0.02, 0),
            self.search._decayed_popularity_weight(0.02, 40),
        )
        self.assertEqual(self.search._decayed_popularity_weight(0.02, 80), 0.0)

    def test_empty_query_returns_valid_catalog_ids(self) -> None:
        result = self.search.search("", constraints(), 10)

        self.assertEqual(len(result.recommendation_ids), min(10, len(CATALOG_ROWS)))
        self.assertTrue(
            set(result.recommendation_ids).issubset(
                {row["parent_asin"] for row in CATALOG_ROWS}
            )
        )

    def test_excluded_ids_are_skipped_before_selecting_top_k(self) -> None:
        first = self.search.search(
            query="black leather shoes",
            constraints=constraints(category="shoes"),
            top_k=1,
        )
        second = self.search.search(
            query="black leather shoes",
            constraints=constraints(category="shoes"),
            top_k=1,
            exclude_ids=set(first.recommendation_ids),
        )

        self.assertEqual(len(second.recommendation_ids), 1)
        self.assertNotEqual(first.recommendation_ids, second.recommendation_ids)

    def test_negative_constraint_removes_conflicting_products(self) -> None:
        result = self.search.search(
            query="black leather shoes",
            constraints=constraints(category="shoes"),
            top_k=10,
            excluded_constraints={"color": {"black"}},
        )

        self.assertNotIn("SHOE_IN_BUDGET", result.recommendation_ids)
        self.assertNotIn("SHOE_OVER_BUDGET", result.recommendation_ids)
        self.assertNotIn("SHOE_CANVAS", result.recommendation_ids)

    def test_alias_route_recovers_footwear_as_shoes(self) -> None:
        result = self.search.search(
            query="footwear",
            constraints=constraints(),
            top_k=3,
        )

        self.assertTrue(
            any(parent_asin.startswith("SHOE_") for parent_asin in result.recommendation_ids)
        )

    def test_required_constraint_has_more_ranking_weight_than_preferred(self) -> None:
        required = self.search.search(
            query="black walking shoes",
            constraints=constraints(category="shoes", material="leather"),
            top_k=10,
            constraint_priorities={"category": "required", "material": "required"},
            route="buying",
        )
        preferred = self.search.search(
            query="black walking shoes",
            constraints=constraints(category="shoes", material="leather"),
            top_k=10,
            constraint_priorities={"category": "required", "material": "preferred"},
            route="browsing",
        )

        self.assertLess(
            required.recommendation_ids.index("SHOE_IN_BUDGET"),
            required.recommendation_ids.index("SHOE_CANVAS"),
        )
        self.assertLessEqual(
            required.diagnostics["candidate_count"], preferred.diagnostics["candidate_count"]
        )

    def test_buying_route_reports_guarded_required_constraint_filtering(self) -> None:
        result = self.search.search(
            query="black walking shoes",
            constraints=constraints(category="shoes", material="leather"),
            top_k=2,
            constraint_priorities={"category": "required", "material": "required"},
            route="buying",
        )

        self.assertEqual(result.diagnostics["strategy"], "filter_first")
        self.assertEqual(result.diagnostics["popularity_weight"], 0.02)
        self.assertEqual(result.diagnostics["required_filter_attributes"], ["material"])
        self.assertNotIn("SHOE_CANVAS", result.recommendation_ids)

    def test_browsing_route_reports_discovery_strategy(self) -> None:
        result = self.search.search(
            query="black walking shoes",
            constraints=constraints(category="shoes", material="leather"),
            top_k=2,
            constraint_priorities={"category": "required", "material": "preferred"},
            route="browsing",
        )

        self.assertEqual(result.diagnostics["strategy"], "discovery")
        self.assertEqual(result.diagnostics["popularity_weight"], 0.02)
        self.assertEqual(result.diagnostics["required_filter_attributes"], [])

    def test_attribute_coverage_does_not_treat_store_name_as_material(self) -> None:
        product = self.search.products["SHOE_CANVAS_LEATHER_STORE"]

        coverage = self.search._attribute_coverage(product, "material", "leather")

        self.assertEqual(coverage, 0.0)

    def test_unknown_route_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported retrieval route"):
            self.search.search(
                query="black walking shoes",
                constraints=constraints(category="shoes"),
                top_k=2,
                route="semantic-magic",
            )

    def test_semantic_reranker_skips_broad_category_only_browsing(self) -> None:
        reranker = FakeSemanticReranker(["SHOE_CANVAS"])
        semantic_search = CatalogSearch(
            self.search.catalog_path,
            semantic_reranker=reranker,
            semantic_weight=10.0,
        )
        self.addCleanup(semantic_search.connection.close)

        result = semantic_search.search(
            query="shoes",
            constraints=constraints(category="shoes"),
            top_k=2,
            route="browsing",
        )

        self.assertEqual(reranker.calls, [])
        self.assertFalse(result.diagnostics["semantic_reranked"])
        self.assertEqual(result.diagnostics["semantic_specific_constraint_count"], 0)

    def test_semantic_reranker_can_reorder_only_specific_filtered_candidates(self) -> None:
        reranker = FakeSemanticReranker(
            [
                "UNKNOWN",
                "AAA_TIE_LOW",
                "AAA_TIE_LOW",
                "ZZZ_TIE_POPULAR",
                "MMM_TIE_MIDDLE",
            ]
        )
        semantic_search = CatalogSearch(
            self.search.catalog_path,
            semantic_reranker=reranker,
            semantic_weight=10.0,
        )
        self.addCleanup(semantic_search.connection.close)

        result = semantic_search.search(
            query="green cotton casual shirt",
            constraints=constraints(
                category="shirts",
                material="cotton",
                color="green",
            ),
            top_k=3,
            constraint_priorities={
                "category": "required",
                "material": "required",
                "color": "required",
            },
            route="buying",
        )

        self.assertEqual(
            result.recommendation_ids,
            ["ZZZ_TIE_POPULAR", "MMM_TIE_MIDDLE", "AAA_TIE_LOW"],
        )
        self.assertNotIn("UNKNOWN", result.recommendation_ids)
        self.assertEqual(len(result.recommendation_ids), len(set(result.recommendation_ids)))
        self.assertTrue(result.diagnostics["semantic_reranked"])
        self.assertEqual(result.diagnostics["semantic_candidate_count"], 3)
        self.assertEqual(result.diagnostics["semantic_specific_constraint_count"], 2)
        self.assertTrue(result.diagnostics["semantic_protected_first"])
        self.assertEqual(result.diagnostics["semantic_protected_head_count"], 2)
        self.assertEqual(result.diagnostics["semantic_gate_reason"], "applied")

    def test_semantic_reranker_protects_two_qualifying_head_candidates(self) -> None:
        reranker = FakeSemanticReranker(
            ["MMM_TIE_MIDDLE", "AAA_TIE_LOW", "ZZZ_TIE_POPULAR"]
        )
        semantic_search = CatalogSearch(
            self.search.catalog_path,
            semantic_reranker=reranker,
            semantic_weight=10.0,
        )
        self.addCleanup(semantic_search.connection.close)

        result = semantic_search.search(
            query="green cotton casual shirt",
            constraints=constraints(
                category="shirts",
                material="cotton",
                color="green",
            ),
            top_k=3,
            constraint_priorities={
                "category": "required",
                "material": "required",
                "color": "required",
            },
            route="buying",
        )

        self.assertEqual(
            result.recommendation_ids,
            ["ZZZ_TIE_POPULAR", "MMM_TIE_MIDDLE", "AAA_TIE_LOW"],
        )
        self.assertEqual(result.diagnostics["semantic_protected_head_count"], 2)

    def test_caller_can_disable_semantic_reranking(self) -> None:
        baseline = self.search.search(
            query="green cotton casual shirt",
            constraints=constraints(
                category="shirts",
                material="cotton",
                color="green",
            ),
            top_k=3,
            constraint_priorities={
                "category": "required",
                "material": "required",
                "color": "required",
            },
            route="buying",
        )
        reranker = FakeSemanticReranker(
            ["AAA_TIE_LOW", "ZZZ_TIE_POPULAR", "MMM_TIE_MIDDLE"]
        )
        semantic_search = CatalogSearch(
            self.search.catalog_path,
            semantic_reranker=reranker,
            semantic_weight=10.0,
        )
        self.addCleanup(semantic_search.connection.close)

        result = semantic_search.search(
            query="green cotton casual shirt",
            constraints=constraints(
                category="shirts",
                material="cotton",
                color="green",
            ),
            top_k=3,
            constraint_priorities={
                "category": "required",
                "material": "required",
                "color": "required",
            },
            route="buying",
            semantic_rerank_allowed=False,
        )

        self.assertEqual(result.recommendation_ids, baseline.recommendation_ids)
        self.assertEqual(reranker.calls, [])
        self.assertFalse(result.diagnostics["semantic_reranked"])
        self.assertEqual(
            result.diagnostics["semantic_gate_reason"], "disabled_by_caller"
        )

    def test_semantic_diagnostics_capture_scores_and_rank_movement(self) -> None:
        reranker = FakeScoredSemanticReranker([0.1, 0.9, 0.5])
        semantic_search = CatalogSearch(
            self.search.catalog_path,
            semantic_reranker=reranker,
            semantic_weight=10.0,
            enable_ranking_diagnostics=True,
        )
        self.addCleanup(semantic_search.connection.close)

        result = semantic_search.search(
            query="green cotton casual shirt",
            constraints=constraints(
                category="shirts",
                material="cotton",
                color="green",
            ),
            top_k=3,
            constraint_priorities={
                "category": "preferred",
                "material": "preferred",
                "color": "preferred",
            },
            route="buying",
        )

        self.assertEqual(len(reranker.calls), 1)
        self.assertTrue(result.diagnostics["semantic_scores_available"])
        self.assertEqual(result.diagnostics["semantic_gate_reason"], "applied")
        self.assertAlmostEqual(result.diagnostics["semantic_confidence_gap"], 0.8)
        candidates = result.diagnostics["ranking_candidates"]
        by_id = {candidate["parent_asin"]: candidate for candidate in candidates}
        self.assertEqual(by_id["ZZZ_TIE_POPULAR"]["semantic_score"], 0.1)
        self.assertEqual(by_id["ZZZ_TIE_POPULAR"]["semantic_rank"], 3)
        self.assertEqual(
            candidates[0]["required_constraint_coverage"],
            {},
        )

    def test_small_semantic_score_gap_preserves_deterministic_ranking(self) -> None:
        baseline = self.search.search(
            query="green cotton casual shirt",
            constraints=constraints(
                category="shirts",
                material="cotton",
                color="green",
            ),
            top_k=3,
            constraint_priorities={
                "category": "preferred",
                "material": "preferred",
                "color": "preferred",
            },
            route="buying",
        )
        reranker = FakeScoredSemanticReranker([0.1, 0.45, 0.3])
        semantic_search = CatalogSearch(
            self.search.catalog_path,
            semantic_reranker=reranker,
            semantic_weight=10.0,
            semantic_min_score_gap=0.5,
        )
        self.addCleanup(semantic_search.connection.close)

        result = semantic_search.search(
            query="green cotton casual shirt",
            constraints=constraints(
                category="shirts",
                material="cotton",
                color="green",
            ),
            top_k=3,
            constraint_priorities={
                "category": "preferred",
                "material": "preferred",
                "color": "preferred",
            },
            route="buying",
        )

        self.assertEqual(result.recommendation_ids, baseline.recommendation_ids)
        self.assertFalse(result.diagnostics["semantic_reranked"])
        self.assertEqual(
            result.diagnostics["semantic_gate_reason"],
            "insufficient_semantic_confidence",
        )
        self.assertAlmostEqual(result.diagnostics["semantic_confidence_gap"], 0.35)

    def test_semantic_reranker_is_skipped_for_underspecified_buying_route(self) -> None:
        reranker = FakeSemanticReranker(["SHOE_CANVAS_LEATHER_STORE"])
        semantic_search = CatalogSearch(
            self.search.catalog_path,
            semantic_reranker=reranker,
        )
        self.addCleanup(semantic_search.connection.close)

        result = semantic_search.search(
            query="black leather walking shoes",
            constraints=constraints(category="shoes", material="leather"),
            top_k=2,
            constraint_priorities={"category": "required", "material": "required"},
            route="buying",
        )

        self.assertEqual(reranker.calls, [])
        self.assertFalse(result.diagnostics["semantic_reranked"])

    def test_semantic_reranker_failure_preserves_deterministic_results(self) -> None:
        baseline = self.search.search(
            query="green cotton casual shirt",
            constraints=constraints(category="shirts"),
            top_k=2,
            route="browsing",
        )
        reranker = FakeSemanticReranker(error=RuntimeError("model unavailable"))
        semantic_search = CatalogSearch(
            self.search.catalog_path,
            semantic_reranker=reranker,
        )
        self.addCleanup(semantic_search.connection.close)

        result = semantic_search.search(
            query="green cotton casual shirt",
            constraints=constraints(category="shirts"),
            top_k=2,
            route="browsing",
        )

        self.assertEqual(result.recommendation_ids, baseline.recommendation_ids)
        self.assertFalse(result.diagnostics["semantic_reranked"])

    def test_exact_feature_phrase_bonus_beats_non_contiguous_token_overlap(self) -> None:
        required_constraints = constraints(feature="All Motion Comfort")
        exact_score = self.search._rerank_score(
            self.search.products["FEATURE_PHRASE_EXACT"],
            1.0,
            required_constraints,
            {"feature": "required"},
            {},
        )
        overlap_score = self.search._rerank_score(
            self.search.products["FEATURE_TOKEN_OVERLAP"],
            1.0,
            required_constraints,
            {"feature": "required"},
            {},
        )

        self.assertIsNotNone(exact_score)
        self.assertIsNotNone(overlap_score)
        self.assertGreater(exact_score, overlap_score)

    def test_generic_feature_phrase_does_not_receive_a_bonus(self) -> None:
        product = self.search.products["FEATURE_PHRASE_EXACT"]

        self.assertEqual(
            self.search._exact_feature_phrase_bonus(
                product,
                constraints(feature="Machine Wash"),
            ),
            0.0,
        )

    def test_catalog_common_feature_clauses_are_preferred_unless_explicit(self) -> None:
        self.search.catalog_size = 1_000
        self.search.feature_term_document_frequency.update(
            {"machine": 500, "wash": 500, "motion": 2, "comfort": 2}
        )

        self.assertEqual(
            self.search.feature_priority([("Machine Wash", "clarification")]),
            "preferred",
        )
        self.assertEqual(
            self.search.feature_priority([("All Motion Comfort", "clarification")]),
            "required",
        )
        self.assertEqual(
            self.search.feature_priority([("Machine Wash", "required")]),
            "required",
        )

if __name__ == "__main__":
    unittest.main()
