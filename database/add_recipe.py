#!/usr/bin/env python3
"""Add one recipe to the SQLite database.

    python database/add_recipe.py database/recipes/earl-grey-martini.json

The database file is database/mixology.db. Pass --database to use another file.
A new file is created from schema.sql. path is built from the title the same
way the recipe page builds it. To rebuild the database from every JSON file,
run database/build_database.py.
"""

import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path
from typing import TypeGuard, cast

from recipe_classes import ChoiceJson, Ingredient, IngredientJson, Recipe, RecipeError, RecipeJson, Step

ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE = ROOT / "mixology.db"
SCHEMA = ROOT / "schema.sql"


def recipe_path(title: str) -> str:
    """
    From a given recipe title, get the recipe path to be used in the URL,
    ie. for Spicy cocoa, it's spicy-cocoa.
    recipePath() in frontend/public/search/search.js builds this same path
    and returns it with /recipes/ in front.
    """
    decomposed = unicodedata.normalize("NFD", title)
    without_marks = "".join(
        character for character in decomposed if not unicodedata.category(character).startswith("M")
    )
    hyphenated = re.sub(r"[^a-z0-9]+", "-", without_marks.lower())
    return hyphenated.strip("-")


def load_recipe(file_path: Path) -> RecipeJson:
    """
    Load the recipe from the given JSON file and cast it to a RecipeJson.
    """
    try:
        recipe = json.loads(file_path.read_text())
    except json.JSONDecodeError as error:
        raise RecipeError(f"{file_path} is not valid JSON: {error}") from error
    if not isinstance(recipe, dict):
        raise RecipeError(f"{file_path} must contain a recipe object.")
    return cast(RecipeJson, recipe)


def require_text(value: str | None, field: str) -> str:
    """
    Validate that a recipe field, like its title, an ingredient name,
    an ingredient unit, a note, a family, and a step, is text and is not blank.
    Returns that text with the surrounding whitespace removed.
    """
    if not isinstance(value, str) or value.strip() == "":
        raise RecipeError(f"{field} must be text.")
    return value.strip()


def read_rows(connection: sqlite3.Connection, sql: str, label: str) -> list[sqlite3.Row]:
    """
    Run the given SQL query and return every row from that query.
    Used to read in the unit names, season names, spirit family names, and spirit aliases.
    A missing table, or a query that returns nothing, raises RecipeError:
    "Rebuild the database so {label} are stored."
    """
    try:
        rows = connection.execute(sql).fetchall()
    except sqlite3.OperationalError as error:
        raise RecipeError(f"Rebuild the database so {label} are stored.") from error
    if not rows:
        raise RecipeError(f"Rebuild the database so {label} are stored.")
    return rows


def read_units(connection: sqlite3.Connection) -> tuple[str, ...]:
    """
    Gets the tuple of unit names an ingredient line can use,
    such as fl oz, cup, and dash, as defined in schema.sql.
    """
    rows = read_rows(connection, "SELECT name FROM units ORDER BY rowid", "units")
    return tuple(row["name"] for row in rows)


def read_seasons(connection: sqlite3.Connection) -> tuple[str, ...]:
    """
    Gets the tuple of season names a recipe can use,
    such as spring, summer, autumn, and winter, as defined in schema.sql.
    """
    rows = read_rows(connection, "SELECT name FROM seasons ORDER BY rowid", "seasons")
    return tuple(row["name"] for row in rows)


def read_spirit_families(connection: sqlite3.Connection) -> tuple[str, ...]:
    """
    Gets the tuple of spirit family names a spirit can belong to,
    such as rum and whiskey, as defined in schema.sql.
    """
    rows = read_rows(connection, "SELECT name FROM spirit_families ORDER BY rowid", "spirit families")
    return tuple(row["name"] for row in rows)


def read_spirit_aliases(connection: sqlite3.Connection) -> dict[str, str]:
    """
    Gets the dictionary whose keys are words that can appear in a spirit name,
    such as rum, rhum, whiskey, and whisky.
    Each value is the family that word belongs to, and every value is a name
    from the spirit families, as defined in schema.sql.
    """
    rows = read_rows(
        connection, "SELECT alias, family FROM spirit_aliases ORDER BY rowid", "spirit families"
    )
    return {row["alias"]: row["family"] for row in rows}


