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

if __name__ == "__main__":
    unittest.main()
