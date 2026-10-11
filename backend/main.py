"""Read-only API for the Chez Émilienne recipe book."""

import os
import sqlite3
from pathlib import Path
from typing import TypedDict

from fastapi import FastAPI, HTTPException, Query

app = FastAPI()
DATABASE = Path(os.environ.get("DATABASE_PATH", "database/mixology.db"))


class Season(TypedDict):
    name: str
    label: str
    emoji: str


class RecipeLink(TypedDict):
    title: str
    path: str


class IngredientLine(TypedDict):
    name: str
    quantity: float | None
    unit: str | None
    note: str | None
    optional: bool
    choiceGroup: int | None
    gramsPerCup: float | None


class RecipePage(TypedDict):
    title: str
    portions: int
    season: str
    photo: str | None
    ingredients: list[IngredientLine]
    steps: list[str]


def open_database() -> sqlite3.Connection:
    """Open the recipe database read-only."""
    if not DATABASE.is_file():
        raise HTTPException(status_code=500, detail="The recipe database is not built.")
    connection = sqlite3.connect(f"{DATABASE.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def read_rows(sql: str, parameters: tuple[str | int, ...] = ()) -> list[sqlite3.Row]:
    """Run one read query and return every row."""
    connection = open_database()
    try:
        return list(connection.execute(sql, parameters))
    finally:
        connection.close()


def recipe_link(row: sqlite3.Row) -> RecipeLink:
    """The title the page shows and the stored path it links to."""
    return {"title": row["title"], "path": row["path"]}


def ingredient_line(row: sqlite3.Row) -> IngredientLine:
    """One ingredient line in the shape the recipe page already shows."""
    return {
        "name": row["name"],
        "quantity": row["quantity"],
        "unit": row["unit"],
        "note": row["note"],
        "optional": bool(row["optional"]),
        "choiceGroup": row["choice_group"],
        "gramsPerCup": row["grams_per_cup"],
    }


@app.get("/api/seasons")
def seasons() -> list[Season]:
    """
    Return the seasons in table order.
    Each season includes the stored name, the label, and the emoji the page shows.
    """
    rows = read_rows("SELECT name, label, emoji FROM seasons ORDER BY rowid")
    if not rows:
        raise HTTPException(status_code=500, detail="The recipe database has no seasons.")
    return [{"name": row["name"], "label": row["label"], "emoji": row["emoji"]} for row in rows]


@app.get("/api/spirits")
def spirit_names() -> list[str]:
    """
    Return the spirit names in alphabetical order.
    The home page puts each name on a checkbox and sends the checked names to search.
    A family name is included when no spirit is stored under that name, so wine appears.
    """
    rows = read_rows(
        """
        SELECT name FROM ingredients WHERE is_spirit = 1
        UNION
        SELECT name FROM spirit_families
        ORDER BY name COLLATE NOCASE
        """
    )
    return [row["name"] for row in rows]


@app.get("/api/recipe-titles")
def recipe_titles() -> list[RecipeLink]:
    """
    Return every recipe in alphabetical order.
    Each entry has the title the home page shows and the stored path it opens.
    """
    rows = read_rows("SELECT title, path FROM recipes ORDER BY title COLLATE NOCASE")
    return [recipe_link(row) for row in rows]


@app.get("/api/recipes/{path}")
def recipe(path: str) -> RecipePage:
    """
    Return one recipe for the page at /recipes/<path>.
    Ingredient lines use choiceGroup. Steps are the instruction strings, in page order.
    A missing path is a 404.
    """
    rows = read_rows(
        "SELECT id, title, portions, season, photo FROM recipes WHERE path = ?",
        (path,),
    )
    if len(rows) != 1:
        raise HTTPException(status_code=404, detail="No recipe has this path.")
    stored = rows[0]
    ingredients = read_rows(
        """
        SELECT ingredients.name, quantity, unit, note, optional, choice_group, ingredients.grams_per_cup
        FROM recipe_ingredients
        JOIN ingredients ON ingredients.id = recipe_ingredients.ingredient_id
        WHERE recipe_id = ?
        ORDER BY position
        """,
        (stored["id"],),
    )
    steps = read_rows(
        "SELECT instruction FROM steps WHERE recipe_id = ? ORDER BY position",
        (stored["id"],),
    )
    return {
        "title": stored["title"],
        "portions": stored["portions"],
        "season": stored["season"],
        "photo": stored["photo"],
        "ingredients": [ingredient_line(row) for row in ingredients],
        "steps": [row["instruction"] for row in steps],
    }


def contained_name(text: str) -> str:
    """A LIKE pattern matching an ingredient name that contains this text. % and _ are literal."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# A drink can be made without alcohol when no line requires a spirit.
# An optional spirit can be left out. A choice can be made without alcohol when one option is not a spirit.
ALCOHOL_FREE = """
NOT EXISTS (
    SELECT 1
    FROM recipe_ingredients
    JOIN ingredients ON ingredients.id = recipe_ingredients.ingredient_id
    WHERE recipe_ingredients.recipe_id = recipes.id
        AND recipe_ingredients.choice_group IS NULL
        AND recipe_ingredients.optional = 0
        AND ingredients.is_spirit = 1
)
AND NOT EXISTS (
    SELECT 1
    FROM recipe_ingredients
    JOIN ingredients ON ingredients.id = recipe_ingredients.ingredient_id
    WHERE recipe_ingredients.recipe_id = recipes.id
        AND recipe_ingredients.choice_group IS NOT NULL
    GROUP BY recipe_ingredients.choice_group
    HAVING SUM(ingredients.is_spirit = 0) = 0
)
"""


@app.get("/api/search")
def search(
    spirit: list[str] = Query(default=[]),
    ingredients: str = "",
    season: str = "",
    alcohol_free: bool = Query(default=False, alias="alcohol-free"),
) -> list[RecipeLink]:
    """
    Return recipes that match the search form, in alphabetical order.
    Each entry has the title the search page shows and the stored path it opens.
    Checked spirits match a drink that uses any of them. A family word such as rum matches every rum.
    The ingredient text matches a name that contains it, ignoring case, including an optional line or a choice.
    A season matches that season.
    Alcohol-free matches a drink with no required spirit.
    At least one criterion must be filled in.
    """
    spirit_names = [name.strip() for name in spirit if name.strip()]
    ingredient_text = ingredients.strip()
    season_name = season.strip()
    if not spirit_names and ingredient_text == "" and season_name == "" and not alcohol_free:
        raise HTTPException(
            status_code=400, detail="Choose a spirit, an ingredient, or a season."
        )

    clauses: list[str] = []
    parameters: list[str] = []
    if spirit_names:
        placeholders = ", ".join("lower(?)" for _ in spirit_names)
        clauses.append(
            f"""
            EXISTS (
                SELECT 1
                FROM recipe_ingredients
                JOIN spirit_search
                    ON spirit_search.ingredient_id = recipe_ingredients.ingredient_id
                WHERE recipe_ingredients.recipe_id = recipes.id
                    AND spirit_search.term IN ({placeholders})
            )
            """
        )
        parameters.extend(spirit_names)
    if ingredient_text != "":
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM recipe_ingredients
                JOIN ingredients ON ingredients.id = recipe_ingredients.ingredient_id
                WHERE recipe_ingredients.recipe_id = recipes.id
                    AND ingredients.name COLLATE NOCASE LIKE ? ESCAPE '\\'
            )
            """
        )
        parameters.append(contained_name(ingredient_text))
    if season_name != "":
        clauses.append("season = ?")
        parameters.append(season_name)
    if alcohol_free:
        clauses.append(ALCOHOL_FREE)

    rows = read_rows(
        f"""
        SELECT title, path FROM recipes
        WHERE {" AND ".join(clauses)}
        ORDER BY title COLLATE NOCASE
        """,
        tuple(parameters),
    )
    return [recipe_link(row) for row in rows]