def join_names_with_or(names: tuple[str, ...]) -> str:
    """
    Join the given names with "or" in between them.
    Used to list the allowed values for a recipe field, such as season or family.
    """
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} or {names[1]}"
    return f"{', '.join(names[:-1])}, or {names[-1]}"


def validate_recipe(
    recipe: RecipeJson,
    seasons: tuple[str, ...],
    units: tuple[str, ...],
    spirit_families: tuple[str, ...],
    spirit_aliases: dict[str, str],
) -> Recipe:
    """
    Validate every field of a recipe and return the recipe
    ready to be inserted into the SQLite database.
    The path is built from the title. A bad field raises RecipeError.
    """
    title = require_text(recipe.get("title"), "title")
    path = recipe_path(title)
    if path == "":
        raise RecipeError(f"{title!r} has no address.")

    portions = recipe.get("portions")
    if isinstance(portions, bool) or not isinstance(portions, int) or portions < 1:
        raise RecipeError("portions must be an integer of at least 1.")

    season = recipe.get("season")
    if not isinstance(season, str) or season.strip() == "":
        raise RecipeError("A recipe needs a season.")
    season = season.strip()
    if season not in seasons:
        raise RecipeError(f"season must be {join_names_with_or(seasons)}.")

    # The photo is an image. The database stores its address, which must be text
    # and which the page puts in img.src.
    photo = recipe.get("photo")
    if photo is not None:
        photo = require_text(photo, "photo")

    ingredients = recipe.get("ingredients")
    if not isinstance(ingredients, list) or len(ingredients) == 0:
        raise RecipeError("A recipe needs at least one ingredient.")

    steps = recipe.get("steps")
    if not isinstance(steps, list) or len(steps) == 0:
        raise RecipeError("A recipe needs at least one step.")

    return {
        "title": title,
        "path": path,
        "portions": portions,
        "season": season,
        "photo": photo,
        "ingredients": validate_ingredients(ingredients, units, spirit_families, spirit_aliases),
        "steps": [validate_step(item, index) for index, item in enumerate(steps, start=1)],
    }


def is_choice(item: IngredientJson | ChoiceJson) -> TypeGuard[ChoiceJson]:
    """
    Return true when this ingredient-list item is a choice.
    A choice holds the ingredient options to pick from, as opposed to a single ingredient.
    """
    return isinstance(item, dict) and "choice" in item


def validate_ingredients(
    items: list[IngredientJson | ChoiceJson],
    units: tuple[str, ...],
    spirit_families: tuple[str, ...],
    spirit_aliases: dict[str, str],
) -> list[Ingredient]:
    """
    Validate every ingredient and return the ingredient lines
    ready to be inserted into the SQLite database.
    Each line gets its position. Each choice gets a choice group.
    A bad ingredient raises RecipeError.
    """
    ingredients: list[Ingredient] = []
    position = 1
    choice_group = 0
    for item in items:
        if is_choice(item):
            choice_group += 1
            options, position = validate_choice(
                item, choice_group, position, units, spirit_families, spirit_aliases
            )
            ingredients.extend(options)
        else:
            ingredients.append(
                validate_ingredient(item, position, units, spirit_families, spirit_aliases)
            )
            position += 1
    return ingredients


def validate_choice(
    item: ChoiceJson,
    choice_group: int,
    position: int,
    units: tuple[str, ...],
    spirit_families: tuple[str, ...],
    spirit_aliases: dict[str, str],
) -> tuple[list[Ingredient], int]:
    """
    Validate one choice and return its ingredient lines
    ready to be inserted into the SQLite database, plus the next position.
    A choice lists at least two different ingredients, and nothing else.
    A bad choice raises RecipeError.
    """
    if set(item) != {"choice"}:
        raise RecipeError("A choice only lists its ingredients.")
    options = item["choice"]
    if not isinstance(options, list) or len(options) < 2:
        raise RecipeError("A choice needs at least two ingredients.")
    ingredients: list[Ingredient] = []
    for option in options:
        if isinstance(option, dict) and "choice" in option:
            raise RecipeError("A choice cannot contain another choice.")
        ingredients.append(
            validate_ingredient(
                option, position, units, spirit_families, spirit_aliases, choice_group
            )
        )
        position += 1
    names = [ingredient["name"].lower() for ingredient in ingredients]
    if len(names) != len(set(names)):
        raise RecipeError("A choice needs different ingredients.")
    return ingredients, position


