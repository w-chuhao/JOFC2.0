from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from starter.retrieval import CatalogRetriever


def product(asin: str, title: str, category: str, material: str, price: float = 50.0) -> dict:
    return {
        "parent_asin": asin,
        "title": title,
        "categories": ["Clothing, Shoes & Jewelry", category],
        "features": [material, "lightweight"],
        "details": {},
        "store": "Example Store",
        "description": [title, material],
        "price": price,
    }


class RetrievalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        catalog = Path(self.directory.name) / "catalog.jsonl"
        rows = [
            product("STEEL-1", "Lightweight stainless steel hoop earrings", "Earrings", "stainless steel", 35),
            product("LEATHER-1", "Lightweight leather hoop earrings", "Earrings", "leather", 90),
            product("SHOE-1", "Lightweight leather shoes", "Shoes", "leather", 120),
        ]
        rows.extend(product(f"FILLER-{number}", f"Lightweight hoop earrings {number}", "Earrings", "alloy", 150) for number in range(9))
        catalog.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        self.retriever = CatalogRetriever(catalog)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_returns_ten_valid_unique_ids_for_specific_query(self) -> None:
        result = self.retriever.search("lightweight stainless steel hoop earrings", {}, 10)
        self.assertEqual(len(result.recommendation_ids), 10)
        self.assertEqual(len(result.recommendation_ids), len(set(result.recommendation_ids)))
        self.assertEqual(result.recommendation_ids[0], "STEEL-1")

    def test_material_constraint_changes_ranking_toward_leather(self) -> None:
        result = self.retriever.search("lightweight hoop earrings", {"material": "leather"}, 10)
        self.assertIn(result.recommendation_ids[0], {"LEATHER-1", "SHOE-1"})

    def test_category_constraint_penalizes_unrelated_categories(self) -> None:
        result = self.retriever.search("lightweight leather", {"category": "earrings"}, 10)
        self.assertEqual(result.recommendation_ids[0], "LEATHER-1")
        self.assertNotIn("SHOE-1", result.recommendation_ids)

    def test_empty_query_returns_valid_results_without_crashing(self) -> None:
        result = self.retriever.search("", {}, 10)
        self.assertEqual(len(result.recommendation_ids), 10)
        self.assertTrue(all(result.recommendation_ids))

    def test_budget_constraint_prefers_an_affordable_match(self) -> None:
        result = self.retriever.search("lightweight hoop earrings", {"budget": 50}, 10)
        self.assertEqual(result.recommendation_ids[0], "STEEL-1")
        self.assertNotIn("LEATHER-1", result.recommendation_ids)


if __name__ == "__main__":
    unittest.main()
