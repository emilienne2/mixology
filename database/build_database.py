#!/usr/bin/env python3
"""Replace the SQLite database with every recipe JSON file.

    python database/build_database.py

Reads database/recipes/*.json and writes database/mixology.db.
Adding one file to an existing database is add_recipe.py.
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from add_recipe import (
    DEFAULT_DATABASE,
    add_recipe,
    validate_recipe,
    open_database,
    load_recipe,
    read_seasons,
    read_spirit_aliases,
    read_spirit_families,
    read_units,
)
from recipe_classes import RecipeError

RECIPES = Path(__file__).resolve().parent / "recipes"


def main() -> int:
    files = sorted(RECIPES.glob("*.json"))
    if not files:
        print(f"No recipe files in {RECIPES}", file=sys.stderr)
        return 1

    handle, temporary_name = tempfile.mkstemp(suffix=".db", dir=DEFAULT_DATABASE.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    connection: sqlite3.Connection | None = None
    try:
        connection = open_database(temporary)
        seasons = read_seasons(connection)
        units = read_units(connection)
        spirit_families = read_spirit_families(connection)
        spirit_aliases = read_spirit_aliases(connection)
        for file_path in files:
            recipe = validate_recipe(
                load_recipe(file_path), seasons, units, spirit_families, spirit_aliases
            )
            add_recipe(connection, recipe)
            print(f"Added {recipe['title']} at /recipes/{recipe['path']}")
        connection.close()
        connection = None
        os.replace(temporary, DEFAULT_DATABASE)
    except RecipeError as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        if connection is not None:
            connection.close()
        if temporary.exists():
            temporary.unlink()

    count = len(files)
    label = "recipe" if count == 1 else "recipes"
    print(f"Built {DEFAULT_DATABASE.name} with {count} {label}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
