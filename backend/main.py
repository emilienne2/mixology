"""Read-only API for the Chez Émilienne recipe book."""

import json
import os
import sqlite3
from pathlib import Path
from typing import TypedDict

import httpx
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


class ChatTurn(TypedDict):
    role: str
    text: str


class ChatRequest(TypedDict):
    portions: int
    measure: str
    question: str
    messages: list[ChatTurn]


class ChatReply(TypedDict):
    reply: str
    exchangesIncluded: int
    earlierExchangesOmitted: bool


# Gemini 3.5 Flash-Lite on Google's free tier answers Get Creative.
# Google may use those requests to improve its models.
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
# One new question. A saved reply is not limited; only the recent exchanges are sent.
QUESTION_CHARACTER_LIMIT = 500
# Completed exchanges included with a new question. Older ones stay on the page.
EXCHANGES_INCLUDED = 6
# How long the API waits for Gemini, in seconds.
ASSISTANT_TIMEOUT_SECONDS = 30
ASSISTANT_INSTRUCTION = (
    "You suggest a change to one cocktail from Chez Émilienne. "
    "The saved recipe stays as it is. Describe what the reader can do instead. "
    "Answer for the portion count and measurement system in the question. "
    "Keep the reply to a short paragraph."
)


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
    return load_recipe_page(path)


def load_recipe_page(path: str) -> RecipePage:
    """The recipe stored at this path. A missing path is a 404."""
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


@app.post("/api/recipes/{path}/chat")
def discuss_recipe(path: str, request: ChatRequest) -> ChatReply:
    """
    Ask Gemini how to change the recipe stored at this path.
    The recipe is read from the database. The reply is not saved.
    A missing path is a 404.
    """
    page = load_recipe_page(path)
    question = checked_chat(request)
    included, omitted = included_exchanges(question["messages"])
    question["messages"] = included
    prompt = assistant_prompt(page, question)
    return {
        "reply": ask_gemini(prompt),
        "exchangesIncluded": EXCHANGES_INCLUDED,
        "earlierExchangesOmitted": omitted,
    }


def checked_chat(request: ChatRequest) -> ChatRequest:
    """The question and earlier turns, with empty text removed. A bad field is a 400."""
    portions = request["portions"]
    if isinstance(portions, bool) or not isinstance(portions, int) or portions < 1:
        raise HTTPException(status_code=400, detail="A recipe needs a portion count.")
    measure = request["measure"]
    if measure not in ("us", "metric"):
        raise HTTPException(status_code=400, detail="Choose US or metric measurements.")
    question = request["question"].strip()
    if question == "":
        raise HTTPException(status_code=400, detail="Ask a question about this recipe.")
    if len(question) > QUESTION_CHARACTER_LIMIT:
        raise HTTPException(status_code=400, detail="Ask a shorter question.")
    messages: list[ChatTurn] = []
    for turn in request["messages"]:
        role = turn["role"]
        text = turn["text"].strip()
        if role not in ("user", "assistant") or text == "":
            raise HTTPException(status_code=400, detail="The conversation could not be read.")
        messages.append({"role": role, "text": text})
    return {
        "portions": portions,
        "measure": measure,
        "question": question,
        "messages": messages,
    }


def included_exchanges(messages: list[ChatTurn]) -> tuple[list[ChatTurn], bool]:
    """The most recent exchanges sent with a question. Older ones are left out."""
    kept = EXCHANGES_INCLUDED * 2
    if len(messages) <= kept:
        return messages, False
    recent = messages[-kept:]
    if recent[0]["role"] == "assistant":
        recent = recent[1:]
    return recent, True


