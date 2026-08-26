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

        first_shoe_rank = min(
            results.index("SHOE_IN_BUDGET"),
            results.index("SHOE_OVER_BUDGET"),
        )
        self.assertLess(first_shoe_rank, results.index("BAG_BLACK"))

    def test_budget_constraint_excludes_known_over_budget_product(self) -> None:
        results = self.search.search(
            query="black leather shoes",
            constraints=constraints(category="shoes", budget=100.0),
            top_k=10,
        )

        self.assertIn("SHOE_IN_BUDGET", results)
        self.assertNotIn("SHOE_OVER_BUDGET", results)

    def test_search_returns_unique_catalog_identifiers(self) -> None:
        results = self.search.search(
            query="black leather",
            constraints=constraints(material="leather", color="black"),
            top_k=2,
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(len(results), len(set(results)))
        self.assertTrue(set(results).issubset({row["parent_asin"] for row in CATALOG_ROWS}))


if __name__ == "__main__":
    unittest.main()