def validate_ingredient(
    item: IngredientJson,
    position: int,
    units: tuple[str, ...],
    spirit_families: tuple[str, ...],
    spirit_aliases: dict[str, str],
    choice_group: int | None = None,
) -> Ingredient:
    """
    Validate one ingredient and return the ingredient line
    ready to be inserted into the SQLite database.
    The line keeps the position and choice group it was given.
    A spirit whose name contains a family word gets that family.
    A bad field raises RecipeError.
    """
    if not isinstance(item, dict):
        raise RecipeError(f"Ingredient {position} must be an object.")
    name = require_text(item.get("name"), f"Ingredient {position} name")
    note = item.get("note")
    if note is not None:
        note = require_text(note, f"Ingredient {position} note")

    quantity = item.get("quantity")
    unit = item.get("unit")
    has_quantity = quantity is not None
    has_unit = unit is not None
    if has_quantity != has_unit:
        raise RecipeError(f"{name} needs both a quantity and a unit, or neither.")

    optional = item.get("optional", False)
    if not isinstance(optional, bool):
        raise RecipeError(f"{name} optional must be true or false.")
    if not has_quantity and note is None and choice_group is None and not optional:
        raise RecipeError(f"{name} needs an amount or a note.")
    if has_quantity:
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or quantity <= 0:
            raise RecipeError(f"{name} needs a quantity above 0.")
        unit = require_text(unit, f"{name} unit")
        if unit not in units:
            raise RecipeError(f"{name} has a unit that this book does not store.")

    is_spirit = item.get("is_spirit")
    if is_spirit is not None and not isinstance(is_spirit, bool):
        raise RecipeError(f"{name} is_spirit must be true or false.")

    family = item.get("family")
    if family is not None:
        family = require_text(family, f"{name} family").lower()
        if family not in spirit_families:
            raise RecipeError(f"{name} family must be {join_names_with_or(spirit_families)}.")
    if is_spirit is True:
        inferred = get_spirit_family_from_name(name, spirit_aliases)
        if family is None:
            family = inferred
        elif inferred is not None and inferred != family:
            raise RecipeError(f"{name} belongs to the {inferred} family.")
    elif family is not None:
        raise RecipeError(f"{name} can belong to the {family} family only when it is a spirit.")

    return {
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "note": note,
        "is_spirit": is_spirit,
        "family": family,
        "choice_group": choice_group,
        "optional": optional,
        "position": position,
    }


def get_spirit_family_from_name(name: str, spirit_aliases: dict[str, str]) -> str | None:
    """
    Return the spirit family named by a word in this spirit's name,
    such as rum for white rum and whiskey for Scotch whiskey.
    Return None when the name contains no family word.
    A name that contains two families raises RecipeError.
    """
    words = re.findall(r"[a-z0-9]+", name.lower())
    found = {spirit_aliases[word] for word in words if word in spirit_aliases}
    if len(found) > 1:
        raise RecipeError(f"{name} names more than one spirit family.")
    if len(found) == 1:
        return next(iter(found))
    return None


def validate_step(item: str, position: int) -> Step:
    """
    Validate one step in recipe instructions and return the step
    ready to be inserted into the SQLite database.
    The step keeps the position it was given.
    A bad step raises RecipeError.
    """
    return {"position": position, "instruction": require_text(item, f"Step {position}")}


def open_database(database: Path) -> sqlite3.Connection:
    """
    Open the SQLite database and return a connection ready for recipes.
    Create the parent directory if needed. When the recipes table is missing,
    create the tables from schema.sql. An existing database is left as it is.
    """
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.isolation_level = None
    connection.execute("PRAGMA foreign_keys = ON")
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'recipes'"
    ).fetchone()
    if exists is None:
        connection.executescript(SCHEMA.read_text())
        connection.execute("PRAGMA foreign_keys = ON")
    return connection