def assistant_prompt(page: RecipePage, request: ChatRequest) -> str:
    """The recipe, the reader's portion count and measurements, and the conversation."""
    measure = "metric" if request["measure"] == "metric" else "US"
    lines = [
        f"The saved recipe serves {page['portions']}.",
        f"The reader is making {request['portions']}.",
        f"The reader is using {measure} measurements.",
        "Amounts below are the saved recipe, in US units, before scaling.",
        "",
        page["title"],
        f"Season: {page['season']}",
        "",
        "Ingredients:",
    ]
    lines.extend(f"- {line}" for line in ingredient_texts(page["ingredients"]))
    lines.append("")
    lines.append("Steps:")
    lines.extend(f"{index}. {step}" for index, step in enumerate(page["steps"], start=1))
    if request["messages"]:
        lines.append("")
        lines.append("Earlier in this conversation:")
        for turn in request["messages"]:
            speaker = "Reader" if turn["role"] == "user" else "Assistant"
            lines.append(f"{speaker}: {turn['text']}")
    lines.append("")
    lines.append(f"Question: {request['question']}")
    return "\n".join(lines)


def ingredient_texts(ingredients: list[IngredientLine]) -> list[str]:
    """One line per ingredient. A choice slot is joined with 'or'."""
    groups: list[list[IngredientLine]] = []
    for line in ingredients:
        same_choice = (
            line["choiceGroup"] is not None
            and groups
            and groups[-1][0]["choiceGroup"] == line["choiceGroup"]
        )
        if same_choice:
            groups[-1].append(line)
        else:
            groups.append([line])
    texts: list[str] = []
    for group in groups:
        text = " or ".join(one_ingredient_text(line) for line in group)
        if all(line["optional"] for line in group):
            text = f"{text}, optional"
        texts.append(text)
    return texts


def one_ingredient_text(line: IngredientLine) -> str:
    """A stored amount, or a name with its note when the line has no amount."""
    if line["quantity"] is None or line["unit"] is None:
        if line["note"]:
            return f"{line['name']} ({line['note']})"
        return line["name"]
    text = f"{line['quantity']:g} {line['unit']} {line['name']}"
    if line["note"]:
        return f"{text} ({line['note']})"
    return text


def ask_gemini(prompt: str) -> str:
    """Send one question to Gemini and return the reply text."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key == "":
        raise HTTPException(status_code=503, detail="The assistant is not connected yet.")
    # The page sends the recipe and the visible chat on every question.
    # store is false so Google is not asked to keep a conversation for the next turn.
    try:
        response = httpx.post(
            GEMINI_URL,
            headers={"x-goog-api-key": key},
            json={
                "model": GEMINI_MODEL,
                "store": False,
                "system_instruction": ASSISTANT_INSTRUCTION,
                "input": prompt,
            },
            timeout=ASSISTANT_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="The assistant did not answer.") from None
    if response.status_code != 200:
        message = provider_message(response.text)
        if message == "":
            message = "The assistant did not answer."
        raise HTTPException(status_code=502, detail=message)
    reply = model_reply(response.text)
    if reply == "":
        raise HTTPException(status_code=502, detail="The assistant did not answer.")
    return reply


def provider_message(payload: str) -> str:
    """Google's error message, when the body has one."""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    error = parsed.get("error")
    if not isinstance(error, dict):
        return ""
    message = error.get("message")
    if not isinstance(message, str):
        return ""
    return message.strip()


def model_reply(payload: str) -> str:
    """The text of the model steps. Empty when the body has none."""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    steps = parsed.get("steps")
    if not isinstance(steps, list):
        return ""
    parts: list[str] = []
    for step in steps:
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        parts.extend(content_texts(step.get("content")))
    return "\n".join(part for part in parts if part != "").strip()


def content_texts(content: str | list[str | dict[str, str]] | None) -> list[str]:
    """Text blocks from a model step. A plain string is one block."""
    if isinstance(content, str):
        return [content.strip()]
    if not isinstance(content, list):
        return []
    texts: list[str] = []
    for block in content:
        if isinstance(block, str):
            texts.append(block.strip())
        elif isinstance(block, dict):
            text = block.get("text")
            if isinstance(text, str):
                texts.append(text.strip())
    return texts


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
