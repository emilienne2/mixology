"""Checks for the loader rules that building the database does not cover.

    python -m unittest database/test_recipe_rules.py
"""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent))

from add_recipe import (
    get_or_store_ingredient_id,
    get_spirit_family_from_name,
    open_database,
    read_spirit_aliases,
    recipe_path,
)
from recipe_classes import Ingredient, RecipeError


def sugar(grams_per_cup: float) -> Ingredient:
    return {
        "name": "sugar",
        "quantity": 1,
        "unit": "cup",
        "note": None,
        "is_spirit": False,
        "family": None,
        "grams_per_cup": grams_per_cup,
        "choice_group": None,
        "optional": False,
        "position": 1,
    }


class RecipeRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.connection = open_database(Path(self.directory.name) / "mixology.db")

    def tearDown(self) -> None:
        self.connection.close()
        self.directory.cleanup()

    def test_recipe_path(self) -> None:
        self.assertEqual(recipe_path("Piña colada smoothie"), "pina-colada-smoothie")
        self.assertEqual(
            recipe_path("Pumpkin old fashioned à la mode"),
            "pumpkin-old-fashioned-a-la-mode",
        )
        self.assertEqual(recipe_path("Goldwyn (non) follies"), "goldwyn-non-follies")

    def test_conflicting_cup_weight_is_rejected(self) -> None:
        get_or_store_ingredient_id(self.connection, sugar(200))
        with self.assertRaises(RecipeError):
            get_or_store_ingredient_id(self.connection, sugar(220))

    def test_spirit_family_comes_from_the_name(self) -> None:
        aliases = read_spirit_aliases(self.connection)
        self.assertEqual(get_spirit_family_from_name("white rum", aliases), "rum")
        with self.assertRaises(RecipeError):
            get_spirit_family_from_name("rum whiskey", aliases)


if __name__ == "__main__":
    unittest.main()