def get_or_store_ingredient_id(connection: sqlite3.Connection, ingredient: Ingredient) -> int:
    """
    Return the id of this ingredient in the ingredients table.
    Store the ingredient when it is not there yet.
    A stored ingredient keeps its spirit flag.
    A family can be filled in when the stored ingredient has none.
    A conflicting spirit flag or family raises RecipeError.
    """
    row = connection.execute(
        "SELECT id, name, is_spirit, family FROM ingredients WHERE name = ?",
        (ingredient["name"],),
    ).fetchone()
    if row is None:
        cursor = connection.execute(
            "INSERT INTO ingredients (name, is_spirit, family) VALUES (?, ?, ?)",
            (ingredient["name"], int(ingredient["is_spirit"] or False), ingredient["family"]),
        )
        if cursor.lastrowid is None:
            raise RecipeError(f"Could not store {ingredient['name']}.")
        return cursor.lastrowid
    if ingredient["is_spirit"] is not None and bool(row["is_spirit"]) != ingredient["is_spirit"]:
        stored = "a spirit" if row["is_spirit"] else "not a spirit"
        raise RecipeError(f"{row['name']} is already stored as {stored}.")
    if ingredient["family"] is not None and row["family"] not in (None, ingredient["family"]):
        raise RecipeError(f"{row['name']} is already in the {row['family']} family.")
    if ingredient["family"] is not None and row["family"] is None:
        connection.execute(
            "UPDATE ingredients SET family = ? WHERE id = ?",
            (ingredient["family"], row["id"]),
        )
    return row["id"]


def add_recipe(connection: sqlite3.Connection, recipe: Recipe) -> None:
    """
    Insert one recipe into the open SQLite database.
    The recipe, its ingredient lines, and its steps are stored together.
    A recipe that is already stored raises RecipeError.
    A failed insert is rolled back.
    """
    try:
        connection.execute("BEGIN")
        cursor = connection.execute(
            """
            INSERT INTO recipes (path, title, portions, season, photo)
            VALUES (?, ?, ?, ?, ?)
            """,
            (recipe["path"], recipe["title"], recipe["portions"], recipe["season"], recipe["photo"]),
        )
        if cursor.lastrowid is None:
            raise RecipeError(f"Could not store {recipe['title']}.")
        recipe_id = cursor.lastrowid
        for ingredient in recipe["ingredients"]:
            connection.execute(
                """
                INSERT INTO recipe_ingredients
                    (recipe_id, ingredient_id, position, choice_group, quantity, unit, note, optional)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recipe_id,
                    get_or_store_ingredient_id(connection, ingredient),
                    ingredient["position"],
                    ingredient["choice_group"],
                    ingredient["quantity"],
                    ingredient["unit"],
                    ingredient["note"],
                    int(ingredient["optional"]),
                ),
            )
        connection.executemany(
            "INSERT INTO steps (recipe_id, position, instruction) VALUES (?, ?, ?)",
            [(recipe_id, step["position"], step["instruction"]) for step in recipe["steps"]],
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        connection.rollback()
        if "recipes.path" in str(error):
            raise RecipeError(f"{recipe['title']} is already stored.") from error
        raise RecipeError(str(error)) from error
    except Exception:
        connection.rollback()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Add one recipe to the SQLite database.")
    parser.add_argument("recipe", type=Path, help="JSON file for one recipe")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE, help="SQLite database file")
    args = parser.parse_args()

    try:
        connection = open_database(args.database)
        try:
            recipe = validate_recipe(
                load_recipe(args.recipe),
                read_seasons(connection),
                read_units(connection),
                read_spirit_families(connection),
                read_spirit_aliases(connection),
            )
            add_recipe(connection, recipe)
        finally:
            connection.close()
    except RecipeError as error:
        print(error, file=sys.stderr)
        return 1

    print(f"Added {recipe['title']} at /recipes/{recipe['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
